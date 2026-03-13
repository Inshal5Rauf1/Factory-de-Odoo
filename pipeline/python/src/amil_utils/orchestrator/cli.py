"""Click command group for orchestrator commands.

Thin wiring layer: each command parses Click args, calls the library
function (which returns a dict), and emits JSON to stdout.
"""
from __future__ import annotations

import json
from pathlib import Path

import click


# ─── Shared helpers ────────────────────────────────────────────────


def _common(fn):
    """Apply --cwd and --raw options to a Click command."""
    fn = click.option(
        "--raw", is_flag=True, default=False, help="Raw output mode"
    )(fn)
    fn = click.option(
        "--cwd",
        default=".",
        type=click.Path(exists=True),
        help="Project root directory",
    )(fn)
    return fn


def _emit(data: dict) -> None:
    click.echo(json.dumps(data))


# ─── Root group ────────────────────────────────────────────────────


@click.group("orch")
def orch_group() -> None:
    """Orchestrator: state, phase, and project management."""


# ─── State commands ────────────────────────────────────────────────


@orch_group.group("state")
def state_grp() -> None:
    """State management commands."""


@state_grp.command("load")
@_common
def state_load_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.state import state_load

    _emit(state_load(cwd))


@state_grp.command("json")
@_common
def state_json_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.state import state_json

    _emit(state_json(cwd))


