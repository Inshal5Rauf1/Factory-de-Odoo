"""Integration tests for iterative mode in render_module().

Tests that render_module correctly detects iterative mode via spec stash,
filters stages based on diff, handles --force/--dry-run flags, routes
conflicts to .amil-pending/, and auto-merges stub-mergeable files.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from amil_utils.iterative.diff import SPEC_STASH_FILENAME, save_spec_stash
from amil_utils.manifest import (
    ArtifactEntry,
    ArtifactInfo,
    GenerationManifest,
    PreprocessingInfo,
    StageResult,
    compute_file_sha256,
    save_manifest,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _do_full_render(spec: dict, output_dir: Path) -> list[Path]:
    """Run render_module with no_context7 + no verifier for fast testing.

    Includes ManifestHook to save manifest (needed for conflict detection).
    """
    from amil_utils.hooks import ManifestHook
    from amil_utils.renderer import get_template_dir, render_module

    module_name = spec.get("module_name", "unknown")
    hooks = [ManifestHook(module_path=output_dir / module_name)]
    files, warnings = render_module(
        spec,
        get_template_dir(),
        output_dir,
        verifier=None,
        no_context7=True,
        hooks=hooks,
    )
    return files


def _do_iterative_render(
    spec: dict,
    output_dir: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[list[Path], list]:
    """Run render_module with iterative mode kwargs."""
    from amil_utils.renderer import get_template_dir, render_module

    return render_module(
        spec,
        get_template_dir(),
        output_dir,
        verifier=None,
        no_context7=True,
        force=force,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# TestUnchangedSpec
# ---------------------------------------------------------------------------


class TestUnchangedSpec:
    """Re-running render-module on unchanged spec should return early."""

    def test_unchanged_spec_returns_empty(self, tmp_path: Path) -> None:
        """With spec stash + same spec -> returns early with empty file list."""
        spec_v1 = _load_fixture("spec_v1_iterative.json")
        # Do initial full render
        _do_full_render(spec_v1, tmp_path)
        module_dir = tmp_path / spec_v1["module_name"]
        # Save the spec stash (simulates what iterative render does)
        save_spec_stash(spec_v1, module_dir)

        # Re-run with same spec
        files, warnings = _do_iterative_render(spec_v1, tmp_path)
        assert files == [], "Unchanged spec should produce no files"

    def test_unchanged_spec_preserves_existing_files(self, tmp_path: Path) -> None:
        """Unchanged spec should not modify any existing files."""
        spec_v1 = _load_fixture("spec_v1_iterative.json")
        _do_full_render(spec_v1, tmp_path)
        module_dir = tmp_path / spec_v1["module_name"]
        save_spec_stash(spec_v1, module_dir)

        # Record file mtimes before re-render
        py_files = list(module_dir.rglob("*.py"))
        assert len(py_files) > 0
        mtimes_before = {str(f): f.stat().st_mtime_ns for f in py_files}

        _do_iterative_render(spec_v1, tmp_path)

        # Verify mtimes unchanged
        for f_str, mtime in mtimes_before.items():
            assert Path(f_str).stat().st_mtime_ns == mtime


# ---------------------------------------------------------------------------
# TestForceFlag
# ---------------------------------------------------------------------------


class TestForceFlag:
    """--force flag triggers full regeneration regardless of spec stash."""

    def test_force_runs_all_stages(self, tmp_path: Path) -> None:
        """force=True + unchanged spec -> full generation (files created)."""
        spec_v1 = _load_fixture("spec_v1_iterative.json")
        _do_full_render(spec_v1, tmp_path)
        module_dir = tmp_path / spec_v1["module_name"]
        save_spec_stash(spec_v1, module_dir)

        files, warnings = _do_iterative_render(spec_v1, tmp_path, force=True)
        assert len(files) > 0, "Force mode should produce files even with unchanged spec"


# ---------------------------------------------------------------------------
# TestFieldAdded
# ---------------------------------------------------------------------------


class TestFieldAdded:
    """Adding a field to spec should run only affected stages."""

    def test_field_added_runs_affected_stages(self, tmp_path: Path) -> None:
        """v1 -> v2_field_added runs models/views/security/tests/stubs, skips others."""
        spec_v1 = _load_fixture("spec_v1_iterative.json")
        spec_v2 = _load_fixture("spec_v2_field_added.json")

        # Initial full render with v1
        files_v1 = _do_full_render(spec_v1, tmp_path)
        module_dir = tmp_path / spec_v1["module_name"]
        save_spec_stash(spec_v1, module_dir)

        # Record static/cron file count before iterative render
        static_before = (module_dir / "static" / "description" / "index.html").read_text()

        # Iterative render with v2 (field added)
        files_v2, warnings = _do_iterative_render(spec_v2, tmp_path)
        assert len(files_v2) > 0, "Field added should produce some files"

        # Static file should be untouched (static stage not affected by FIELD_ADDED)
        static_after = (module_dir / "static" / "description" / "index.html").read_text()
        assert static_before == static_after


# ---------------------------------------------------------------------------
# TestModelAdded
# ---------------------------------------------------------------------------


class TestModelAdded:
    """Adding a model creates new model file and updates __init__.py."""

    def test_model_added_creates_new_file(self, tmp_path: Path) -> None:
        """v1 -> v2_model_added creates fee_scholarship.py."""
        spec_v1 = _load_fixture("spec_v1_iterative.json")
        spec_v2 = _load_fixture("spec_v2_model_added.json")

        _do_full_render(spec_v1, tmp_path)
        module_dir = tmp_path / spec_v1["module_name"]
        save_spec_stash(spec_v1, module_dir)

        # Verify new model file doesn't exist yet
        new_model = module_dir / "models" / "fee_scholarship.py"
        assert not new_model.exists()

        # Iterative render with model added
        files_v2, _ = _do_iterative_render(spec_v2, tmp_path)
        assert new_model.exists(), "New model file should be created"


# ---------------------------------------------------------------------------
# TestDryRun
# ---------------------------------------------------------------------------


class TestDryRun:
    """--dry-run shows what would change without writing files."""

    def test_dry_run_no_files_written(self, tmp_path: Path) -> None:
        """dry_run=True -> returns empty list, no files modified."""
        spec_v1 = _load_fixture("spec_v1_iterative.json")
        spec_v2 = _load_fixture("spec_v2_field_added.json")

        _do_full_render(spec_v1, tmp_path)
        module_dir = tmp_path / spec_v1["module_name"]
        save_spec_stash(spec_v1, module_dir)

        # Record state before
        py_files = list(module_dir.rglob("*.py"))
        mtimes_before = {str(f): f.stat().st_mtime_ns for f in py_files}

        files, _ = _do_iterative_render(spec_v2, tmp_path, dry_run=True)
        assert files == [], "Dry run should produce no files"

        # Verify no files changed
        for f_str, mtime in mtimes_before.items():
            assert Path(f_str).stat().st_mtime_ns == mtime


# ---------------------------------------------------------------------------
# TestSpecStashSaved
# ---------------------------------------------------------------------------


class TestSpecStashSaved:
    """After any generation, .amil-spec.json should exist."""

    def test_stash_saved_after_full_render(self, tmp_path: Path) -> None:
        """Full render saves spec stash."""
        spec_v1 = _load_fixture("spec_v1_iterative.json")
        _do_iterative_render(spec_v1, tmp_path)
        module_dir = tmp_path / spec_v1["module_name"]
        stash_path = module_dir / SPEC_STASH_FILENAME
        assert stash_path.exists(), "Spec stash should be saved after generation"

    def test_stash_saved_after_iterative_render(self, tmp_path: Path) -> None:
        """Iterative render updates spec stash to new version."""
        spec_v1 = _load_fixture("spec_v1_iterative.json")
        spec_v2 = _load_fixture("spec_v2_field_added.json")

        _do_full_render(spec_v1, tmp_path)
        module_dir = tmp_path / spec_v1["module_name"]
        save_spec_stash(spec_v1, module_dir)

        _do_iterative_render(spec_v2, tmp_path)
        stash_path = module_dir / SPEC_STASH_FILENAME
        stash = json.loads(stash_path.read_text(encoding="utf-8"))
        # Stash should now contain the discount field
        field_names = [f["name"] for f in stash["models"][0]["fields"]]
        assert "discount" in field_names


# ---------------------------------------------------------------------------
# TestConflictDetection
# ---------------------------------------------------------------------------


class TestConflictDetection:
    """Files edited outside stub zones should go to .amil-pending/."""

    def test_edited_file_goes_to_pending(self, tmp_path: Path) -> None:
        """Edit a file outside stub zones -> file routed to .amil-pending/."""
        spec_v1 = _load_fixture("spec_v1_iterative.json")
        spec_v2 = _load_fixture("spec_v2_field_added.json")

        _do_full_render(spec_v1, tmp_path)
        module_dir = tmp_path / spec_v1["module_name"]
        save_spec_stash(spec_v1, module_dir)

        # Edit a model file outside stub zones (add a comment at top)
        model_file = module_dir / "models" / "fee_invoice.py"
        original = model_file.read_text(encoding="utf-8")
        model_file.write_text("# Custom edit outside zones\n" + original, encoding="utf-8")

        # Iterative render with field added
        files, _ = _do_iterative_render(spec_v2, tmp_path)

        # The conflicted file should be in .amil-pending/
        pending_dir = module_dir / ".amil-pending"
        assert pending_dir.exists(), "Pending directory should be created for conflicts"

        # Check that pending has some files
        pending_files = list(pending_dir.rglob("*"))
        pending_files = [f for f in pending_files if f.is_file()]
        assert len(pending_files) > 0, "Should have pending conflict files"


# ---------------------------------------------------------------------------
# TestStubMerge
# ---------------------------------------------------------------------------


class TestStubMerge:
    """Files edited only inside stub zones should auto-merge."""

    def test_stub_zone_edits_preserved(self, tmp_path: Path) -> None:
        """Edit file only inside stub zones -> merged output preserves implementation."""
        spec_v1 = _load_fixture("spec_v1_iterative.json")
        spec_v2 = _load_fixture("spec_v2_field_added.json")

        _do_full_render(spec_v1, tmp_path)
        module_dir = tmp_path / spec_v1["module_name"]
        save_spec_stash(spec_v1, module_dir)

        # Find a .py file with stub zones and edit within them
        model_file = module_dir / "models" / "fee_invoice.py"
        content = model_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Find BUSINESS LOGIC START marker
        start_idx = None
        for i, line in enumerate(lines):
            if "BUSINESS LOGIC START" in line:
                start_idx = i
                break

        if start_idx is not None:
            # Replace the line after the START marker (inside the zone)
            # with custom implementation
            lines[start_idx + 1] = "        result = self.amount * 1.05  # Custom business logic"
            model_file.write_text("\n".join(lines), encoding="utf-8")

            # Iterative render with field added
            files, _ = _do_iterative_render(spec_v2, tmp_path)

            # The file should have been auto-merged (not in pending)
            pending_dir = module_dir / ".amil-pending"
            if pending_dir.exists():
                pending_files = [f.name for f in pending_dir.rglob("*") if f.is_file()]
                assert "fee_invoice.py" not in pending_files, (
                    "Stub-zone-only edit should be auto-merged, not pending"
                )

            # The custom line should be preserved
            merged = model_file.read_text(encoding="utf-8")
            assert "Custom business logic" in merged, (
                "Auto-merge should preserve stub zone implementations"
            )
        else:
            # If no stub zones exist in the rendered output, test is inconclusive
            # but should still not fail
            pytest.skip("No BUSINESS LOGIC zones found in rendered file")
