"""Tests for resolve module and CLI resolve command group.

Tests that resolve_status, resolve_accept_new, resolve_keep_mine,
resolve_accept_all, and the CLI resolve subcommands work correctly
for managing pending conflict files from iterative generation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from amil_utils.iterative.resolve import (
    PENDING_DIR_NAME,
    resolve_accept_all,
    resolve_accept_new,
    resolve_keep_mine,
    resolve_status,
)
from amil_utils.manifest import (
    ArtifactEntry,
    ArtifactInfo,
    GenerationManifest,
    StageResult,
    save_manifest,
    compute_file_sha256,
)


def _create_module_with_pending(
    tmp_path: Path,
    pending_files: dict[str, str] | None = None,
    module_files: dict[str, str] | None = None,
) -> Path:
    """Create a mock module directory with optional pending and module files.

    Returns the module_dir path.
    """
    module_dir = tmp_path / "test_module"
    module_dir.mkdir(parents=True, exist_ok=True)

    # Create module files
    if module_files:
        for rel_path, content in module_files.items():
            fp = module_dir / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")

    # Create pending files
    if pending_files:
        pending_dir = module_dir / PENDING_DIR_NAME
        for rel_path, content in pending_files.items():
            fp = pending_dir / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")

    return module_dir


def _create_manifest(module_dir: Path, file_entries: dict[str, str] | None = None) -> None:
    """Create a minimal manifest with optional file entries."""
    artifact_files = []
    if file_entries:
        for path, sha in file_entries.items():
            artifact_files.append(ArtifactEntry(path=path, sha256=sha))

    manifest = GenerationManifest(
        module="test_module",
        spec_sha256="abc123",
        generated_at="2026-03-09T00:00:00Z",
        generator_version="0.1.0",
        artifacts=ArtifactInfo(files=artifact_files),
    )
    save_manifest(manifest, module_dir)


# ---------------------------------------------------------------------------
# TestResolveStatus
# ---------------------------------------------------------------------------


class TestResolveStatus:
    """resolve_status returns list of pending conflict files."""

    def test_lists_pending_files(self, tmp_path: Path) -> None:
        """Pending files listed correctly with relative paths."""
        module_dir = _create_module_with_pending(
            tmp_path,
            pending_files={
                "models/fee_invoice.py": "# new version",
                "views/fee_invoice_views.xml": "<odoo/>",
            },
        )
        result = resolve_status(module_dir)
        assert len(result) == 2
        assert "models/fee_invoice.py" in result
        assert "views/fee_invoice_views.xml" in result

    def test_empty_when_no_pending(self, tmp_path: Path) -> None:
        """Returns empty list when no .amil-pending/ exists."""
        module_dir = _create_module_with_pending(tmp_path)
        result = resolve_status(module_dir)
        assert result == []

    def test_empty_when_pending_dir_empty(self, tmp_path: Path) -> None:
        """Returns empty list when .amil-pending/ exists but is empty."""
        module_dir = _create_module_with_pending(tmp_path)
        (module_dir / PENDING_DIR_NAME).mkdir(parents=True, exist_ok=True)
        result = resolve_status(module_dir)
        assert result == []


# ---------------------------------------------------------------------------
# TestAcceptNew
# ---------------------------------------------------------------------------


class TestAcceptNew:
    """resolve_accept_new copies pending file to module dir."""

    def test_copies_to_module_dir(self, tmp_path: Path) -> None:
        """Pending file copied to module dir, removed from pending."""
        module_dir = _create_module_with_pending(
            tmp_path,
            pending_files={"models/fee_invoice.py": "# new version"},
            module_files={"models/fee_invoice.py": "# old version"},
        )
        # Create manifest with old hash
        old_hash = compute_file_sha256(module_dir / "models/fee_invoice.py")
        _create_manifest(module_dir, {"models/fee_invoice.py": old_hash})

        result = resolve_accept_new(module_dir, "models/fee_invoice.py")
        assert result is True

        # File should now have new content
        content = (module_dir / "models/fee_invoice.py").read_text()
        assert content == "# new version"

        # Pending file should be gone
        pending_file = module_dir / PENDING_DIR_NAME / "models/fee_invoice.py"
        assert not pending_file.exists()

    def test_returns_false_when_not_found(self, tmp_path: Path) -> None:
        """Returns False when pending file doesn't exist."""
        module_dir = _create_module_with_pending(tmp_path)
        result = resolve_accept_new(module_dir, "nonexistent.py")
        assert result is False

    def test_updates_manifest_hash(self, tmp_path: Path) -> None:
        """Manifest artifact hash is updated after accept."""
        module_dir = _create_module_with_pending(
            tmp_path,
            pending_files={"models/fee_invoice.py": "# new version"},
            module_files={"models/fee_invoice.py": "# old version"},
        )
        old_hash = compute_file_sha256(module_dir / "models/fee_invoice.py")
        _create_manifest(module_dir, {"models/fee_invoice.py": old_hash})

        resolve_accept_new(module_dir, "models/fee_invoice.py")

        # Load manifest and check updated hash
        from amil_utils.manifest import load_manifest
        updated_manifest = load_manifest(module_dir)
        assert updated_manifest is not None
        new_hash = compute_file_sha256(module_dir / "models/fee_invoice.py")
        entry = next(
            (e for e in updated_manifest.artifacts.files if e.path == "models/fee_invoice.py"),
            None,
        )
        assert entry is not None
        assert entry.sha256 == new_hash


