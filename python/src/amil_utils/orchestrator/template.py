"""Template — Template selection and fill operations.

Ported from orchestrator/amil/bin/lib/template.cjs (223 lines, since deleted).
Provides template_select (heuristic complexity classification) and template_fill
(generates summary/plan/verification documents from templates).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

from amil_utils.orchestrator.core import (
    find_phase,
    generate_slug,
    normalize_phase_name,
    to_posix_path,
)
from amil_utils.orchestrator.frontmatter import reconstruct_frontmatter


# ── Public API ───────────────────────────────────────────────────────────────


def template_select(cwd: str | Path, plan_path: str) -> dict:
    """Select a template type based on plan complexity heuristics."""
    try:
        full_path = Path(plan_path)
        if not full_path.is_absolute():
            full_path = Path(cwd) / plan_path
        content = full_path.read_text(encoding="utf-8")

        # Count tasks
        task_matches = re.findall(r"###\s*Task\s*\d+", content)
        task_count = len(task_matches)

        # Check for decisions
        decision_matches = re.findall(r"decision", content, re.IGNORECASE)
        has_decisions = len(decision_matches) > 0

        # Count file mentions
        file_mentions: set[str] = set()
        for m in re.finditer(r"`([^`]+\.[a-zA-Z]+)`", content):
            if "/" in m.group(1) and not m.group(1).startswith("http"):
                file_mentions.add(m.group(1))
        file_count = len(file_mentions)

        # Classify
        template_type = "standard"
        if task_count <= 2 and file_count <= 3 and not has_decisions:
            template_type = "minimal"
        elif has_decisions or file_count > 6 or task_count > 5:
            template_type = "complex"

        return {
            "template": f"templates/summary-{template_type}.md",
            "type": template_type,
            "taskCount": task_count,
            "fileCount": file_count,
            "hasDecisions": has_decisions,
        }
    except OSError as e:
        return {
            "template": "templates/summary-standard.md",
            "type": "standard",
            "error": str(e),
        }


def template_fill(
    cwd: str | Path,
    template_type: str,
    *,
    phase: str,
    name: str | None = None,
    plan: str | None = None,
    plan_type: str | None = None,
    wave: int | None = None,
    fields: dict | None = None,
) -> dict:
    """Generate a template document and write it to the phase directory."""
    if template_type not in ("summary", "plan", "verification"):
        raise ValueError(
            f"Unknown template type: {template_type}. Available: summary, plan, verification"
        )

    cwd = Path(cwd)
    phase_info = find_phase(cwd, phase)
    if not phase_info or not phase_info.get("found"):
        return {"error": "Phase not found", "phase": phase}

    padded = normalize_phase_name(phase)
    today = date.today().isoformat()
    phase_name = name or phase_info.get("phase_name") or "Unnamed"
    phase_slug = phase_info.get("phase_slug") or generate_slug(phase_name)
    phase_id = f"{padded}-{phase_slug}"
    plan_num = (plan or "01").zfill(2)
    extra_fields = fields or {}

    if template_type == "summary":
        frontmatter = {
            "phase": phase_id,
            "plan": plan_num,
            "subsystem": "[primary category]",
            "tags": [],
            "provides": [],
            "affects": [],
            "tech-stack": {"added": [], "patterns": []},
            "key-files": {"created": [], "modified": []},
            "key-decisions": [],
            "patterns-established": [],
            "duration": "[X]min",
            "completed": today,
            **extra_fields,
        }
        body = "\n".join([
            f"# Phase {phase}: {phase_name} Summary",
            "",
            "**[Substantive one-liner describing outcome]**",
            "",
            "## Performance",
            "- **Duration:** [time]",
            "- **Tasks:** [count completed]",
            "- **Files modified:** [count]",
            "",
            "## Accomplishments",
            "- [Key outcome 1]",
            "- [Key outcome 2]",
            "",
            "## Task Commits",
            "1. **Task 1: [task name]** - `hash`",
            "",
            "## Files Created/Modified",
            "- `path/to/file.ts` - What it does",
            "",
            "## Decisions & Deviations",
            "[Key decisions or \"None - followed plan as specified\"]",
            "",
            "## Next Phase Readiness",
            "[What's ready for next phase]",
        ])
        file_name = f"{padded}-{plan_num}-SUMMARY.md"

    elif template_type == "plan":
        plan_t = plan_type or "execute"
        wave_num = wave or 1
        frontmatter = {
            "phase": phase_id,
            "plan": plan_num,
            "type": plan_t,
            "wave": wave_num,
            "depends_on": [],
            "files_modified": [],
            "autonomous": True,
            "user_setup": [],
            "must_haves": {"truths": [], "artifacts": [], "key_links": []},
            **extra_fields,
        }
        body = "\n".join([
            f"# Phase {phase} Plan {plan_num}: [Title]",
            "",
            "## Objective",
            "- **What:** [What this plan builds]",
            "- **Why:** [Why it matters for the phase goal]",
            "- **Output:** [Concrete deliverable]",
            "",
            "## Context",
            "@.planning/PROJECT.md",
            "@.planning/ROADMAP.md",
            "@.planning/STATE.md",
            "",
            "## Tasks",
            "",
            '<task type="code">',
            "  <name>[Task name]</name>",
            "  <files>[file paths]</files>",
            "  <action>[What to do]</action>",
            "  <verify>[How to verify]</verify>",
            "  <done>[Definition of done]</done>",
            "</task>",
            "",
            "## Verification",
            "[How to verify this plan achieved its objective]",
            "",
            "## Success Criteria",
            "- [ ] [Criterion 1]",
            "- [ ] [Criterion 2]",
        ])
        file_name = f"{padded}-{plan_num}-PLAN.md"

    else:  # verification
        frontmatter = {
            "phase": phase_id,
            "verified": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "score": "0/0 must-haves verified",
            **extra_fields,
        }
        body = "\n".join([
            f"# Phase {phase}: {phase_name} — Verification",
            "",
            "## Observable Truths",
            "| # | Truth | Status | Evidence |",
            "|---|-------|--------|----------|",
            "| 1 | [Truth] | pending | |",
            "",
            "## Required Artifacts",
            "| Artifact | Expected | Status | Details |",
            "|----------|----------|--------|---------|",
            "| [path] | [what] | pending | |",
            "",
            "## Key Link Verification",
            "| From | To | Via | Status | Details |",
            "|------|----|----|--------|---------|",
            "| [source] | [target] | [connection] | pending | |",
            "",
            "## Requirements Coverage",
            "| Requirement | Status | Blocking Issue |",
            "|-------------|--------|----------------|",
            "| [req] | pending | |",
            "",
            "## Result",
            "[Pending verification]",
        ])
        file_name = f"{padded}-VERIFICATION.md"

    yaml_str = reconstruct_frontmatter(frontmatter)
    full_content = f"---\n{yaml_str}\n---\n\n{body}\n"
    out_path = Path(cwd) / phase_info["directory"] / file_name

    if out_path.exists():
        rel_path = to_posix_path(out_path.relative_to(cwd))
        return {"error": "File already exists", "path": rel_path}

    out_path.write_text(full_content, encoding="utf-8")
    rel_path = to_posix_path(out_path.relative_to(cwd))
    return {"created": True, "path": rel_path, "template": template_type}
