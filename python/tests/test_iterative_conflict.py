"""Tests for iterative three-way conflict detection (conflict.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amil_utils.iterative.conflict import (
    ConflictResult,
    detect_conflicts,
)
from amil_utils.manifest import (
    ArtifactEntry,
    ArtifactInfo,
    GenerationManifest,
    compute_file_sha256,
)


def _make_manifest(artifacts: list[ArtifactEntry]) -> GenerationManifest:
    """Create a minimal manifest for testing."""
    return GenerationManifest(
        module="test_module",
        spec_sha256="abc123",
        generated_at="2026-01-01T00:00:00Z",
        generator_version="0.1.0",
        artifacts=ArtifactInfo(
            files=artifacts,
            total_files=len(artifacts),
            total_lines=0,
        ),
    )


def _write_file(path: Path, content: str) -> str:
    """Write content to file and return its sha256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return compute_file_sha256(path)


# ---------------------------------------------------------------------------
# ConflictResult dataclass
# ---------------------------------------------------------------------------


class TestConflictResultDataclass:
    """ConflictResult is a frozen dataclass."""

    def test_frozen(self) -> None:
        result = ConflictResult(
            safe_to_overwrite=("a.py",),
            conflicts=(),
            stub_mergeable=(),
        )
        with pytest.raises(AttributeError):
            result.safe_to_overwrite = ("b.py",)  # type: ignore[misc]

    def test_tuple_fields(self) -> None:
        result = ConflictResult(
            safe_to_overwrite=("a.py",),
            conflicts=("b.py",),
            stub_mergeable=("c.py",),
        )
        assert isinstance(result.safe_to_overwrite, tuple)
        assert isinstance(result.conflicts, tuple)
        assert isinstance(result.stub_mergeable, tuple)


# ---------------------------------------------------------------------------
# detect_conflicts tests
# ---------------------------------------------------------------------------


class TestSafeOverwrite:
    """File hash matches manifest -> safe_to_overwrite."""

    def test_file_unchanged_since_generation(self, tmp_path: Path) -> None:
        module_dir = tmp_path / "module"
        content = "# Original generated file\nclass FeeInvoice:\n    pass\n"
        sha = _write_file(module_dir / "models" / "fee_invoice.py", content)

        manifest = _make_manifest([
            ArtifactEntry(path="models/fee_invoice.py", sha256=sha),
        ])

        result = detect_conflicts(
            manifest=manifest,
            affected_files=["models/fee_invoice.py"],
            module_dir=module_dir,
        )
        assert "models/fee_invoice.py" in result.safe_to_overwrite
        assert len(result.conflicts) == 0
        assert len(result.stub_mergeable) == 0


class TestConflict:
    """File hash differs, edits outside stub zones -> conflicts."""

    def test_file_edited_outside_stubs(self, tmp_path: Path) -> None:
        module_dir = tmp_path / "module"
        original = "# Original file\nclass FeeInvoice:\n    pass\n"
        sha = _write_file(module_dir / "models" / "fee_invoice.py", original)

        manifest = _make_manifest([
            ArtifactEntry(path="models/fee_invoice.py", sha256=sha),
        ])

        # User edits the file OUTSIDE stub zones
        edited = "# Modified by user\nclass FeeInvoice:\n    custom_field = True\n"
        (module_dir / "models" / "fee_invoice.py").write_text(edited, encoding="utf-8")

        result = detect_conflicts(
            manifest=manifest,
            affected_files=["models/fee_invoice.py"],
            module_dir=module_dir,
        )
        assert "models/fee_invoice.py" in result.conflicts


class TestStubMergeable:
    """File hash differs, edits only inside stub zones -> stub_mergeable."""

    def test_file_edited_only_in_stubs(self, tmp_path: Path) -> None:
        module_dir = tmp_path / "module"
        skeleton_dir = tmp_path / "skeleton"

        # Original skeleton with stub zones
        skeleton_content = (
            "class FeeInvoice:\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        pass\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        skeleton_sha = _write_file(skeleton_dir / "models" / "fee_invoice.py", skeleton_content)

        # Manifest records the skeleton hash
        manifest = _make_manifest([
            ArtifactEntry(path="models/fee_invoice.py", sha256=skeleton_sha),
        ])

        # User edits ONLY inside stub zones
        edited_content = (
            "class FeeInvoice:\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        for rec in self:\n"
            "            rec.total = rec.amount * rec.qty\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        _write_file(module_dir / "models" / "fee_invoice.py", edited_content)

        result = detect_conflicts(
            manifest=manifest,
            affected_files=["models/fee_invoice.py"],
            module_dir=module_dir,
            skeleton_dir=skeleton_dir,
        )
        assert "models/fee_invoice.py" in result.stub_mergeable


class TestMissingFile:
    """File deleted by user -> not in any conflict list (will be recreated)."""

    def test_file_does_not_exist(self, tmp_path: Path) -> None:
        module_dir = tmp_path / "module"
        module_dir.mkdir()

        manifest = _make_manifest([
            ArtifactEntry(path="models/fee_invoice.py", sha256="deadbeef"),
        ])

        result = detect_conflicts(
            manifest=manifest,
            affected_files=["models/fee_invoice.py"],
            module_dir=module_dir,
        )
        # File doesn't exist -> safe to create fresh
        assert "models/fee_invoice.py" in result.safe_to_overwrite


class TestNotInManifest:
    """New file not tracked in manifest -> safe_to_overwrite."""

    def test_new_file_not_in_manifest(self, tmp_path: Path) -> None:
        module_dir = tmp_path / "module"
        module_dir.mkdir()

        manifest = _make_manifest([])  # Empty manifest

        result = detect_conflicts(
            manifest=manifest,
            affected_files=["models/new_model.py"],
            module_dir=module_dir,
        )
        assert "models/new_model.py" in result.safe_to_overwrite


class TestMultipleFiles:
    """Multiple files with mixed results."""

    def test_mixed_conflict_results(self, tmp_path: Path) -> None:
        module_dir = tmp_path / "module"

        # File 1: unchanged (safe)
        content1 = "# file 1\n"
        sha1 = _write_file(module_dir / "models" / "a.py", content1)

        # File 2: edited (conflict)
        content2 = "# file 2\n"
        sha2 = _write_file(module_dir / "models" / "b.py", content2)
        (module_dir / "models" / "b.py").write_text("# edited\n", encoding="utf-8")

        manifest = _make_manifest([
            ArtifactEntry(path="models/a.py", sha256=sha1),
            ArtifactEntry(path="models/b.py", sha256=sha2),
        ])

        result = detect_conflicts(
            manifest=manifest,
            affected_files=["models/a.py", "models/b.py"],
            module_dir=module_dir,
        )
        assert "models/a.py" in result.safe_to_overwrite
        assert "models/b.py" in result.conflicts
