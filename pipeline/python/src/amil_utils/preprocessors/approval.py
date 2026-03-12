"""Approval workflow pattern processing."""

from __future__ import annotations

import logging
from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.utils.copy import deep_copy_model

logger = logging.getLogger(__name__)


def _validate_acyclic_states(levels: list[dict[str, Any]], model_name: str) -> None:
    """Validate that the approval state graph has no cycles (BUG-M15).

    Builds a directed graph from (from_state -> to_state) transitions and
    checks for cycles using DFS. Raises ValueError if a cycle is detected.
    """
    # Build adjacency list: draft -> level[0].state, level[i].state -> level[i+1].state, ...
    edges: dict[str, list[str]] = {}
    prev_state = "draft"
    for level in levels:
        edges.setdefault(prev_state, []).append(level["state"])
        prev_state = level["state"]
    # Last level -> terminal
    if levels:
        edges.setdefault(levels[-1]["state"], []).append(levels[-1]["next"])

    # DFS cycle detection
    visited: set[str] = set()
    in_stack: set[str] = set()

    def _dfs(node: str) -> bool:
        if node in in_stack:
            return True  # Cycle found
        if node in visited:
            return False
        visited.add(node)
        in_stack.add(node)
        for neighbor in edges.get(node, []):
            if _dfs(neighbor):
                return True
        in_stack.discard(node)
        return False

    for state in edges:
        if _dfs(state):
            raise ValueError(
                f"Circular approval states detected in model '{model_name}'. "
                f"State graph must be acyclic. States: {list(edges.keys())}"
            )