@state_grp.command("get")
@click.argument("section", required=False, default=None)
@_common
def state_get_cmd(section: str | None, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.state import state_get

    _emit(state_get(cwd, section))


@state_grp.command("update")
@click.argument("field")
@click.argument("value")
@_common
def state_update_cmd(field: str, value: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.state import state_update

    _emit(state_update(cwd, field, value))


@state_grp.command("patch")
@click.argument("pairs", nargs=-1)
@_common
def state_patch_cmd(pairs: tuple[str, ...], cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.state import state_patch

    patches: dict[str, str] = {}
    args = list(pairs)
    for i in range(0, len(args) - 1, 2):
        key = args[i].lstrip("-")
        patches[key] = args[i + 1]
    _emit(state_patch(cwd, patches))


@state_grp.command("advance-plan")
@_common
def state_advance_plan_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.state import state_advance_plan

    _emit(state_advance_plan(cwd))


@state_grp.command("record-metric")
@click.option("--phase", required=True)
@click.option("--plan", required=True)
@click.option("--duration", required=True)
@click.option("--tasks", default=None)
@click.option("--files", default=None)
@_common
def state_record_metric_cmd(
    phase: str,
    plan: str,
    duration: str,
    tasks: str | None,
    files: str | None,
    cwd: str,
    raw: bool,
) -> None:
    from amil_utils.orchestrator.state import state_record_metric

    _emit(
        state_record_metric(
            cwd,
            phase=phase,
            plan=plan,
            duration=duration,
            tasks=tasks,
            files=files,
        )
    )


@state_grp.command("update-progress")
@_common
def state_update_progress_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.state import state_update_progress

    _emit(state_update_progress(cwd))


@state_grp.command("add-decision")
@click.option("--phase", default=None)
@click.option("--summary", default=None)
@click.option("--summary-file", default=None)
@click.option("--rationale", default="")
@click.option("--rationale-file", default=None)
@_common
def state_add_decision_cmd(
    phase: str | None,
    summary: str | None,
    summary_file: str | None,
    rationale: str,
    rationale_file: str | None,
    cwd: str,
    raw: bool,
) -> None:
    from amil_utils.orchestrator.state import state_add_decision

    if summary_file and not summary:
        summary = Path(summary_file).read_text(encoding="utf-8").strip()
    if rationale_file and not rationale:
        rationale = Path(rationale_file).read_text(encoding="utf-8").strip()
    _emit(state_add_decision(cwd, phase=phase, summary=summary, rationale=rationale))


@state_grp.command("add-blocker")
@click.option("--text", required=True)
@_common
def state_add_blocker_cmd(text: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.state import state_add_blocker

    _emit(state_add_blocker(cwd, text))


@state_grp.command("resolve-blocker")
@click.option("--text", required=True)
@_common
def state_resolve_blocker_cmd(text: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.state import state_resolve_blocker

    _emit(state_resolve_blocker(cwd, text))


@state_grp.command("record-session")
@click.option("--stopped-at", required=True)
@click.option("--resume-file", default="None")
@_common
def state_record_session_cmd(
    stopped_at: str, resume_file: str, cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.state import state_record_session

    _emit(state_record_session(cwd, stopped_at=stopped_at, resume_file=resume_file))


@state_grp.command("snapshot")
@_common
def state_snapshot_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.state import state_snapshot

    _emit(state_snapshot(cwd))


# ─── Phase commands ────────────────────────────────────────────────


@orch_group.group("phase")
def phase_grp() -> None:
    """Phase mutation commands."""


@phase_grp.command("next-decimal")
@click.argument("base_phase")
@_common
def phase_next_decimal_cmd(base_phase: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.phase import phase_next_decimal

    _emit(phase_next_decimal(cwd, base_phase))


@phase_grp.command("add")
@click.argument("description")
@_common
def phase_add_cmd(description: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.phase import phase_add

    _emit(phase_add(cwd, description))


@phase_grp.command("insert")
@click.argument("after_phase")
@click.argument("description")
@_common
def phase_insert_cmd(after_phase: str, description: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.phase import phase_insert

    _emit(phase_insert(cwd, after_phase, description))


@phase_grp.command("remove")
@click.argument("target_phase")
@click.option("--force", is_flag=True, default=False)
@_common
def phase_remove_cmd(
    target_phase: str, force: bool, cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.phase import phase_remove

    _emit(phase_remove(cwd, target_phase, force=force))


@phase_grp.command("complete")
@click.argument("phase_num")
@_common
def phase_complete_cmd(phase_num: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.phase import phase_complete

    _emit(phase_complete(cwd, phase_num))


# ─── Phases (listing) ─────────────────────────────────────────────


@orch_group.group("phases")
def phases_grp() -> None:
    """Phase listing commands."""


@phases_grp.command("list")
@click.option("--type", "file_type", default=None)
@click.option("--phase", default=None)
@click.option("--include-archived", is_flag=True, default=False)
@_common
def phases_list_cmd(
    file_type: str | None,
    phase: str | None,
    include_archived: bool,
    cwd: str,
    raw: bool,
) -> None:
    from amil_utils.orchestrator.phase import phases_list

    _emit(
        phases_list(
            cwd, file_type=file_type, phase=phase, include_archived=include_archived
        )
    )


# ─── Roadmap commands ─────────────────────────────────────────────


@orch_group.group("roadmap")
def roadmap_grp() -> None:
    """Roadmap operations."""


@roadmap_grp.command("get-phase")
@click.argument("phase_num")
@_common
def roadmap_get_phase_cmd(phase_num: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.roadmap import roadmap_get_phase

    _emit(roadmap_get_phase(cwd, phase_num))


@roadmap_grp.command("analyze")
@_common
def roadmap_analyze_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.roadmap import roadmap_analyze

    _emit(roadmap_analyze(cwd))


@roadmap_grp.command("update-plan-progress")
@click.argument("phase_num")
@_common
def roadmap_update_plan_progress_cmd(phase_num: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.roadmap import roadmap_update_plan_progress

    _emit(roadmap_update_plan_progress(cwd, phase_num))


# ─── Requirements ──────────────────────────────────────────────────


@orch_group.group("requirements")
def requirements_grp() -> None:
    """Requirements operations."""


@requirements_grp.command("mark-complete")
@click.argument("req_ids", nargs=-1, required=True)
@_common
def requirements_mark_complete_cmd(
    req_ids: tuple[str, ...], cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.milestone import requirements_mark_complete

    _emit(requirements_mark_complete(cwd, list(req_ids)))


# ─── Milestone ─────────────────────────────────────────────────────


@orch_group.group("milestone")
def milestone_grp() -> None:
    """Milestone operations."""


@milestone_grp.command("complete")
@click.argument("version")
@click.option("--name", default=None)
@click.option("--archive-phases", is_flag=True, default=False)
@_common
def milestone_complete_cmd(
    version: str,
    name: str | None,
    archive_phases: bool,
    cwd: str,
    raw: bool,
) -> None:
    from amil_utils.orchestrator.milestone import milestone_complete

    _emit(
        milestone_complete(
            cwd, version, name=name, archive_phases=archive_phases
        )
    )


# ─── Validate ──────────────────────────────────────────────────────


@orch_group.group("validate")
def validate_grp() -> None:
    """Validation commands."""


@validate_grp.command("health")
@click.option("--repair", is_flag=True, default=False)
@_common
def validate_health_cmd(repair: bool, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.health import validate_health

    _emit(validate_health(cwd, repair=repair))


# ─── Template ──────────────────────────────────────────────────────


@orch_group.group("template")
def template_grp() -> None:
    """Template operations."""


@template_grp.command("select")
@click.argument("plan_path")
@_common
def template_select_cmd(plan_path: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.template import template_select

    _emit(template_select(cwd, plan_path))


@template_grp.command("fill")
@click.argument("template_type")
@click.option("--phase", required=True)
@click.option("--plan", default=None)
@click.option("--name", default=None)
@click.option("--type", "fill_type", default="execute")
@click.option("--wave", default="1")
@click.option("--fields", default="{}")
@_common
def template_fill_cmd(
    template_type: str,
    phase: str,
    plan: str | None,
    name: str | None,
    fill_type: str,
    wave: str,
    fields: str,
    cwd: str,
    raw: bool,
) -> None:
    from amil_utils.orchestrator.template import template_fill

    _emit(
        template_fill(
            cwd,
            template_type,
            phase=phase,
            plan=plan,
            name=name,
            fill_type=fill_type,
            wave=wave,
            fields=json.loads(fields),
        )
    )


# ─── Frontmatter ──────────────────────────────────────────────────


@orch_group.group("frontmatter")
def frontmatter_grp() -> None:
    """Frontmatter CRUD commands."""


@frontmatter_grp.command("get")
@click.argument("file")
@click.option("--field", default=None)
@_common
def frontmatter_get_cmd(
    file: str, field: str | None, cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.core import ensure_within_cwd
    from amil_utils.orchestrator.frontmatter import extract_frontmatter

    resolved = ensure_within_cwd(cwd, file)
    content = resolved.read_text(encoding="utf-8")
    fm = extract_frontmatter(content)
    if field:
        _emit({field: fm.get(field)})
    else:
        _emit(fm)


@frontmatter_grp.command("set")
@click.argument("file")
@click.option("--field", required=True)
@click.option("--value", required=True)
@_common
def frontmatter_set_cmd(
    file: str, field: str, value: str, cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.core import ensure_within_cwd
    from amil_utils.orchestrator.frontmatter import (
        extract_frontmatter,
        splice_frontmatter,
    )

    resolved = ensure_within_cwd(cwd, file)
    content = resolved.read_text(encoding="utf-8")
    fm = extract_frontmatter(content)
    try:
        fm[field] = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        fm[field] = value
    new_content = splice_frontmatter(content, fm)
    resolved.write_text(new_content, encoding="utf-8")
    _emit({"updated": True, "field": field})


@frontmatter_grp.command("merge")
@click.argument("file")
@click.option("--data", required=True)
@_common
def frontmatter_merge_cmd(file: str, data: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.core import ensure_within_cwd
    from amil_utils.orchestrator.frontmatter import (
        extract_frontmatter,
        splice_frontmatter,
    )

    resolved = ensure_within_cwd(cwd, file)
    content = resolved.read_text(encoding="utf-8")
    fm = extract_frontmatter(content)
    fm.update(json.loads(data))
    new_content = splice_frontmatter(content, fm)
    resolved.write_text(new_content, encoding="utf-8")
    _emit({"merged": True, "fields": list(json.loads(data).keys())})


@frontmatter_grp.command("validate")
@click.argument("file")
@click.option("--schema", required=True)
@_common
def frontmatter_validate_cmd(
    file: str, schema: str, cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.core import ensure_within_cwd
    from amil_utils.orchestrator.frontmatter import (
        extract_frontmatter,
        validate_frontmatter,
    )

    resolved = ensure_within_cwd(cwd, file)
    content = resolved.read_text(encoding="utf-8")
    fm = extract_frontmatter(content)
    _emit(validate_frontmatter(fm, schema))


# ─── Init commands ─────────────────────────────────────────────────


@orch_group.group("init")
def init_grp() -> None:
    """Workflow initialization commands."""


@init_grp.command("execute-phase")
@click.argument("phase")
@_common
def init_execute_phase_cmd(phase: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_execute_phase

    _emit(init_execute_phase(cwd, phase))


@init_grp.command("plan-phase")
@click.argument("phase")
@_common
def init_plan_phase_cmd(phase: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_plan_phase

    _emit(init_plan_phase(cwd, phase))


@init_grp.command("new-project")
@_common
def init_new_project_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_new_project

    _emit(init_new_project(cwd))


@init_grp.command("new-milestone")
@_common
def init_new_milestone_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_new_milestone

    _emit(init_new_milestone(cwd))


@init_grp.command("quick")
@click.argument("description")
@_common
def init_quick_cmd(description: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_quick

    _emit(init_quick(cwd, description))


@init_grp.command("resume")
@_common
def init_resume_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_resume

    _emit(init_resume(cwd))


@init_grp.command("verify-work")
@click.argument("phase")
@_common
def init_verify_work_cmd(phase: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_verify_work

    _emit(init_verify_work(cwd, phase))


@init_grp.command("phase-op")
@click.argument("phase")
@_common
def init_phase_op_cmd(phase: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_phase_op

    _emit(init_phase_op(cwd, phase))


@init_grp.command("todos")
@click.argument("area", required=False, default=None)
@_common
def init_todos_cmd(area: str | None, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_todos

    _emit(init_todos(cwd, area=area))


@init_grp.command("milestone-op")
@_common
def init_milestone_op_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_milestone_op

    _emit(init_milestone_op(cwd))


@init_grp.command("map-codebase")
@_common
def init_map_codebase_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_map_codebase

    _emit(init_map_codebase(cwd))


@init_grp.command("progress")
@_common
def init_progress_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.init_commands import init_progress

    _emit(init_progress(cwd))


# ─── Dep-graph commands ───────────────────────────────────────────


@orch_group.group("dep-graph")
def dep_graph_grp() -> None:
    """Dependency graph commands."""


@dep_graph_grp.command("build")
@_common
def dep_graph_build_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.dependency_graph import dep_graph_build

    _emit(dep_graph_build(cwd))


@dep_graph_grp.command("order")
@_common
def dep_graph_order_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.dependency_graph import dep_graph_order

    _emit({"order": dep_graph_order(cwd)})


@dep_graph_grp.command("tiers")
@_common
def dep_graph_tiers_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.dependency_graph import dep_graph_tiers

    _emit(dep_graph_tiers(cwd))


@dep_graph_grp.command("can-generate")
@click.argument("module_name")
@_common
def dep_graph_can_generate_cmd(module_name: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.dependency_graph import dep_graph_can_generate

    _emit(dep_graph_can_generate(cwd, module_name))


# ─── Module-status commands ───────────────────────────────────────


@orch_group.group("module-status")
def module_status_grp() -> None:
    """Module lifecycle status commands."""


@module_status_grp.command("read")
@_common
def module_status_read_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.module_status import module_status_read

    _emit(module_status_read(cwd))


@module_status_grp.command("get")
@click.argument("module_name")
@_common
def module_status_get_cmd(module_name: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.module_status import module_status_get

    _emit(module_status_get(cwd, module_name))


@module_status_grp.command("init")
@click.argument("module_name")
@click.argument("tier")
@click.argument("depends", required=False, default="")
@_common
def module_status_init_cmd(
    module_name: str, tier: str, depends: str, cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.module_status import module_status_init

    _emit(module_status_init(cwd, module_name, tier, depends))


@module_status_grp.command("transition")
@click.argument("module_name")
@click.argument("new_state")
@_common
def module_status_transition_cmd(
    module_name: str, new_state: str, cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.module_status import module_status_transition

    _emit(module_status_transition(cwd, module_name, new_state))


@module_status_grp.command("tiers")
@_common
def module_status_tiers_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.module_status import tier_status

    _emit(tier_status(cwd))


# ─── Registry commands ────────────────────────────────────────────


@orch_group.group("registry")
def registry_grp() -> None:
    """Model registry commands."""


@registry_grp.command("read")
@_common
def registry_read_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.registry import read_registry_file

    _emit(read_registry_file(cwd))


@registry_grp.command("read-model")
@click.argument("model_name")
@_common
def registry_read_model_cmd(model_name: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.registry import read_model_from_registry

    result = read_model_from_registry(cwd, model_name)
    _emit(result if result else {"found": False, "model": model_name})


@registry_grp.command("update")
@click.argument("manifest_path")
@_common
def registry_update_cmd(manifest_path: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.registry import update_registry

    _emit(update_registry(cwd, manifest_path))


@registry_grp.command("rollback")
@_common
def registry_rollback_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.registry import rollback_registry

    result = rollback_registry(cwd)
    _emit(result if result else {"rolled_back": False, "reason": "no_backup"})


@registry_grp.command("validate")
@_common
def registry_validate_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.registry import validate_registry

    _emit(validate_registry(cwd))


@registry_grp.command("stats")
@_common
def registry_stats_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.registry import stats_registry

    _emit(stats_registry(cwd))


# ─── Cycle-log commands ───────────────────────────────────────────


@orch_group.group("cycle-log")
def cycle_log_grp() -> None:
    """Module generation cycle log commands."""


@cycle_log_grp.command("init")
@click.argument("project_name", default="ERP Project")
@_common
def cycle_log_init_cmd(project_name: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.cycle_log import init_log

    path = init_log(Path(cwd), project_name)
    _emit({"created": True, "path": str(path)})


@cycle_log_grp.command("append")
@click.argument("entry_json")
@_common
def cycle_log_append_cmd(entry_json: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.cycle_log import append_entry

    append_entry(Path(cwd), json.loads(entry_json))
    _emit({"appended": True})


@cycle_log_grp.command("blocked")
@click.argument("module_name")
@click.argument("reason")
@_common
def cycle_log_blocked_cmd(
    module_name: str, reason: str, cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.cycle_log import append_blocked_module

    append_blocked_module(Path(cwd), module_name, reason)
    _emit({"blocked": True, "module": module_name})


@cycle_log_grp.command("coherence")
@click.argument("event_json")
@_common
def cycle_log_coherence_cmd(event_json: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.cycle_log import append_coherence_event

    append_coherence_event(Path(cwd), json.loads(event_json))
    _emit({"recorded": True})


@cycle_log_grp.command("finalize")
@click.argument("summary_json")
@_common
def cycle_log_finalize_cmd(summary_json: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.cycle_log import finalize_log

    finalize_log(Path(cwd), json.loads(summary_json))
    _emit({"finalized": True})


# ─── Coherence commands ───────────────────────────────────────────


@orch_group.group("coherence")
def coherence_grp() -> None:
    """Cross-module coherence commands."""


@coherence_grp.command("check")
@click.option("--spec", required=True, help="Path to spec JSON")
@click.option("--registry", "registry_path", default=None, help="Registry path override")
@_common
def coherence_check_cmd(
    spec: str, registry_path: str | None, cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.coherence import run_all_checks
    from amil_utils.orchestrator.registry import read_registry_file

    spec_data = json.loads(Path(cwd).joinpath(spec).read_text(encoding="utf-8"))
    reg = read_registry_file(cwd)
    _emit(run_all_checks(spec_data, reg))


# ─── Standalone commands ──────────────────────────────────────────


@orch_group.command("find-phase")
@click.argument("phase")
@_common
def find_phase_cmd(phase: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.phase import phase_find

    _emit(phase_find(cwd, phase))


@orch_group.command("phase-plan-index")
@click.argument("phase")
@_common
def phase_plan_index_cmd(phase: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.phase import phase_plan_index

    _emit(phase_plan_index(cwd, phase))


@orch_group.command("generate-slug")
@click.argument("text")
@_common
def generate_slug_cmd(text: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.commands import generate_slug

    _emit(generate_slug(text))


@orch_group.command("current-timestamp")
@click.argument("format", default="full")
@_common
def current_timestamp_cmd(format: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.commands import current_timestamp

    _emit(current_timestamp(format))


@orch_group.command("list-todos")
@click.argument("area", required=False, default=None)
@_common
def list_todos_cmd(area: str | None, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.commands import list_todos

    _emit(list_todos(cwd, area))


@orch_group.command("verify-path-exists")
@click.argument("target_path")
@_common
def verify_path_exists_cmd(target_path: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.commands import verify_path_exists

    _emit(verify_path_exists(cwd, target_path))


@orch_group.command("resolve-model")
@click.argument("agent_type")
@_common
def resolve_model_cmd(agent_type: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.commands import resolve_model

    _emit(resolve_model(cwd, agent_type))


@orch_group.command("commit")
@click.argument("message")
@click.option("--files", multiple=True)
@click.option("--amend", is_flag=True, default=False)
@_common
def commit_cmd(
    message: str,
    files: tuple[str, ...],
    amend: bool,
    cwd: str,
    raw: bool,
) -> None:
    from amil_utils.orchestrator.commands import commit

    _emit(commit(cwd, message, list(files), amend=amend))


@orch_group.command("history-digest")
@_common
def history_digest_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.commands import history_digest

    _emit(history_digest(cwd))


@orch_group.command("summary-extract")
@click.argument("summary_path")
@click.option("--fields", default=None)
@_common
def summary_extract_cmd(
    summary_path: str, fields: str | None, cwd: str, raw: bool
) -> None:
    from amil_utils.orchestrator.commands import summary_extract

    field_list = fields.split(",") if fields else None
    _emit(summary_extract(cwd, summary_path, fields=field_list))


@orch_group.command("progress")
@click.argument("format", default="json")
@_common
def progress_cmd(format: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.commands import progress_render

    _emit(progress_render(cwd, format=format))


@orch_group.command("todo")
@click.argument("subcommand")
@click.argument("filename")
@_common
def todo_cmd(subcommand: str, filename: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.commands import todo_complete

    if subcommand == "complete":
        _emit(todo_complete(cwd, filename))
    else:
        _emit({"error": f"Unknown todo subcommand: {subcommand}"})


@orch_group.command("scaffold")
@click.argument("scaffold_type")
@click.option("--phase", default=None)
@click.option("--name", default=None)
@_common
def scaffold_cmd(
    scaffold_type: str,
    phase: str | None,
    name: str | None,
    cwd: str,
    raw: bool,
) -> None:
    from amil_utils.orchestrator.commands import scaffold

    _emit(scaffold(cwd, scaffold_type, phase=phase, name=name))


@orch_group.command("config-ensure-section")
@_common
def config_ensure_section_cmd(cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.config import config_ensure_section

    _emit(config_ensure_section(cwd))


@orch_group.command("config-set")
@click.argument("key_path")
@click.argument("value")
@_common
def config_set_cmd(key_path: str, value: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.config import config_set

    _emit(config_set(cwd, key_path, value))


@orch_group.command("config-get")
@click.argument("key_path")
@_common
def config_get_cmd(key_path: str, cwd: str, raw: bool) -> None:
    from amil_utils.orchestrator.config import config_get

    result = config_get(cwd, key_path)
    _emit({"key": key_path, "value": result})
