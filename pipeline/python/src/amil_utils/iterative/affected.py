"""Diff-to-stage mapping for iterative refinement.

Provides:
- ``AffectedStages`` — frozen dataclass holding the set of affected
  pipeline stages and a human-readable diff summary.
- ``determine_affected_stages`` — classifies a ``SpecDiff`` into diff
  categories and unions the corresponding stage sets.

This is a **pure function** with no side effects.  All stage name sets
are validated against ``STAGE_NAMES`` from ``renderer.py`` plus the
virtual ``"stubs"`` stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from odoo_gen_utils.renderer import STAGE_NAMES

if TYPE_CHECKING:
    from odoo_gen_utils.spec_differ import SpecDiff

# ---------------------------------------------------------------------------
# Valid stage names (pipeline stages + virtual "stubs")
# ---------------------------------------------------------------------------

_VALID_STAGES: frozenset[str] = frozenset(STAGE_NAMES) | frozenset({"stubs"})

# ---------------------------------------------------------------------------
# Category-to-stages mapping (from CONTEXT.md table)
# ---------------------------------------------------------------------------

_CATEGORY_TO_STAGES: dict[str, frozenset[str]] = {
    "FIELD_ADDED": frozenset({"models", "views", "security", "tests", "stubs"}),
    "FIELD_REMOVED": frozenset({"models", "views", "security", "tests", "stubs"}),
    "FIELD_MODIFIED": frozenset({"models", "views", "stubs"}),
    "MODEL_ADDED": frozenset({"models", "views", "security", "tests", "manifest", "stubs"}),
    "MODEL_REMOVED": frozenset({"models", "views", "security", "tests", "manifest", "stubs"}),
    "METHOD_ADDED": frozenset({"stubs"}),
    "METHOD_REMOVED": frozenset({"stubs"}),
    "SECURITY_CHANGED": frozenset({"security"}),
    "APPROVAL_CHANGED": frozenset({"models", "views", "security", "stubs"}),
    "VIEW_HINT_CHANGED": frozenset({"views"}),
}

# Validate all mapped stages are valid
for _cat, _stages in _CATEGORY_TO_STAGES.items():
    _invalid = _stages - _VALID_STAGES
    assert not _invalid, f"Invalid stages {_invalid} in category {_cat}"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AffectedStages:
    """Immutable result of diff-to-stage mapping.

    Attributes:
        stages: Frozenset of pipeline stage names that need re-running.
        diff_summary: Human-readable summary of what changed, keyed by
            category (e.g. ``{"FIELD_ADDED": ["fee.invoice.discount"]}``).
    """

    stages: frozenset[str]
    diff_summary: dict[str, Any]


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------


def _classify_diff(
    spec_diff: "SpecDiff",
    old_spec: dict | None = None,
    new_spec: dict | None = None,
) -> tuple[set[str], dict[str, list[str]]]:
    """Classify a SpecDiff into diff categories and build a summary.

    When *old_spec* and *new_spec* are provided, also detects attribute-level
    model changes (view_hints, etc.) that ``spec_differ.diff_specs()`` does
    not track.

    Returns:
        Tuple of (category_set, summary_dict) where category_set is the
        set of matched category names and summary_dict maps each category
        to a list of human-readable descriptions.
    """
    categories: set[str] = set()
    summary: dict[str, list[str]] = {}
    changes = spec_diff.get("changes", {})
    models = changes.get("models", {})

    # --- Added models ---
    added_models = models.get("added", [])
    if added_models:
        categories.add("MODEL_ADDED")
        summary["MODEL_ADDED"] = [m["name"] for m in added_models]

    # --- Removed models ---
    removed_models = models.get("removed", [])
    if removed_models:
        categories.add("MODEL_REMOVED")
        summary["MODEL_REMOVED"] = [m["name"] for m in removed_models]

    # --- Modified models ---
    modified_models = models.get("modified", {})
    for model_name, model_changes in modified_models.items():
        # Field changes
        fields = model_changes.get("fields", {})

        added_fields = fields.get("added", [])
        if added_fields:
            categories.add("FIELD_ADDED")
            field_names = [f"{model_name}.{f['name']}" for f in added_fields]
            summary.setdefault("FIELD_ADDED", []).extend(field_names)

        removed_fields = fields.get("removed", [])
        if removed_fields:
            categories.add("FIELD_REMOVED")
            field_names = [f"{model_name}.{f['name']}" for f in removed_fields]
            summary.setdefault("FIELD_REMOVED", []).extend(field_names)

        modified_fields = fields.get("modified", [])
        if modified_fields:
            categories.add("FIELD_MODIFIED")
            field_names = [f"{model_name}.{f['name']}" for f in modified_fields]
            summary.setdefault("FIELD_MODIFIED", []).extend(field_names)

        # Security changes
        security = model_changes.get("security", {})
        if security:
            categories.add("SECURITY_CHANGED")
            sec_desc = []
            for key, val in security.items():
                sec_desc.append(f"{model_name}.{key}")
            summary.setdefault("SECURITY_CHANGED", []).extend(sec_desc)

        # Approval changes
        approval = model_changes.get("approval", {})
        if approval:
            categories.add("APPROVAL_CHANGED")
            approval_desc = []
            for key, val in approval.items():
                approval_desc.append(f"{model_name}.{key}")
            summary.setdefault("APPROVAL_CHANGED", []).extend(approval_desc)

    # --- Detect model-level attribute changes not tracked by spec_differ ---
    # spec_differ only compares: fields, security, approval, webhooks, constraints.
    # Attributes like view_hints, view_extensions, add_methods etc. are missed.
    # When raw specs are provided, detect these directly.
    _VIEW_HINT_ATTRS = frozenset({"view_hints", "view_extensions"})
    if old_spec is not None and new_spec is not None:
        old_models_by_name = {m["name"]: m for m in old_spec.get("models", [])}
        new_models_by_name = {m["name"]: m for m in new_spec.get("models", [])}
        common_models = set(old_models_by_name) & set(new_models_by_name)
        for model_name in common_models:
            old_m = old_models_by_name[model_name]
            new_m = new_models_by_name[model_name]
            for attr in _VIEW_HINT_ATTRS:
                if old_m.get(attr) != new_m.get(attr):
                    categories.add("VIEW_HINT_CHANGED")
                    summary.setdefault("VIEW_HINT_CHANGED", []).append(
                        f"{model_name}.{attr}"
                    )

    return categories, summary


def determine_affected_stages(
    spec_diff: "SpecDiff",
    old_spec: dict | None = None,
    new_spec: dict | None = None,
) -> AffectedStages:
    """Map a ``SpecDiff`` to the set of pipeline stages that need re-running.

    Classifies changes into diff categories (FIELD_ADDED, MODEL_REMOVED,
    SECURITY_CHANGED, etc.) and unions the stage sets for each category.

    When *old_spec* and *new_spec* are provided, also detects model-level
    attribute changes (view_hints, view_extensions) that ``spec_differ``
    does not track.

    Args:
        spec_diff: Output from ``diff_specs()`` or ``compute_spec_diff()``.
        old_spec: Optional raw old spec for detecting untracked attributes.
        new_spec: Optional raw new spec for detecting untracked attributes.

    Returns:
        ``AffectedStages`` with the union of all affected stages and a
        diff summary describing what changed.
    """
    categories, summary = _classify_diff(spec_diff, old_spec, new_spec)

    # Union all stage sets for matched categories
    all_stages: set[str] = set()
    for category in categories:
        stage_set = _CATEGORY_TO_STAGES.get(category, frozenset())
        all_stages.update(stage_set)

    return AffectedStages(
        stages=frozenset(all_stages),
        diff_summary=summary,
    )
