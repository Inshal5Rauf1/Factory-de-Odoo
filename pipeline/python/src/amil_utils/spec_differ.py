"""Spec differ module: compare two spec JSON versions and produce hierarchical change objects.

Provides:
- diff_specs(): Main entry point returning hierarchical diff with destructiveness
- format_human_summary(): Console-friendly output with +/-/~/! symbols
- SpecDiff: TypedDict for the diff result structure
- _spec_to_diffable(): Convert list-indexed spec to dict-indexed for stable paths
- _classify_destructiveness(): Classify changes by severity level
"""

from __future__ import annotations

import copy
import logging
from typing import Any, TypedDict

from deepdiff import DeepDiff

logger = logging.getLogger("odoo-gen.spec_differ")


# ---------------------------------------------------------------------------
# Type Definitions
# ---------------------------------------------------------------------------

class FieldChange(TypedDict, total=False):
    name: str
    type: str
    changes: dict[str, dict[str, Any]]
    destructive: bool
    severity: str


class FieldChanges(TypedDict, total=False):
    added: list[dict[str, Any]]
    removed: list[FieldChange]
    modified: list[FieldChange]


class ModelChange(TypedDict, total=False):
    name: str
    fields: list[dict[str, Any]] | FieldChanges
    destructive: bool


class ChangesModels(TypedDict, total=False):
    added: list[ModelChange]
    removed: list[ModelChange]
    modified: dict[str, dict]


class Changes(TypedDict, total=False):
    models: ChangesModels
    cron_jobs: dict
    reports: dict


class SpecDiff(TypedDict, total=False):
    module: str
    old_version: str
    new_version: str
    changes: Changes
    destructive_count: int
    warnings: list[str]
    migration_required: bool


# ---------------------------------------------------------------------------
# Destructiveness Classification
# ---------------------------------------------------------------------------

# Type transitions that always cause data loss
ALWAYS_DESTRUCTIVE_TYPE_CHANGES: frozenset[tuple[str, str]] = frozenset({
    ("Text", "Char"),
    ("Text", "Integer"),
    ("Float", "Integer"),
    ("Monetary", "Integer"),
    ("Many2one", "Char"),
    ("Char", "Many2one"),
    ("Selection", "Integer"),
    ("Boolean", "Many2one"),
    ("Monetary", "Char"),
    ("Many2one", "Integer"),
    ("Many2one", "Boolean"),
    ("Many2one", "Selection"),
    ("Many2many", "Char"),
    ("One2many", "Char"),
    ("Html", "Char"),
    ("Html", "Integer"),
    ("Binary", "Char"),
})

# Type transitions that widen data (safe)
TYPE_WIDENING: frozenset[tuple[str, str]] = frozenset({
    ("Char", "Text"),
    ("Integer", "Float"),
    ("Integer", "Monetary"),
    ("Char", "Html"),
    ("Boolean", "Integer"),
})

# Type transitions that may lose precision or have edge cases
POSSIBLY_DESTRUCTIVE_TYPE_CHANGES: frozenset[tuple[str, str]] = frozenset({
    ("Float", "Monetary"),
    ("Monetary", "Float"),
})

# Presentation-only attributes excluded from schema comparison
EXCLUDED_FIELD_ATTRIBUTES: frozenset[str] = frozenset({
    "string",
    "help",
    "placeholder",
})


