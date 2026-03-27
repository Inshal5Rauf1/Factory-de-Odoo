"""Cycle Log — Append-only markdown log tracking every action in an ERP generation cycle.

Ported from orchestrator/amil/bin/lib/cycle-log.cjs (157 lines, since deleted).
Each entry is timestamped and includes module name, action, result, and error details.
The compact summary header at the top is rewritten after each iteration so Claude can
resume from the header alone without reading the full log.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

LOG_FILENAME = "ERP_CYCLE_LOG.md"

_COMPACT_SUMMARY_RE = re.compile(
    r"<!-- COMPACT-SUMMARY-START -->[\s\S]*?<!-- COMPACT-SUMMARY-END -->"
)


def get_log_path(cwd: Path) -> Path:
    """Return the path to the cycle log file."""
    return Path(cwd) / ".planning" / LOG_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_log(cwd: Path, project_name: str) -> Path:
    """Create a new cycle log with header and empty compact summary."""
    log_path = get_log_path(cwd)
    header = "\n".join([
        f"# ERP Cycle Log: {project_name}",
        "",
        f"**Started:** {_now_iso()}",
        "**Status:** In Progress",
        "",
        "<!-- COMPACT-SUMMARY-START -->",
        "## Quick Resume",
        "- **Last Iteration:** 0",
        "- **Shipped:** 0/0",
        "- **In Progress:** 0",
        "- **Blocked:** 0",
        "- **Next Action:** decompose PRD",
        "- **Current Wave:** 0",
        "<!-- COMPACT-SUMMARY-END -->",
        "",
        "---",
        "",
        "## Iterations",
        "",
    ])
    log_path.write_text(header, encoding="utf-8")
    return log_path


def update_compact_summary(cwd: Path, summary: dict) -> None:
    """Replace the compact summary block in the log."""
    log_path = get_log_path(cwd)
    content = log_path.read_text(encoding="utf-8")
    new_summary = "\n".join([
        "<!-- COMPACT-SUMMARY-START -->",
        "## Quick Resume",
        f"- **Last Iteration:** {summary['iteration']}",
        f"- **Shipped:** {summary['shipped']}/{summary['total']}",
        f"- **In Progress:** {summary['in_progress']}",
        f"- **Blocked:** {summary['blocked']}",
        f"- **Next Action:** {summary['next_action']}",
        f"- **Current Wave:** {summary['wave']}",
        f"- **Coherence Warnings:** {summary.get('coherence_warnings', 0)}",
        "<!-- COMPACT-SUMMARY-END -->",
    ])
    updated = _COMPACT_SUMMARY_RE.sub(new_summary, content)
    log_path.write_text(updated, encoding="utf-8")


def append_entry(cwd: Path, entry: dict) -> None:
    """Append an iteration entry and update the compact summary."""
    log_path = get_log_path(cwd)
    timestamp = _now_iso()
    stats = entry.get("stats", {})

    lines = [
        f"### Iteration {entry['iteration']} — {timestamp}",
        f"- **Module:** {entry.get('module', 'N/A')}",
        f"- **Action:** {entry['action']}",
        f"- **Result:** {entry['result']}",
    ]
    if entry.get("wave"):
        lines.append(f"- **Wave:** {entry['wave']}")
    if entry.get("errors"):
        lines.append(f"- **Errors:** {entry['errors']}")
    lines.append(
        f"- **Progress:** {stats.get('shipped', 0)}/{stats.get('total', 0)} shipped "
        f"| {stats.get('in_progress', 0)} in progress "
        f"| {stats.get('remaining', 0)} remaining"
    )
    lines.append("")

    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    update_compact_summary(cwd, {
        "iteration": entry["iteration"],
        "shipped": stats.get("shipped", 0),
        "total": stats.get("total", 0),
        "in_progress": stats.get("in_progress", 0),
        "blocked": stats.get("blocked", 0),
        "next_action": entry.get("next_action", "continue"),
        "wave": entry.get("wave", 0),
        "coherence_warnings": entry.get("coherence_warnings", 0),
    })


def append_blocked_module(cwd: Path, module_name: str, reason: str) -> None:
    """Append a blocked module notice."""
    log_path = get_log_path(cwd)
    block = f"\n> **BLOCKED:** `{module_name}` — {reason}\n\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(block)


def append_coherence_event(cwd: Path, event: dict) -> None:
    """Append a coherence event notice."""
    log_path = get_log_path(cwd)
    lines = [
        "",
        f"> **COHERENCE [{event['type']}]:** `{event['source_module']}` → `{event['target_module']}`",
        f"> {event['details']}",
    ]
    if event.get("resolution"):
        lines.append(f"> **Resolution:** {event['resolution']}")
    lines.append("")

    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def finalize_log(cwd: Path, summary: dict) -> None:
    """Append the completion footer to the log."""
    log_path = get_log_path(cwd)
    lines = [
        "",
        "---",
        "",
        "## Cycle Complete",
        "",
        f"**Finished:** {_now_iso()}",
        f"**Total Modules:** {summary['total']}",
        f"**Shipped:** {summary['shipped']}",
        f"**Blocked:** {summary['blocked']}",
        f"**Total Iterations:** {summary['iterations']}",
        f"**Errors Encountered:** {summary['errors']}",
        f"**Coherence Warnings:** {summary.get('coherence_warnings', 0)}",
        f"**Context Resets:** {summary.get('context_resets', 0)}",
        "",
        "### Shipped Modules",
    ]
    for m in summary.get("shipped_list", []):
        lines.append(f"- {m}")
    lines.append("")

    blocked_list = summary.get("blocked_list", [])
    if blocked_list:
        lines.append("### Blocked Modules")
        for m in blocked_list:
            lines.append(f"- {m['name']}: {m['reason']}")

    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
