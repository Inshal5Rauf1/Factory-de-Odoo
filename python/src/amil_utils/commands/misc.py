"""Business logic for smaller CLI commands that don't warrant their own module.

Pure Python -- no Click dependency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# show-state
# ---------------------------------------------------------------------------

def execute_show_state(module_path: str) -> dict[str, Any]:
    """Show artifact generation state for a module.

    Returns:
        - manifest_data: dict | None -- model_dump of manifest
        - text: str -- human-readable output
        - legacy: bool -- True if legacy state file found
        - found: bool -- True if any state found
    """
    from amil_utils.manifest import load_manifest

    mp = Path(module_path).resolve()
    m = load_manifest(mp)

    if m is not None:
        lines = [
            f"Module: {m.module}",
            f"Generated: {m.generated_at}",
            f"Odoo: {m.odoo_version}",
            f"Spec SHA: {m.spec_sha256[:12]}...",
            f"Files: {m.artifacts.total_files} ({m.artifacts.total_lines} lines)",
            "",
            "Stages:",
        ]
        for name, stage in m.stages.items():
            icon = {"complete": "[OK]", "skipped": "[--]", "failed": "[!!]", "pending": "[..]"}.get(stage.status, "[??]")
            dur = f" ({stage.duration_ms}ms)" if stage.duration_ms else ""
            lines.append(f"  {icon} {name}{dur}")
            if stage.error:
                lines.append(f"       ERROR: {stage.error}")
        if m.preprocessing.preprocessors_run:
            lines.append(f"\nPreprocessors: {len(m.preprocessing.preprocessors_run)} ran ({m.preprocessing.duration_ms}ms)")
        if m.models_registered:
            lines.append(f"Models: {', '.join(m.models_registered)}")
        return {
            "manifest_data": m.model_dump(exclude_none=True),
            "text": "\n".join(lines),
            "legacy": False,
            "found": True,
        }

    if (mp / ".amil-state.json").exists():
        return {
            "manifest_data": None,
            "text": "Legacy state file found. Re-generate for manifest tracking.",
            "legacy": True,
            "found": True,
        }

    return {
        "manifest_data": None,
        "text": "No manifest found. Module has not been tracked.",
        "legacy": False,
        "found": False,
    }


# ---------------------------------------------------------------------------
# diff-spec
# ---------------------------------------------------------------------------

def execute_diff_spec(old_spec: str, new_spec: str) -> dict[str, Any]:
    """Compare two spec versions.

    Returns:
        - result: dict -- the diff result
        - human_summary: str
        - error: str | None
    """
    from amil_utils.spec_differ import diff_specs, format_human_summary

    try:
        od = json.loads(Path(old_spec).read_text(encoding="utf-8"))
        nd = json.loads(Path(new_spec).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"result": {}, "human_summary": "", "error": str(exc)}

    r = diff_specs(od, nd)
    return {"result": r, "human_summary": format_human_summary(r), "error": None}


# ---------------------------------------------------------------------------
# gen-migration
# ---------------------------------------------------------------------------

def execute_gen_migration(old_spec: str, new_spec: str, migration_version: str, output_dir: str) -> dict[str, Any]:
    """Generate migration scripts.

    Returns:
        - migration_dir: str
        - migration_required: bool
        - destructive_count: int
        - error: str | None
    """
    from amil_utils.migration_generator import generate_migration
    from amil_utils.spec_differ import diff_specs

    try:
        od = json.loads(Path(old_spec).read_text(encoding="utf-8"))
        nd = json.loads(Path(new_spec).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"migration_dir": "", "migration_required": False, "destructive_count": 0, "error": str(exc)}

    diff = diff_specs(od, nd)
    if not diff["migration_required"]:
        return {"migration_dir": "", "migration_required": False, "destructive_count": 0, "error": None}

    generate_migration(diff, migration_version, output_dir=output_dir)
    md = str(Path(output_dir) / "migrations" / migration_version)
    return {
        "migration_dir": md,
        "migration_required": True,
        "destructive_count": diff.get("destructive_count", 0),
        "error": None,
    }


# ---------------------------------------------------------------------------
# validate-kb
# ---------------------------------------------------------------------------

def execute_validate_kb(scope: str) -> dict[str, Any]:
    """Validate knowledge base rule files.

    Returns:
        - output_lines: list[str]
        - has_errors: bool
        - error: str | None -- if KB not found
    """
    from amil_utils.kb_validator import validate_kb_directory

    kb: Path | None = None
    for p in (Path.home() / ".claude" / "amil" / "knowledge", Path.cwd() / "knowledge"):
        if p.is_dir():
            kb = p
            break
    if kb is None:
        return {"output_lines": [], "has_errors": False, "error": "Knowledge base not found."}

    lines: list[str] = []
    has_errors = False

    if scope == "all":
        lines.append(f"Validating shipped rules: {kb}/")
        sr = validate_kb_directory(kb)
        for fn, res in sr.get("files", {}).items():
            _kb_lines(fn, res, lines)
        if sr["files"]:
            s = sr["summary"]
            lines.append(f"  {s['valid']} valid, {s['invalid']} invalid, {s['warnings']} warnings")
            if not sr["valid"]:
                has_errors = True
        lines.append("")

    cp = kb / "custom"
    lines.append(f"Validating custom rules: {cp}/")
    if not cp.is_dir():
        lines.append("  No custom/ directory.")
    else:
        cr = validate_kb_directory(cp)
        for fn, res in cr.get("files", {}).items():
            _kb_lines(fn, res, lines)
        if cr["files"]:
            s = cr["summary"]
            lines.append(f"  {s['valid']} valid, {s['invalid']} invalid, {s['warnings']} warnings")
            if not cr["valid"]:
                has_errors = True
        else:
            lines.append("  No custom .md files found.")

    return {"output_lines": lines, "has_errors": has_errors, "error": None}


def _kb_lines(fn: str, r: dict, lines: list[str]) -> None:
    lines.append(f"  [{'+'if r['valid'] else 'x'}] {fn}: {'VALID'if r['valid'] else 'INVALID'}")
    for e in r["errors"]:
        lines.append(f"      ERROR: {e}")
    for w in r["warnings"]:
        lines.append(f"      WARN:  {w}")