def _classify_destructiveness(
    change_type: str, old_val: Any, new_val: Any, attribute: str
) -> str:
    """Classify a single change by destructiveness severity.

    Args:
        change_type: Category of change (e.g., "type", "required", "field_removed",
                     "field_added", "model_removed", "selection_removed",
                     "selection_added", "attribute").
        old_val: Previous value.
        new_val: New value.
        attribute: The attribute name being changed.

    Returns:
        One of: "always_destructive", "possibly_destructive", "non_destructive"
    """
    # Field or model removed
    if change_type in ("field_removed", "model_removed"):
        return "always_destructive"

    # Field or model added
    if change_type in ("field_added", "model_added"):
        return "non_destructive"

    # Type changes
    if change_type == "type" and attribute == "type":
        pair = (old_val, new_val)
        if pair in ALWAYS_DESTRUCTIVE_TYPE_CHANGES:
            return "always_destructive"
        if pair in TYPE_WIDENING:
            return "non_destructive"
        if pair in POSSIBLY_DESTRUCTIVE_TYPE_CHANGES:
            return "possibly_destructive"
        # Unknown type transition -- assume possibly destructive
        return "possibly_destructive"

    # Required false -> true
    if change_type == "required" and attribute == "required":
        if old_val is False and new_val is True:
            return "possibly_destructive"
        return "non_destructive"

    # Selection option changes
    if change_type == "selection_removed":
        return "possibly_destructive"
    if change_type == "selection_added":
        return "non_destructive"

    # Presentation-only attributes
    if attribute in EXCLUDED_FIELD_ATTRIBUTES:
        return "non_destructive"

    # Default: non-destructive for other attribute changes
    return "non_destructive"


# ---------------------------------------------------------------------------
# Spec Preprocessing
# ---------------------------------------------------------------------------

def _spec_to_diffable(spec: dict) -> dict:
    """Convert list-indexed spec to dict-indexed for stable deepdiff paths.

    Transforms:
    - spec['models'] from list to dict keyed by model name
    - Each model's 'fields' from list to dict keyed by field name
    - Each model's 'constraints' from list to dict keyed by constraint name
    - Each model's 'approval.levels' from list to dict keyed by level name
    - spec['cron_jobs'] from list to dict keyed by cron name
    - spec['reports'] from list to dict keyed by report name

    This eliminates deepdiff index instability (Pitfall 1 from RESEARCH.md).
    """
    result = {k: v for k, v in spec.items() if k not in ("models", "cron_jobs", "reports")}

    # Convert models list -> dict keyed by name
    models: dict[str, dict] = {}
    for model in spec.get("models", []):
        model_data = {k: v for k, v in model.items() if k not in ("name", "fields", "constraints")}

        # Convert fields list -> dict keyed by name
        fields: dict[str, dict] = {}
        for field in model.get("fields", []):
            field_data = {k: v for k, v in field.items() if k != "name"}
            fields[field["name"]] = field_data
        model_data["fields"] = fields

        # Convert constraints list -> dict keyed by name
        constraints_list = model.get("constraints", [])
        if constraints_list:
            constraints: dict[str, dict] = {}
            for c in constraints_list:
                constraints[c["name"]] = {k: v for k, v in c.items() if k != "name"}
            model_data["constraints"] = constraints

        # Convert approval levels list -> dict keyed by name
        approval = model.get("approval")
        if approval and "levels" in approval:
            levels_dict: dict[str, dict] = {}
            for level in approval["levels"]:
                levels_dict[level["name"]] = {k: v for k, v in level.items() if k != "name"}
            model_data["approval"] = {**approval, "levels": levels_dict}

        models[model["name"]] = model_data
    result["models"] = models

    # Convert cron_jobs list -> dict keyed by name
    cron_list = spec.get("cron_jobs", [])
    if cron_list:
        cron_dict: dict[str, dict] = {}
        for cj in cron_list:
            cron_dict[cj["name"]] = {k: v for k, v in cj.items() if k != "name"}
        result["cron_jobs"] = cron_dict

    # Convert reports list -> dict keyed by name
    reports_list = spec.get("reports", [])
    if reports_list:
        reports_dict: dict[str, dict] = {}
        for r in reports_list:
            reports_dict[r["name"]] = {k: v for k, v in r.items() if k != "name"}
        result["reports"] = reports_dict

    return result


# ---------------------------------------------------------------------------
# DeepDiff Translation
# ---------------------------------------------------------------------------

