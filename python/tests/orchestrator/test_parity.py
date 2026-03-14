"""Parity tests: verify Python CLI produces same JSON as CJS CLI.

Runs each command through both `node amil-tools.cjs` and `amil-utils orch`,
then compares the JSON output. Skips if Node.js is not available.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from amil_utils.orchestrator.cli import orch_group

# ─── Helpers ───────────────────────────────────────────────────────

_NODE = shutil.which("node")
_REPO_ROOT = Path(__file__).resolve().parents[4]  # pipeline/python/tests/orch -> repo root
_CJS_PATH = _REPO_ROOT / "orchestrator" / "amil" / "bin" / "amil-tools.cjs"

_SKIP = not (_NODE and _CJS_PATH.exists())
_REASON = "Node.js or amil-tools.cjs not available"

# Fields that legitimately differ between runs (timestamps, etc.)
_VOLATILE_KEYS = frozenset({
    "timestamp", "date", "last_activity", "session_start",
    "current_date", "state_raw",
})


def _run_cjs(args: list[str], cwd: str) -> dict:
    """Run a CJS command and return parsed JSON."""
    cmd = [_NODE, str(_CJS_PATH)] + args + ["--cwd", cwd]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        pytest.skip(f"CJS command failed: {result.stderr.strip()}")
    raw = result.stdout.strip()
    if raw.startswith("@file:"):
        raw = Path(raw[6:]).read_text(encoding="utf-8")
    return json.loads(raw)


def _run_py(args: list[str], cwd: str) -> dict:
    """Run a Python CLI command and return parsed JSON."""
    runner = CliRunner()
    result = runner.invoke(orch_group, args + ["--cwd", cwd])
    assert result.exit_code == 0, f"Python CLI failed: {result.output}"
    return json.loads(result.output)


def _normalize(data: object, *, drop_volatile: bool = True) -> object:
    """Recursively normalize JSON for comparison.

    - Drop volatile keys (timestamps that differ between runs)
    - Sort dict keys
    - Normalize Path separators
    """
    if isinstance(data, dict):
        return {
            k: _normalize(v, drop_volatile=drop_volatile)
            for k, v in sorted(data.items())
            if not (drop_volatile and k in _VOLATILE_KEYS)
        }
    if isinstance(data, list):
        return [_normalize(item, drop_volatile=drop_volatile) for item in data]
    if isinstance(data, str):
        # Normalize path separators
        return data.replace("\\", "/")
    return data


def _assert_parity(cjs_data: dict, py_data: dict, label: str) -> None:
    """Assert Python output is a superset of CJS output.

    The Python port intentionally enriches responses with extra fields
    (e.g., has_context, phase_slug). We verify that every CJS key exists
    in the Python output with a matching value, but allow extra keys.
    """
    cjs_norm = _normalize(cjs_data)
    py_norm = _normalize(py_data)
    _assert_superset(cjs_norm, py_norm, label, path="$")


def _assert_superset(cjs: object, py: object, label: str, path: str) -> None:
    """Recursively check that py is a superset of cjs."""
    if isinstance(cjs, dict) and isinstance(py, dict):
        for key in cjs:
            assert key in py, (
                f"Parity mismatch for {label} at {path}.{key}: "
                f"key present in CJS but missing in Python"
            )
            _assert_superset(cjs[key], py[key], label, f"{path}.{key}")
    elif isinstance(cjs, list) and isinstance(py, list):
        assert len(cjs) == len(py), (
            f"Parity mismatch for {label} at {path}: "
            f"list lengths differ (CJS={len(cjs)}, PY={len(py)})"
        )
        for i, (c, p) in enumerate(zip(cjs, py)):
            _assert_superset(c, p, label, f"{path}[{i}]")
    else:
        assert cjs == py, (
            f"Parity mismatch for {label} at {path}: "
            f"CJS={cjs!r} != PY={py!r}"
        )


# ─── Fixtures ──────────────────────────────────────────────────────


def _make_parity_project(tmp_path: Path) -> Path:
    """Create a .planning directory identical for CJS and Python tests."""
    planning = tmp_path / ".planning"
    planning.mkdir()
    phases = planning / "phases"
    phases.mkdir()

    (planning / "config.json").write_text(json.dumps({
        "model_profile": "balanced",
        "commit_docs": True,
        "parallelization": True,
        "branching_strategy": "phase",
        "phase_branch_template": "phase-{phase}-{slug}",
        "milestone_branch_template": "milestone-{milestone}-{slug}",
        "verifier": True,
        "research": True,
        "plan_checker": True,
        "nyquist_validation": True,
        "brave_search": False,
        "search_gitignored": False,
    }, indent=2))

    phase1 = phases / "01-setup"
    phase1.mkdir()
    (phase1 / "01-01-PLAN.md").write_text(
        "---\nphase: 1\nplan: 01\nwave: 1\nautonomous: true\n"
        "depends_on: []\nfiles_modified: []\nmust_haves:\n---\n"
        "# Plan\n<objective>\nSetup\n</objective>\n<task>\n## Task 1\nDo it\n</task>\n"
    )
    (phase1 / "01-01-SUMMARY.md").write_text(
        "---\none-liner: Set up project structure\nphase: 1\nplan: 01\n"
        "key-decisions:\n  - Use Python: Better ecosystem\n"
        "patterns-established:\n  - Repository pattern\n"
        "tech-stack:\n  added:\n    - Python 3.12\n---\n"
        "# Summary\n## Task 1\nDone\n"
    )

    phase2 = phases / "02-core"
    phase2.mkdir()
    (phase2 / "02-01-PLAN.md").write_text(
        "---\nphase: 2\nplan: 01\n---\n# Plan\n## Task 1\n## Task 2\n"
    )

    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## v1.0: First Release\n\n"
        "### Phase 1: Setup\n\n**Goal:** Project setup\n"
        "**Requirements**: REQ-01\n"
        "**Plans:** 1 plans\n\n"
        "### Phase 2: Core\n\n**Goal:** Core module\n"
        "**Requirements**: REQ-02, REQ-03\n"
        "**Plans:** 1 plans\n"
    )
    (planning / "STATE.md").write_text(
        "# Session State\n\n"
        "**Milestone:** v1.0\n"
        "**Status:** Executing\n"
        "**Last Activity:** 2026-03-13\n"
    )
    (planning / "REQUIREMENTS.md").write_text(
        "# Requirements\n\n"
        "- [ ] **REQ-01** Setup requirement\n"
        "- [ ] **REQ-02** Core requirement A\n\n"
        "## Traceability\n\n"
        "| Requirement | Phase | Status |\n"
        "|---|---|---|\n"
        "| REQ-01 | Phase 1 | Pending |\n"
        "| REQ-02 | Phase 2 | Pending |\n"
    )
    (planning / "PROJECT.md").write_text("# Project\n\nTest project.\n")

    return planning


@pytest.fixture()
def parity_project(tmp_path: Path) -> Path:
    _make_parity_project(tmp_path)
    return tmp_path


# ─── Stateless commands (no --cwd needed) ──────────────────────────


@pytest.mark.skipif(_SKIP, reason=_REASON)
class TestStatelessParity:
    def test_generate_slug(self) -> None:
        cjs = _run_cjs(["generate-slug", "Hello World"], ".")
        py = _run_py(["generate-slug", "Hello World"], ".")
        _assert_parity(cjs, py, "generate-slug")

    def test_generate_slug_special_chars(self) -> None:
        cjs = _run_cjs(["generate-slug", "My Project!! (v2.0)"], ".")
        py = _run_py(["generate-slug", "My Project!! (v2.0)"], ".")
        _assert_parity(cjs, py, "generate-slug-special")

    def test_current_timestamp_date(self) -> None:
        cjs = _run_cjs(["current-timestamp", "date"], ".")
        py = _run_py(["current-timestamp", "date"], ".")
        # Both return a date string; just verify the format matches
        assert "timestamp" in cjs
        assert "timestamp" in py
        # Date format should be YYYY-MM-DD in both
        assert len(cjs["timestamp"]) == 10
        assert len(py["timestamp"]) == 10


# ─── State commands ────────────────────────────────────────────────


@pytest.mark.skipif(_SKIP, reason=_REASON)
class TestStateParity:
    def test_state_load(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["state", "load"], cwd)
        py = _run_py(["state", "load"], cwd)
        _assert_parity(cjs, py, "state-load")

    def test_state_get(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["state", "get"], cwd)
        py = _run_py(["state", "get"], cwd)
        _assert_parity(cjs, py, "state-get")

    def test_state_snapshot(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["state-snapshot"], cwd)
        py = _run_py(["state", "snapshot"], cwd)
        _assert_parity(cjs, py, "state-snapshot")


# ─── Phase commands ────────────────────────────────────────────────


@pytest.mark.skipif(_SKIP, reason=_REASON)
class TestPhaseParity:
    def test_find_phase(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["find-phase", "1"], cwd)
        py = _run_py(["find-phase", "1"], cwd)
        _assert_parity(cjs, py, "find-phase")

    def test_find_phase_missing(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["find-phase", "99"], cwd)
        py = _run_py(["find-phase", "99"], cwd)
        _assert_parity(cjs, py, "find-phase-missing")

    def test_phase_plan_index(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["phase-plan-index", "1"], cwd)
        py = _run_py(["phase-plan-index", "1"], cwd)
        _assert_parity(cjs, py, "phase-plan-index")

    def test_phase_next_decimal(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["phase", "next-decimal", "01"], cwd)
        py = _run_py(["phase", "next-decimal", "01"], cwd)
        _assert_parity(cjs, py, "phase-next-decimal")

    def test_phases_list(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["phases", "list"], cwd)
        py = _run_py(["phases", "list"], cwd)
        _assert_parity(cjs, py, "phases-list")


# ─── Utility commands ─────────────────────────────────────────────


@pytest.mark.skipif(_SKIP, reason=_REASON)
class TestUtilityParity:
    def test_verify_path_exists(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["verify-path-exists", ".planning"], cwd)
        py = _run_py(["verify-path-exists", ".planning"], cwd)
        _assert_parity(cjs, py, "verify-path-exists")

    def test_verify_path_missing(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["verify-path-exists", "nope.txt"], cwd)
        py = _run_py(["verify-path-exists", "nope.txt"], cwd)
        _assert_parity(cjs, py, "verify-path-missing")

    def test_list_todos(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["list-todos"], cwd)
        py = _run_py(["list-todos"], cwd)
        _assert_parity(cjs, py, "list-todos")

    def test_resolve_model(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["resolve-model", "amil-executor"], cwd)
        py = _run_py(["resolve-model", "amil-executor"], cwd)
        _assert_parity(cjs, py, "resolve-model")

    def test_history_digest(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["history-digest"], cwd)
        py = _run_py(["history-digest"], cwd)
        _assert_parity(cjs, py, "history-digest")

    def test_config_ensure_section(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        # Both should report already_exists since config.json exists
        cjs = _run_cjs(["config-ensure-section"], cwd)
        py = _run_py(["config-ensure-section"], cwd)
        _assert_parity(cjs, py, "config-ensure-section")


# ─── Roadmap commands ──────────────────────────────────────────────


@pytest.mark.skipif(_SKIP, reason=_REASON)
class TestRoadmapParity:
    def test_roadmap_get_phase(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["roadmap", "get-phase", "1"], cwd)
        py = _run_py(["roadmap", "get-phase", "1"], cwd)
        _assert_parity(cjs, py, "roadmap-get-phase")

    def test_roadmap_analyze(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["roadmap", "analyze"], cwd)
        py = _run_py(["roadmap", "analyze"], cwd)
        _assert_parity(cjs, py, "roadmap-analyze")


# ─── Progress commands ─────────────────────────────────────────────


@pytest.mark.skipif(_SKIP, reason=_REASON)
class TestProgressParity:
    def test_progress_json(self, parity_project: Path) -> None:
        cwd = str(parity_project)
        cjs = _run_cjs(["progress", "json"], cwd)
        py = _run_py(["progress", "json"], cwd)
        _assert_parity(cjs, py, "progress-json")
