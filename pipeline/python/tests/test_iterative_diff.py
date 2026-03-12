"""Tests for iterative spec stash save/load and diff orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amil_utils.iterative.diff import (
    SPEC_STASH_FILENAME,
    compute_spec_diff,
    load_spec_stash,
    save_spec_stash,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Spec stash tests
# ---------------------------------------------------------------------------


class TestSpecStash:
    """Tests for save_spec_stash / load_spec_stash round-trip."""

    def test_load_returns_none_when_no_stash(self, tmp_path: Path) -> None:
        result = load_spec_stash(tmp_path)
        assert result is None

    def test_round_trip_save_load(self, tmp_path: Path) -> None:
        spec = _load_fixture("spec_v1_iterative.json")
        save_spec_stash(spec, tmp_path)
        loaded = load_spec_stash(tmp_path)
        assert loaded == spec

    def test_canonical_json_format(self, tmp_path: Path) -> None:
        spec = {"z_key": 1, "a_key": 2, "m_key": 3}
        save_spec_stash(spec, tmp_path)
        raw = (tmp_path / SPEC_STASH_FILENAME).read_text(encoding="utf-8")
        # Sorted keys: a_key before m_key before z_key
        lines = raw.strip().splitlines()
        key_lines = [l.strip().strip('"').split('"')[0] for l in lines if '"' in l and ":" in l]
        assert key_lines == ["a_key", "m_key", "z_key"]

    def test_stash_file_ends_with_newline(self, tmp_path: Path) -> None:
        spec = {"key": "value"}
        save_spec_stash(spec, tmp_path)
        raw = (tmp_path / SPEC_STASH_FILENAME).read_text(encoding="utf-8")
        assert raw.endswith("\n")

    def test_stash_path_returned(self, tmp_path: Path) -> None:
        spec = {"key": "value"}
        result = save_spec_stash(spec, tmp_path)
        assert result == tmp_path / SPEC_STASH_FILENAME
        assert result.exists()


# ---------------------------------------------------------------------------
# Spec diff tests
# ---------------------------------------------------------------------------


class TestComputeSpecDiff:
    """Tests for compute_spec_diff orchestration."""

    def test_returns_none_for_identical_specs(self) -> None:
        spec = _load_fixture("spec_v1_iterative.json")
        result = compute_spec_diff(spec, spec)
        assert result is None

    def test_returns_spec_diff_for_different_specs(self) -> None:
        old = _load_fixture("spec_v1_iterative.json")
        new = _load_fixture("spec_v2_field_added.json")
        result = compute_spec_diff(old, new)
        assert result is not None
        assert "changes" in result
        assert "models" in result["changes"]


class TestFieldAdded:
    """Test diff detection when a field is added."""

    def test_field_added_detected(self) -> None:
        old = _load_fixture("spec_v1_iterative.json")
        new = _load_fixture("spec_v2_field_added.json")
        result = compute_spec_diff(old, new)
        assert result is not None
        models = result["changes"]["models"]
        # fee.invoice should be modified with an added field
        modified = models.get("modified", {})
        assert "fee.invoice" in modified
        fields = modified["fee.invoice"].get("fields", {})
        added_names = [f["name"] for f in fields.get("added", [])]
        assert "discount" in added_names


class TestModelAdded:
    """Test diff detection when a model is added."""

    def test_model_added_detected(self) -> None:
        old = _load_fixture("spec_v1_iterative.json")
        new = _load_fixture("spec_v2_model_added.json")
        result = compute_spec_diff(old, new)
        assert result is not None
        models = result["changes"]["models"]
        added_names = [m["name"] for m in models.get("added", [])]
        assert "fee.scholarship" in added_names


class TestForceFlag:
    """Placeholder tests for --force semantics (CLI-level, Plan 02)."""

    def test_placeholder_force_flag(self) -> None:
        # Force semantics bypass the sha256 check at the CLI level.
        # The compute_spec_diff function itself always returns None for identical specs.
        # This is tested at the CLI integration level in Plan 02.
        pass


class TestDryRun:
    """Placeholder tests for --dry-run semantics (CLI-level, Plan 02)."""

    def test_placeholder_dry_run(self) -> None:
        # Dry-run display is a CLI concern.
        # compute_spec_diff provides the data; formatting is in Plan 02.
        pass