def _parse_path(path_str: str) -> list[str]:
    """Parse a deepdiff path string into components.

    Example: "root['models']['fee.invoice']['fields']['amount']['type']"
    Returns: ['models', 'fee.invoice', 'fields', 'amount', 'type']
    """
    parts: list[str] = []
    # Remove 'root' prefix
    remaining = path_str
    if remaining.startswith("root"):
        remaining = remaining[4:]

    while remaining:
        if remaining.startswith("['"):
            end = remaining.index("']", 2)
            parts.append(remaining[2:end])
            remaining = remaining[end + 2:]
        elif remaining.startswith("["):
            end = remaining.index("]", 1)
            parts.append(remaining[1:end])
            remaining = remaining[end + 1:]
        else:
            break

    return parts


def _selection_changes(old_selection: list, new_selection: list) -> dict:
    """Compute selection option changes.

    Returns dict with 'added' and 'removed' selection options.
    """
    old_keys = {opt[0] if isinstance(opt, list) else opt for opt in old_selection}
    new_keys = {opt[0] if isinstance(opt, list) else opt for opt in new_selection}

    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    return {"added": added, "removed": removed}


def _diff_field_attributes(
    old_field: dict, new_field: dict
) -> tuple[dict[str, dict[str, Any]], bool, str]:
    """Compare two field dicts and return changes with destructiveness.

    Returns:
        Tuple of (changes_dict, is_destructive, severity)
        changes_dict maps attribute -> {old, new}
    """
    changes: dict[str, dict[str, Any]] = {}
    max_severity = "non_destructive"

    # Attributes that affect schema/behavior
    schema_attributes = {
        "type", "required", "default", "compute", "store", "related",
        "comodel_name", "inverse_name", "groups", "index", "ondelete",
        "selection",
    }

    all_keys = set(old_field.keys()) | set(new_field.keys())
    for attr in all_keys:
        if attr in EXCLUDED_FIELD_ATTRIBUTES:
            continue
        if attr not in schema_attributes:
            continue

        old_val = old_field.get(attr)
        new_val = new_field.get(attr)

        if old_val == new_val:
            continue

        # Special handling for selection values
        if attr == "selection":
            if old_val is not None and new_val is not None:
                sel_changes = _selection_changes(old_val, new_val)
                if sel_changes["removed"]:
                    severity = _classify_destructiveness(
                        "selection_removed", old_val, new_val, "selection"
                    )
                    changes["selection"] = {
                        "old": old_val,
                        "new": new_val,
                        "options_added": sel_changes["added"],
                        "options_removed": sel_changes["removed"],
                    }
                elif sel_changes["added"]:
                    severity = _classify_destructiveness(
                        "selection_added", old_val, new_val, "selection"
                    )
                    changes["selection"] = {
                        "old": old_val,
                        "new": new_val,
                        "options_added": sel_changes["added"],
                        "options_removed": sel_changes["removed"],
                    }
                else:
                    severity = "non_destructive"
                    continue
            else:
                changes["selection"] = {"old": old_val, "new": new_val}
                severity = "non_destructive"
        elif attr == "type":
            severity = _classify_destructiveness("type", old_val, new_val, "type")
            changes["type"] = {"old": old_val, "new": new_val}
        elif attr == "required":
            severity = _classify_destructiveness("required", old_val, new_val, "required")
            changes["required"] = {"old": old_val, "new": new_val}
        else:
            severity = _classify_destructiveness("attribute", old_val, new_val, attr)
            changes[attr] = {"old": old_val, "new": new_val}

        # Track max severity
        if severity == "always_destructive":
            max_severity = "always_destructive"
        elif severity == "possibly_destructive" and max_severity != "always_destructive":
            max_severity = "possibly_destructive"

    is_destructive = max_severity in ("always_destructive", "possibly_destructive")
    return changes, is_destructive, max_severity