# ---------------------------------------------------------------------------
# TestAcceptAll
# ---------------------------------------------------------------------------


class TestAcceptAll:
    """resolve_accept_all resolves all pending files."""

    def test_resolves_all_pending(self, tmp_path: Path) -> None:
        """All pending files resolved, count returned."""
        module_dir = _create_module_with_pending(
            tmp_path,
            pending_files={
                "models/fee_invoice.py": "# new invoice",
                "models/fee_scholarship.py": "# new scholarship",
            },
            module_files={
                "models/fee_invoice.py": "# old invoice",
                "models/fee_scholarship.py": "# old scholarship",
            },
        )
        _create_manifest(module_dir, {
            "models/fee_invoice.py": "aaa",
            "models/fee_scholarship.py": "bbb",
        })

        count = resolve_accept_all(module_dir)
        assert count == 2

        # Both files should have new content
        assert (module_dir / "models/fee_invoice.py").read_text() == "# new invoice"
        assert (module_dir / "models/fee_scholarship.py").read_text() == "# new scholarship"

    def test_returns_zero_when_no_pending(self, tmp_path: Path) -> None:
        """Returns 0 when no pending files exist."""
        module_dir = _create_module_with_pending(tmp_path)
        count = resolve_accept_all(module_dir)
        assert count == 0


# ---------------------------------------------------------------------------
# TestKeepMine
# ---------------------------------------------------------------------------


class TestKeepMine:
    """resolve_keep_mine removes pending file, keeps module file."""

    def test_removes_pending_keeps_module(self, tmp_path: Path) -> None:
        """Pending file removed, module file unchanged."""
        module_dir = _create_module_with_pending(
            tmp_path,
            pending_files={"models/fee_invoice.py": "# new version"},
            module_files={"models/fee_invoice.py": "# my version"},
        )

        result = resolve_keep_mine(module_dir, "models/fee_invoice.py")
        assert result is True

        # Module file should be unchanged
        content = (module_dir / "models/fee_invoice.py").read_text()
        assert content == "# my version"

        # Pending file should be gone
        assert not (module_dir / PENDING_DIR_NAME / "models/fee_invoice.py").exists()

    def test_returns_false_when_not_found(self, tmp_path: Path) -> None:
        """Returns False when pending file doesn't exist."""
        module_dir = _create_module_with_pending(tmp_path)
        result = resolve_keep_mine(module_dir, "nonexistent.py")
        assert result is False