@register_preprocessor(order=80, name="approval_patterns")
def _process_approval_patterns(spec: dict[str, Any]) -> dict[str, Any]:
    """Pre-process approval workflow configuration, enriching approval models.

    For each model with an ``approval`` block:
    1. Validates role references against ``security_roles`` (skip if ``group`` explicit)
    2. Synthesizes state Selection field (draft + levels + terminal + optional rejected)
    3. Builds action method specs for each level transition
    4. Resolves group XML IDs (role-based or explicit override)
    5. Builds submit, reject, and reset action specs
    6. Sets lock_after, editable_fields for stage locking
    7. Builds approval_record_rules (two-tier: draft-owner + manager-full)
    8. Adds ``"approval"`` to ``override_sources["write"]``
    9. Sets ``has_write_override = True``, ``needs_translate = True``
    10. Adds ``"approval"`` to ``record_rule_scopes``

    Returns a new spec dict. Pure function -- does NOT mutate the input spec.
    """
    models = spec.get("models", [])
    approval_models = [m for m in models if m.get("approval")]
    if not approval_models:
        return spec

    module_name = spec["module_name"]
    security_roles = spec.get("security_roles", [])
    role_lookup = {r["name"]: r for r in security_roles}

    new_models = []
    for model in models:
        if not model.get("approval"):
            new_models.append(model)
            continue

        new_model = deep_copy_model(model)
        approval = new_model["approval"]
        levels = approval.get("levels", [])

        # 0. Validate non-empty levels -- skip model with warning if empty
        if not levels:
            logger.warning(
                "Model '%s' has approval block with empty levels -- skipping "
                "approval enrichment. Define at least one approval level.",
                model.get("name", "unknown"),
            )
            new_models.append(model)
            continue

        # 1. Validate all roles exist in security_roles (skip if group explicit)
        for level in levels:
            role = level.get("role")
            if role and role not in role_lookup and not level.get("group"):
                raise ValueError(
                    f"Approval role '{role}' not found in security_roles. "
                    f"Available roles: {list(role_lookup.keys())}"
                )

        # 1b. Validate state graph is acyclic (BUG-M15)
        _validate_acyclic_states(levels, model.get("name", "unknown"))

        # 2. Build state Selection with auto-prepended draft
        initial_label = approval.get("initial_label", "Draft")
        state_selection: list[tuple[str, str]] = [("draft", initial_label)]
        for level in levels:
            label = level.get("label", level["state"].replace("_", " ").title())
            state_selection.append((level["state"], label))
        # Terminal state from last level's "next"
        terminal = levels[-1]["next"]
        terminal_label = terminal.replace("_", " ").title()
        state_selection.append((terminal, terminal_label))
        # Optional rejected state
        on_reject = approval.get("on_reject", "draft")
        if on_reject == "rejected":
            state_selection.append(("rejected", "Rejected"))

        # 3. Remove any existing state/status Selection field from model fields
        new_model["fields"] = [
            f for f in new_model["fields"]
            if not (f.get("name") in ("state", "status") and f.get("type") == "Selection")
        ]

        # 4. Inject synthesized state field
        state_field = {
            "name": "state",
            "type": "Selection",
            "selection": state_selection,
            "default": "draft",
            "tracking": True,
            "required": True,
        }
        new_model["fields"].insert(0, state_field)

        # 5. Build action method specs -- one per level
        action_methods = []
        escalation_configs = []
        for i, level in enumerate(levels):
            if i == 0:
                from_state = "draft"
                from_state_label = initial_label
            else:
                from_state = levels[i - 1]["state"]
                from_state_label = levels[i - 1].get(
                    "label", levels[i - 1]["state"].replace("_", " ").title()
                )

            group_xml_id = level.get("group") or (
                f"{module_name}.group_{module_name}_{level['role']}"
            )
            role_label = role_lookup.get(level.get("role", ""), {}).get(
                "label", level.get("role", "").replace("_", " ").title()
            )

            method_spec: dict[str, Any] = {
                "name": f"action_approve_{level['state']}",
                "from_state": from_state,
                "to_state": level["state"],
                "from_state_label": from_state_label,
                "group_xml_id": group_xml_id,
                "role_label": role_label,
                "button_label": f"Approve ({role_label})",
            }

            # FLAW-18: Conditional routing -- skip level if condition met
            skip_if = level.get("skip_if")
            if skip_if:
                method_spec["skip_if"] = skip_if

            # FLAW-18: Delegation -- allow delegating approval
            if level.get("allow_delegation"):
                method_spec["allow_delegation"] = True

            action_methods.append(method_spec)

            # FLAW-18: Escalation config per level
            escalation = level.get("escalation")
            if escalation:
                escalate_to_role = escalation.get("escalate_to")
                escalate_group = None
                if escalate_to_role and escalate_to_role in role_lookup:
                    escalate_group = (
                        f"{module_name}.group_{module_name}_{escalate_to_role}"
                    )
                escalation_configs.append({
                    "level_state": level["state"],
                    "timeout_hours": escalation.get("timeout_hours", 48),
                    "escalate_to_role": escalate_to_role,
                    "escalate_to_group": escalate_group,
                    "action_name": f"action_approve_{level['state']}",
                })

        # 6. Build submit action (draft -> first level)
        first_level = levels[0]
        submit_action = {
            "name": "action_submit",
            "from_state": "draft",
            "to_state": first_level["state"],
            "from_state_label": initial_label,
            "group_xml_id": "",
            "role_label": "",
            "button_label": "Submit",
        }

        # 7. Build reject action (if reject_allowed_from non-empty or defaults to all non-terminal)
        reject_allowed_from = approval.get("reject_allowed_from")
        if reject_allowed_from is None:
            # Default: all non-terminal level states
            reject_allowed_from = [level["state"] for level in levels]
        reject_action = None
        if reject_allowed_from:
            reject_action = {
                "name": "action_reject",
                "to_state": on_reject,
                "reject_allowed_from": reject_allowed_from,
            }

        # 8. Build reset action (always generated)
        reset_action = {
            "name": "action_reset_to_draft",
            "to_state": "draft",
        }

        # 9. Build approval_record_rules (two-tier)
        model_var = model["name"].replace(".", "_")
        record_rules = [
            {
                "xml_id": f"rule_{model_var}_draft",
                "name": f"{model['description']}: Draft Records",
                "domain_force": "['|', ('state', '!=', 'draft'), ('create_uid', '=', user.id)]",
                "scope": "draft_owner",
            },
            {
                "xml_id": f"rule_{model_var}_manager",
                "name": f"{model['description']}: Manager Full Access",
                "domain_force": "[(1, '=', 1)]",
                "scope": "manager_full",
            },
        ]

        # 10. Set all enrichment keys on model
        new_model["has_approval"] = True
        new_model["approval_levels"] = levels
        new_model["approval_action_methods"] = action_methods
        new_model["approval_submit_action"] = submit_action
        new_model["approval_reject_action"] = reject_action
        new_model["approval_reset_action"] = reset_action
        new_model["approval_state_field_name"] = "state"
        new_model["lock_after"] = approval.get("lock_after", "draft")
        new_model["editable_fields"] = approval.get("editable_fields", [])
        new_model["on_reject"] = on_reject
        new_model["reject_allowed_from"] = reject_allowed_from
        new_model["approval_record_rules"] = record_rules
        new_model["needs_translate"] = True

        # FLAW-18: Escalation config (cron-driven auto-escalation)
        if escalation_configs:
            new_model["approval_escalation_configs"] = escalation_configs
            new_model["has_approval_escalation"] = True

        # 11. Add "approval" to override_sources["write"]
        sources = new_model.get("override_sources", {})
        write_set = set(sources.get("write", set()))
        write_set.add("approval")
        new_model["override_sources"] = {**sources, "write": write_set}
        new_model["has_write_override"] = True

        # 12. Add "approval" to record_rule_scopes
        existing_scopes = list(model.get("record_rule_scopes", []))
        if "approval" not in existing_scopes:
            existing_scopes.append("approval")
        new_model["record_rule_scopes"] = existing_scopes

        new_models.append(new_model)

    return {**spec, "models": new_models}