def _diff_models(old_diffable: dict, new_diffable: dict) -> tuple[ChangesModels, int, list[str]]:
    """Compute hierarchical model changes.

    Returns:
        Tuple of (changes_models, destructive_count, warnings)
    """
    old_models = old_diffable.get("models", {})
    new_models = new_diffable.get("models", {})

    added: list[ModelChange] = []
    removed: list[ModelChange] = []
    modified: dict[str, dict] = {}
    destructive_count = 0
    warnings: list[str] = []

    # Added models
    for name in sorted(set(new_models.keys()) - set(old_models.keys())):
        model_data = new_models[name]
        field_list = [
            {"name": fname, **fdata}
            for fname, fdata in model_data.get("fields", {}).items()
        ]
        added.append({"name": name, "fields": field_list, "destructive": False})

    # Removed models
    for name in sorted(set(old_models.keys()) - set(new_models.keys())):
        model_data = old_models[name]
        field_list = [
            {"name": fname, **fdata}
            for fname, fdata in model_data.get("fields", {}).items()
        ]
        removed.append({"name": name, "fields": field_list, "destructive": True})
        destructive_count += 1
        warnings.append(f"Model '{name}' removed -- ALWAYS DESTRUCTIVE")

    # Modified models
    for name in sorted(set(old_models.keys()) & set(new_models.keys())):
        old_model = old_models[name]
        new_model = new_models[name]

        model_changes: dict = {}
        has_changes = False

        # Compare fields
        old_fields = old_model.get("fields", {})
        new_fields = new_model.get("fields", {})

        added_fields: list[dict] = []
        removed_fields: list[FieldChange] = []
        modified_fields: list[FieldChange] = []

        # Added fields
        for fname in sorted(set(new_fields.keys()) - set(old_fields.keys())):
            fdata = new_fields[fname]
            added_fields.append({"name": fname, **fdata})

        # Removed fields
        for fname in sorted(set(old_fields.keys()) - set(new_fields.keys())):
            fdata = old_fields[fname]
            removed_fields.append({
                "name": fname,
                "type": fdata.get("type", "Unknown"),
                "destructive": True,
                "severity": "always_destructive",
            })
            destructive_count += 1
            warnings.append(f"Field '{name}.{fname}' removed -- ALWAYS DESTRUCTIVE")

        # Modified fields
        for fname in sorted(set(old_fields.keys()) & set(new_fields.keys())):
            changes, is_destructive, severity = _diff_field_attributes(
                old_fields[fname], new_fields[fname]
            )
            if changes:
                entry: FieldChange = {
                    "name": fname,
                    "type": new_fields[fname].get("type", old_fields[fname].get("type", "Unknown")),
                    "changes": changes,
                    "destructive": is_destructive,
                    "severity": severity,
                }
                modified_fields.append(entry)
                if is_destructive:
                    destructive_count += 1
                    label = "ALWAYS" if severity == "always_destructive" else "POSSIBLY"
                    warnings.append(
                        f"Field '{name}.{fname}' modified -- {label} DESTRUCTIVE"
                    )

        if added_fields or removed_fields or modified_fields:
            model_changes["fields"] = {
                "added": added_fields,
                "removed": removed_fields,
                "modified": modified_fields,
            }
            has_changes = True

        # Compare security
        old_security = old_model.get("security", {})
        new_security = new_model.get("security", {})
        if old_security != new_security:
            security_changes = _diff_security(old_security, new_security)
            if security_changes:
                model_changes["security"] = security_changes
                has_changes = True

        # Compare approval
        old_approval = old_model.get("approval", {})
        new_approval = new_model.get("approval", {})
        if old_approval != new_approval:
            approval_changes = _diff_approval(old_approval, new_approval)
            if approval_changes:
                model_changes["approval"] = approval_changes
                has_changes = True

        # Compare webhooks
        old_webhooks = old_model.get("webhooks", {})
        new_webhooks = new_model.get("webhooks", {})
        if old_webhooks != new_webhooks:
            webhook_changes = _diff_webhooks(old_webhooks, new_webhooks)
            if webhook_changes:
                model_changes["webhooks"] = webhook_changes
                has_changes = True

        # Compare constraints
        old_constraints = old_model.get("constraints", {})
        new_constraints = new_model.get("constraints", {})
        if old_constraints != new_constraints:
            constraint_changes = _diff_constraints(old_constraints, new_constraints)
            if constraint_changes:
                model_changes["constraints"] = constraint_changes
                has_changes = True

        if has_changes:
            modified[name] = model_changes

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
    }, destructive_count, warnings