# ---------------------------------------------------------------------------
# TestCleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    """Pending directory cleaned up when empty after resolution."""

    def test_pending_removed_when_empty(self, tmp_path: Path) -> None:
        """.amil-pending/ removed when empty after resolution."""
        module_dir = _create_module_with_pending(
            tmp_path,
            pending_files={"models/fee_invoice.py": "# new version"},
            module_files={"models/fee_invoice.py": "# old version"},
        )
        _create_manifest(module_dir, {"models/fee_invoice.py": "aaa"})

        resolve_accept_new(module_dir, "models/fee_invoice.py")

        pending_dir = module_dir / PENDING_DIR_NAME
        assert not pending_dir.exists(), "Empty pending dir should be removed"


# ---------------------------------------------------------------------------
# TestRemovedFiles
# ---------------------------------------------------------------------------


class TestRemovedFiles:
    """Removed file workflow handles both accept (delete) and keep (preserve)."""

    def test_accept_removed_deletes_module_file(self, tmp_path: Path) -> None:
        """accept-new on removed/ subdir confirms deletion."""
        module_dir = _create_module_with_pending(
            tmp_path,
            pending_files={"removed/models/old_model.py": "# marked for removal"},
            module_files={"models/old_model.py": "# existing model"},
        )
        _create_manifest(module_dir, {"models/old_model.py": "aaa"})

        result = resolve_accept_new(module_dir, "removed/models/old_model.py")
        assert result is True

        # Module file should be deleted
        assert not (module_dir / "models/old_model.py").exists()

    def test_keep_removed_preserves_module_file(self, tmp_path: Path) -> None:
        """keep-mine on removed/ subdir keeps the file in module_dir."""
        module_dir = _create_module_with_pending(
            tmp_path,
            pending_files={"removed/models/old_model.py": "# marked for removal"},
            module_files={"models/old_model.py": "# keep this"},
        )

        result = resolve_keep_mine(module_dir, "removed/models/old_model.py")
        assert result is True

        # Module file should still exist
        content = (module_dir / "models/old_model.py").read_text()
        assert content == "# keep this"


# ---------------------------------------------------------------------------
# TestCLIResolveStatus
# ---------------------------------------------------------------------------


class TestCLIResolveStatus:
    """CLI resolve status command shows pending files."""

    def test_status_output(self, tmp_path: Path) -> None:
        """resolve status shows pending files."""
        from amil_utils.cli import main

        module_dir = _create_module_with_pending(
            tmp_path,
            pending_files={"models/fee_invoice.py": "# new version"},
        )

        runner = CliRunner()
        result = runner.invoke(main, ["resolve", "status", "--module-dir", str(module_dir)])
        assert result.exit_code == 0
        assert "fee_invoice.py" in result.output

    def test_status_no_pending(self, tmp_path: Path) -> None:
        """resolve status shows 'No pending conflicts' when empty."""
        from amil_utils.cli import main

        module_dir = _create_module_with_pending(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["resolve", "status", "--module-dir", str(module_dir)])
        assert result.exit_code == 0
        assert "No pending conflicts" in result.output


# ---------------------------------------------------------------------------
# TestCLIResolveAcceptAll
# ---------------------------------------------------------------------------


class TestCLIResolveAcceptAll:
    """CLI resolve accept-all command resolves all pending files."""

    def test_accept_all_via_cli(self, tmp_path: Path) -> None:
        """resolve accept-all resolves all pending files."""
        from amil_utils.cli import main

        module_dir = _create_module_with_pending(
            tmp_path,
            pending_files={"models/fee_invoice.py": "# new version"},
            module_files={"models/fee_invoice.py": "# old version"},
        )
        _create_manifest(module_dir, {"models/fee_invoice.py": "aaa"})

        runner = CliRunner()
        result = runner.invoke(main, ["resolve", "accept-all", "--module-dir", str(module_dir)])
        assert result.exit_code == 0
        assert "1" in result.output or "Resolved" in result.output

        # File should have new content
        content = (module_dir / "models/fee_invoice.py").read_text()
        assert content == "# new version"