def _diff_security(old: dict, new: dict) -> dict:
    """Diff security block: roles and ACL changes."""
    result: dict = {}

    old_roles = set(old.get("roles", []))
    new_roles = set(new.get("roles", []))

    added_roles = sorted(new_roles - old_roles)
    removed_roles = sorted(old_roles - new_roles)

    if added_roles:
        result["roles_added"] = added_roles
    if removed_roles:
        result["roles_removed"] = removed_roles

    old_acl = old.get("acl", {})
    new_acl = new.get("acl", {})
    if old_acl != new_acl:
        acl_changes: dict = {}
        for role in sorted(set(old_acl.keys()) | set(new_acl.keys())):
            old_perms = old_acl.get(role)
            new_perms = new_acl.get(role)
            if old_perms != new_perms:
                acl_changes[role] = {"old": old_perms, "new": new_perms}
        if acl_changes:
            result["acl_changed"] = acl_changes

    return result


def _diff_approval(old: dict, new: dict) -> dict:
    """Diff approval block: levels added/removed/modified."""
    result: dict = {}

    old_levels = old.get("levels", {})
    new_levels = new.get("levels", {})

    # If levels are still lists (shouldn't be after _spec_to_diffable), handle it
    if isinstance(old_levels, list):
        old_levels = {lv["name"]: {k: v for k, v in lv.items() if k != "name"} for lv in old_levels}
    if isinstance(new_levels, list):
        new_levels = {lv["name"]: {k: v for k, v in lv.items() if k != "name"} for lv in new_levels}

    added = sorted(set(new_levels.keys()) - set(old_levels.keys()))
    removed = sorted(set(old_levels.keys()) - set(new_levels.keys()))

    if added:
        result["levels_added"] = added
    if removed:
        result["levels_removed"] = removed

    # Modified levels
    modified: dict = {}
    for name in sorted(set(old_levels.keys()) & set(new_levels.keys())):
        if old_levels[name] != new_levels[name]:
            modified[name] = {"old": old_levels[name], "new": new_levels[name]}
    if modified:
        result["levels_modified"] = modified

    return result


def _diff_webhooks(old: dict, new: dict) -> dict:
    """Diff webhook block: watched_fields changes."""
    result: dict = {}

    old_watched = set(old.get("watched_fields", []))
    new_watched = set(new.get("watched_fields", []))

    if old_watched != new_watched:
        added = sorted(new_watched - old_watched)
        removed = sorted(old_watched - new_watched)
        result["watched_fields"] = {}
        if added:
            result["watched_fields"]["added"] = added
        if removed:
            result["watched_fields"]["removed"] = removed

    return result


def _diff_constraints(old: dict, new: dict) -> dict:
    """Diff constraints: added/removed/modified."""
    result: dict = {}

    added_names = sorted(set(new.keys()) - set(old.keys()))
    removed_names = sorted(set(old.keys()) - set(new.keys()))

    if added_names:
        result["added"] = [{"name": n, **new[n]} for n in added_names]
    if removed_names:
        result["removed"] = [{"name": n, **old[n]} for n in removed_names]

    # Modified
    modified: dict = {}
    for name in sorted(set(old.keys()) & set(new.keys())):
        if old[name] != new[name]:
            modified[name] = {"old": old[name], "new": new[name]}
    if modified:
        result["modified"] = modified

    return result


def _diff_cron_jobs(old_diffable: dict, new_diffable: dict) -> dict:
    """Diff cron jobs: added/removed/modified."""
    old_crons = old_diffable.get("cron_jobs", {})
    new_crons = new_diffable.get("cron_jobs", {})
    result: dict = {}

    added = sorted(set(new_crons.keys()) - set(old_crons.keys()))
    removed = sorted(set(old_crons.keys()) - set(new_crons.keys()))

    if added:
        result["added"] = [{"name": n, **new_crons[n]} for n in added]
    if removed:
        result["removed"] = [{"name": n, **old_crons[n]} for n in removed]

    modified: dict = {}
    for name in sorted(set(old_crons.keys()) & set(new_crons.keys())):
        if old_crons[name] != new_crons[name]:
            changes: dict = {}
            for key in set(old_crons[name].keys()) | set(new_crons[name].keys()):
                old_val = old_crons[name].get(key)
                new_val = new_crons[name].get(key)
                if old_val != new_val:
                    changes[key] = {"old": old_val, "new": new_val}
            modified[name] = changes
    if modified:
        result["modified"] = modified

    return result


def _diff_reports(old_diffable: dict, new_diffable: dict) -> dict:
    """Diff reports: added/removed."""
    old_reports = old_diffable.get("reports", {})
    new_reports = new_diffable.get("reports", {})
    result: dict = {}

    added = sorted(set(new_reports.keys()) - set(old_reports.keys()))
    removed = sorted(set(old_reports.keys()) - set(new_reports.keys()))

    if added:
        result["added"] = [{"name": n, **new_reports[n]} for n in added]
    if removed:
        result["removed"] = [{"name": n, **old_reports[n]} for n in removed]

    return result


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def diff_specs(old_spec: dict, new_spec: dict) -> SpecDiff:
    """Compare two spec versions and produce hierarchical change objects.

    Uses deepcopy on inputs to guarantee pure function behavior.
    Converts specs to dict-indexed form for stable comparison paths.

    Args:
        old_spec: The previous spec version.
        new_spec: The new spec version.

    Returns:
        SpecDiff with keys: module, old_version, new_version, changes,
        destructive_count, warnings, migration_required.
    """
    # Deep copy inputs to guarantee pure function
    old = copy.deepcopy(old_spec)
    new = copy.deepcopy(new_spec)

    # Convert to diffable format
    old_diffable = _spec_to_diffable(old)
    new_diffable = _spec_to_diffable(new)

    # Diff models
    models_changes, destructive_count, warnings = _diff_models(old_diffable, new_diffable)

    # Diff cron jobs
    cron_changes = _diff_cron_jobs(old_diffable, new_diffable)

    # Diff reports
    report_changes = _diff_reports(old_diffable, new_diffable)

    changes: Changes = {
        "models": models_changes,
    }
    if cron_changes:
        changes["cron_jobs"] = cron_changes
    if report_changes:
        changes["reports"] = report_changes

    migration_required = destructive_count > 0
    logger.info(
        "Diff complete for module '%s': %d destructive change(s), migration %s",
        old_spec.get("module_name", "unknown"),
        destructive_count,
        "required" if migration_required else "not required",
    )

    return {
        "module": old_spec.get("module_name", "unknown"),
        "old_version": old_spec.get("version", "unknown"),
        "new_version": new_spec.get("version", "unknown"),
        "changes": changes,
        "destructive_count": destructive_count,
        "warnings": warnings,
        "migration_required": migration_required,
    }


# ---------------------------------------------------------------------------
# Human-Readable Formatting
# ---------------------------------------------------------------------------

def format_human_summary(diff_result: SpecDiff) -> str:
    """Format a diff result for console output.

    Uses symbols: + added, - removed, ~ modified, ! destructive.
    Includes warning count footer when destructive changes exist.

    Args:
        diff_result: Output from diff_specs().

    Returns:
        Formatted multi-line string.
    """
    lines: list[str] = []

    module = diff_result.get("module", "unknown")
    old_ver = diff_result.get("old_version", "?")
    new_ver = diff_result.get("new_version", "?")
    lines.append(f"{module} {old_ver} -> {new_ver}")

    changes = diff_result.get("changes", {})
    models = changes.get("models", {})

    # Added models
    for model in models.get("added", []):
        lines.append(f"  + {model['name']} (NEW MODEL)")
        for field in model.get("fields", []):
            fname = field.get("name", field) if isinstance(field, dict) else field
            ftype = field.get("type", "") if isinstance(field, dict) else ""
            lines.append(f"      + {fname} ({ftype})" if ftype else f"      + {fname}")

    # Removed models
    for model in models.get("removed", []):
        lines.append(f"  - {model['name']} (REMOVED) -- DESTRUCTIVE")

    # Modified models
    for name, model_data in models.get("modified", {}).items():
        lines.append(f"  ~ {name}:")
        fields = model_data.get("fields", {})

        for field in fields.get("added", []):
            ftype = field.get("type", "")
            lines.append(f"      + {field['name']} ({ftype})" if ftype else f"      + {field['name']}")

        for field in fields.get("removed", []):
            ftype = field.get("type", "Unknown")
            lines.append(f"      - {field['name']} ({ftype}) -- DESTRUCTIVE")

        for field in fields.get("modified", []):
            change_parts: list[str] = []
            for attr, vals in field.get("changes", {}).items():
                if isinstance(vals, dict) and "old" in vals and "new" in vals:
                    change_parts.append(f"{attr}: {vals['old']} -> {vals['new']}")

            change_str = ", ".join(change_parts)
            if field.get("destructive"):
                lines.append(f"      ! {field['name']}: {change_str} -- DESTRUCTIVE")
            else:
                lines.append(f"      ~ {field['name']}: {change_str}")

        # Security changes
        security = model_data.get("security", {})
        if security:
            for role in security.get("roles_added", []):
                lines.append(f"    SECURITY: + role: {role}")
            for role in security.get("roles_removed", []):
                lines.append(f"    SECURITY: - role: {role}")

        # Approval changes
        approval = model_data.get("approval", {})
        if approval:
            for level in approval.get("levels_added", []):
                lines.append(f"    APPROVAL: + level: {level}")
            for level in approval.get("levels_removed", []):
                lines.append(f"    APPROVAL: - level: {level}")

        # Webhook changes
        webhooks = model_data.get("webhooks", {})
        if webhooks:
            wf = webhooks.get("watched_fields", {})
            for field_name in wf.get("added", []):
                lines.append(f"    WEBHOOKS: + watched: {field_name}")
            for field_name in wf.get("removed", []):
                lines.append(f"    WEBHOOKS: - watched: {field_name}")

        # Constraint changes
        constraints = model_data.get("constraints", {})
        if constraints:
            for c in constraints.get("added", []):
                cname = c["name"] if isinstance(c, dict) else c
                lines.append(f"    CONSTRAINTS: + {cname}")
            for c in constraints.get("removed", []):
                cname = c["name"] if isinstance(c, dict) else c
                lines.append(f"    CONSTRAINTS: - {cname}")

    # Cron job changes
    cron = changes.get("cron_jobs", {})
    if cron:
        lines.append("CRON JOBS:")
        for item in cron.get("added", []):
            lines.append(f"  + {item['name']}")
        for item in cron.get("removed", []):
            lines.append(f"  - {item['name']}")
        for name, cron_changes in cron.get("modified", {}).items():
            parts = []
            for attr, vals in cron_changes.items():
                if isinstance(vals, dict) and "old" in vals and "new" in vals:
                    parts.append(f"{attr}: {vals['old']} -> {vals['new']}")
            lines.append(f"  ~ {name}: {', '.join(parts)}")

    # Report changes
    reports = changes.get("reports", {})
    if reports:
        lines.append("REPORTS:")
        for item in reports.get("added", []):
            lines.append(f"  + {item['name']}")
        for item in reports.get("removed", []):
            lines.append(f"  - {item['name']}")

    # Warning footer
    destructive_count = diff_result.get("destructive_count", 0)
    if destructive_count > 0:
        lines.append(
            f"-- {destructive_count} destructive change{'s' if destructive_count != 1 else ''}"
            " -- review migration script carefully"
        )

    return "\n".join(lines)
