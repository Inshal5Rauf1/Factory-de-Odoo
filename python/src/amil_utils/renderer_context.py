"""Context builders for Jinja2 rendering of Odoo module templates.

Extracted from renderer.py -- builds model-level and module-level template
contexts consumed by the render stage functions.
"""

from __future__ import annotations

import re
from typing import Any

from amil_utils.renderer_utils import (
    _is_monetary_field,
    _to_class,
    _to_python_var,
    _to_xml_id,
    _topologically_sort_fields,
    SEQUENCE_FIELD_NAMES,
)

# PIPE-07: Module-level constant for Odoo version-conditional model renames.
_VERSION_GATES: dict[str, dict[str, str]] = {
    "18.0": {
        "mail.channel": "discuss.channel",
        "mail.channel_all_employees": "discuss.channel_general",
    },
    "19.0": {
        "mail.channel": "discuss.channel",
        "mail.channel_all_employees": "discuss.channel_general",
        # Add any 19.0-specific renames here
    },
}


# NEW-07: Known external Python packages mapping (pip_name -> import_name).
EXTERNAL_PACKAGES: dict[str, str] = {
    "openpyxl": "openpyxl",
    "requests": "requests",
    "boto3": "boto3",
    "paramiko": "paramiko",
    "pdfplumber": "pdfplumber",
    "xlsxwriter": "xlsxwriter",
    "phonenumbers": "phonenumbers",
    "cryptography": "cryptography",
    "Pillow": "PIL",
    "python-dateutil": "dateutil",
    "pytz": "pytz",
    "num2words": "num2words",
    "python-barcode": "barcode",
}


def _detect_external_dependencies(spec: dict[str, Any]) -> list[str]:
    """Scan model fields and method code for references to known external packages.

    Returns a deduplicated sorted list of pip package names that should be
    declared in the manifest's external_dependencies.python.
    """
    # Build a reverse mapping: import_name -> pip_name
    import_to_pip = {v: k for k, v in EXTERNAL_PACKAGES.items()}

    detected: set[str] = set()
    text_corpus: list[str] = []

    for model in spec.get("models", []):
        for field in model.get("fields", []):
            # Check field compute code, defaults, etc.
            for key in ("compute", "default", "onchange"):
                val = field.get(key, "")
                if val:
                    text_corpus.append(str(val))

        # Check complex_constraints, business_rules body text
        for cc in model.get("complex_constraints", []):
            body = cc.get("check_body", "")
            if body:
                text_corpus.append(body)

    # Check module-level business_rules
    for rule in spec.get("business_rules", []):
        text_corpus.append(str(rule))

    # Scan the text corpus for import references
    full_text = " ".join(text_corpus)
    for import_name, pip_name in import_to_pip.items():
        if import_name in full_text:
            detected.add(pip_name)

    # Also check if import_export is used (needs openpyxl)
    if any(m.get("import_export") for m in spec.get("models", [])):
        detected.add("openpyxl")

    # Check if archival models exist (needs python-dateutil)
    if any(m.get("is_archival") or m.get("archival") for m in spec.get("models", [])):
        detected.add("python-dateutil")

    return sorted(detected)


def _build_base_context(spec: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    """Build base context: module metadata, model identity, and basic field lists."""
    module_name = spec.get("module_name", "")
    fields = model.get("fields", [])

    # BUG-04: Wire sensitive flag to groups attribute
    for f in fields:
        if f.get("sensitive") and not f.get("groups"):
            f["groups"] = f"{module_name}.group_{module_name}_manager"

    return {
        "module_name": spec["module_name"],
        "module_title": spec.get("module_title", spec["module_name"].replace("_", " ").title()),
        "summary": spec.get("summary", ""),
        "author": spec.get("author", ""),
        "website": spec.get("website", ""),
        "license": spec.get("license", "LGPL-3"),
        "category": spec.get("category", "Uncategorized"),
        "odoo_version": spec.get("odoo_version", "19.0"),
        "depends": spec.get("depends", ["base"]),
        "application": spec.get("application", True),
        "models": spec.get("models", []),
        "model_name": model["name"],
        "model_description": model.get("description", model["name"]),
        "model_var": _to_python_var(model["name"]),
        "model_xml_id": _to_xml_id(model["name"]),
        "fields": fields,
        "required_fields": [f for f in fields if f.get("required")],
        "sql_constraints": model.get("sql_constraints", []),
        "inherit": model.get("inherit"),
        "wizards": spec.get("wizards", []),
        # Phase 33 keys
        "model_order": model.get("model_order", ""),
        "is_transient": model.get("transient", False),
        "transient_max_hours": model.get("transient_max_hours"),
        "transient_max_count": model.get("transient_max_count"),
        # Integration keys
        "model_workflow": next(
            (w for w in spec.get("workflow", [])
             if isinstance(w, dict) and w.get("model") == model["name"]),
            None,
        ),
        "composite_indexes": model.get("composite_indexes", []),
    }


def _build_field_context(model: dict[str, Any], fields: list[dict[str, Any]]) -> dict[str, Any]:
    """Build field-analysis context: computed, constrained, sequence, monetary, etc."""
    computed_fields = [f for f in fields if f.get("compute")]
    if len(computed_fields) > 1:
        computed_fields = _topologically_sort_fields(computed_fields)
    onchange_fields = [f for f in fields if f.get("onchange")]
    constrained_fields = [f for f in fields if f.get("constrains")]
    sequence_fields = [
        f for f in fields
        if f.get("type") == "Char"
        and f.get("name") in SEQUENCE_FIELD_NAMES
        and f.get("required")
    ]
    state_field = next(
        (f for f in fields
         if f.get("name") in ("state", "status") and f.get("type") == "Selection"),
        None,
    )

    # Phase 26: monetary field detection (immutable rewrite)
    has_monetary = any(_is_monetary_field(f) for f in fields)
    if has_monetary:
        fields = [
            {**f, "type": "Monetary"} if _is_monetary_field(f) and f.get("type") == "Float" else f
            for f in fields
        ]
    has_currency_id = any(f.get("name") == "currency_id" for f in fields)

    # Phase 6: multi-company field detection
    has_company_field = any(
        f.get("name") == "company_id" and f.get("type") == "Many2one"
        for f in fields
    )

    # Phase 29: complex constraints from preprocessor
    complex_constraints = model.get("complex_constraints", [])
    has_constraints = any(
        f.get("constraints") for f in fields
    ) or bool(model.get("sql_constraints")) or bool(complex_constraints)

    return {
        "fields": fields,  # may be updated with monetary rewrites
        "computed_fields": computed_fields,
        "onchange_fields": onchange_fields,
        "constrained_fields": constrained_fields,
        "sequence_fields": sequence_fields,
        "sequence_field_names": list(SEQUENCE_FIELD_NAMES),
        "state_field": state_field,
        "has_computed": bool(computed_fields),
        "has_sequence_fields": bool(sequence_fields),
        "has_company_field": has_company_field,
        "workflow_states": model.get("workflow_states", []),
        "needs_currency_id": has_monetary and not has_currency_id,
        "has_constraints": has_constraints,
        "complex_constraints": complex_constraints,
        "create_constraints": model.get("create_constraints", []),
        "write_constraints": model.get("write_constraints", []),
        "has_create_override": bool(model.get("override_sources", {}).get("create")),
        "has_write_override": bool(model.get("override_sources", {}).get("write")),
    }


def _build_workflow_context(
    spec: dict[str, Any], model: dict[str, Any], fields: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build inheritance and chatter context: mail.thread injection, hierarchy."""
    explicit_inherit = model.get("inherit")
    if isinstance(explicit_inherit, list):
        inherit_list = list(explicit_inherit)
    elif explicit_inherit:
        inherit_list = [explicit_inherit]
    else:
        inherit_list = []

    module_model_names = {m["name"] for m in spec.get("models", [])}

    is_line_item = any(
        f.get("type") == "Many2one"
        and f.get("required")
        and f.get("comodel_name") in module_model_names
        and f.get("name", "").endswith("_id")
        for f in fields
    )

    chatter = model.get("chatter")
    if chatter is None:
        chatter = not is_line_item

    if isinstance(explicit_inherit, list):
        parent_is_in_module = any(inh in module_model_names for inh in explicit_inherit)
    elif explicit_inherit:
        parent_is_in_module = explicit_inherit in module_model_names
    else:
        parent_is_in_module = False

    if chatter and "mail" in spec.get("depends", []) and not parent_is_in_module:
        for mixin in ("mail.thread", "mail.activity.mixin"):
            if mixin not in inherit_list:
                inherit_list.append(mixin)

    # Phase 27: hierarchical model detection
    is_hierarchical = model.get("hierarchical", False)
    if is_hierarchical:
        field_names_set = {f.get("name") for f in fields}
        hierarchical_injections: list[dict[str, Any]] = []
        if "parent_id" not in field_names_set:
            hierarchical_injections.append({
                "name": "parent_id", "type": "Many2one",
                "comodel_name": model["name"], "string": "Parent",
                "index": True, "ondelete": "cascade",
            })
        if "child_ids" not in field_names_set:
            hierarchical_injections.append({
                "name": "child_ids", "type": "One2many",
                "comodel_name": model["name"], "inverse_name": "parent_id",
                "string": "Children",
            })
        if "parent_path" not in field_names_set:
            hierarchical_injections.append({
                "name": "parent_path", "type": "Char",
                "index": True, "internal": True,
            })
        if hierarchical_injections:
            fields = [*fields, *hierarchical_injections]

    view_fields = [f for f in fields if not f.get("internal")]

    return {
        "fields": fields,  # may be extended with hierarchy injections
        "chatter": chatter,
        "inherit_list": inherit_list,
        "is_hierarchical": is_hierarchical,
        "view_fields": view_fields,
    }


def _build_approval_context(model: dict[str, Any]) -> dict[str, Any]:
    """Build approval workflow context keys."""
    return {
        "has_approval": model.get("has_approval", False),
        "approval_levels": model.get("approval_levels", []),
        "approval_action_methods": model.get("approval_action_methods", []),
        "approval_submit_action": model.get("approval_submit_action", None),
        "approval_reject_action": model.get("approval_reject_action", None),
        "approval_reset_action": model.get("approval_reset_action", None),
        "approval_state_field_name": model.get("approval_state_field_name", "state"),
        "lock_after": model.get("lock_after", "draft"),
        "editable_fields": model.get("editable_fields", []),
        "approval_record_rules": model.get("approval_record_rules", []),
        "on_reject": model.get("on_reject", "draft"),
        "reject_allowed_from": model.get("reject_allowed_from", []),
    }


def _build_audit_context(model: dict[str, Any]) -> dict[str, Any]:
    """Build audit trail context keys."""
    audit_fields = model.get("audit_fields", [])
    return {
        "has_audit": model.get("has_audit", False),
        "audit_fields": audit_fields,
        "audit_field_names": {f["name"] for f in audit_fields},
        "audit_exclude": model.get("audit_exclude", []),
    }


def _build_webhook_context(model: dict[str, Any]) -> dict[str, Any]:
    """Build webhook and notification context keys."""
    webhook_watched_fields = model.get("webhook_watched_fields", [])
    return {
        "has_notifications": model.get("has_notifications", False),
        "notification_templates": model.get("notification_templates", []),
        "needs_logger": model.get("needs_logger", False),
        "has_webhooks": model.get("has_webhooks", False),
        "webhook_config": model.get("webhook_config", None),
        "webhook_watched_fields": webhook_watched_fields,
        "webhook_on_create": model.get("webhook_on_create", False),
        "webhook_on_write": bool(webhook_watched_fields),
        "webhook_on_unlink": model.get("webhook_on_unlink", False),
    }


def _build_document_context(
    spec: dict[str, Any], model: dict[str, Any], complex_constraints: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build document verification/versioning context keys."""
    has_document_verification = model.get("has_document_verification", False)
    document_verification_actions: list[dict[str, Any]] = model.get(
        "document_verification_actions", []
    )
    if has_document_verification and not document_verification_actions:
        module_name = spec.get("module_name", "module")
        _doc_action_map = {
            "doc_action_verify": {
                "name": "doc_action_verify", "button_label": "Verify",
                "button_class": "btn-primary", "visible_when": "pending",
                "group_xml_id": f"group_{module_name}_verifier",
            },
            "doc_action_reject": {
                "name": "doc_action_reject", "button_label": "Reject",
                "button_class": "btn-danger", "visible_when": "pending",
                "group_xml_id": f"group_{module_name}_verifier",
            },
            "doc_action_reset": {
                "name": "doc_action_reset", "button_label": "Reset to Pending",
                "button_class": "btn-secondary", "visible_when": "rejected",
                "group_xml_id": f"group_{module_name}_manager",
            },
        }
        for cc in complex_constraints:
            cc_name = cc.get("name", "")
            if cc_name in _doc_action_map:
                document_verification_actions.append(_doc_action_map[cc_name])

    return {
        "has_document_verification": has_document_verification,
        "document_verification_actions": document_verification_actions,
        "has_document_versioning": model.get("has_document_versioning", False),
        "document_version_action": model.get("document_version_action", None),
    }


def _build_performance_context(
    spec: dict[str, Any], model: dict[str, Any], cron_methods: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build caching, archival, bulk, reporting, and dashboard context keys."""
    is_archival = model.get("is_archival", False)
    if is_archival:
        cron_methods = [c for c in cron_methods if c.get("method") != "_cron_archive_old_records"]

    has_dashboard = any(
        d.get("model_name") == model["name"]
        for d in spec.get("dashboards", [])
    )
    has_kanban = any(
        (d.get("kanban") or d.get("kanban_fields"))
        and d.get("model_name") == model["name"]
        for d in spec.get("dashboards", [])
    )
    model_reports = [
        r for r in spec.get("reports", [])
        if r.get("model_name") == model["name"]
    ]

    return {
        "cron_methods": cron_methods,
        "model_reports": model_reports,
        "has_dashboard": has_dashboard,
        "has_kanban": has_kanban,
        "is_bulk": model.get("is_bulk", False),
        "bulk_post_processing_batch_size": model.get("bulk_post_processing_batch_size"),
        "is_cacheable": model.get("is_cacheable", False),
        "cache_lookup_field": model.get("cache_lookup_field", "name"),
        "needs_tools": model.get("needs_tools", False),
        "is_archival": is_archival,
        "archival_batch_size": model.get("archival_batch_size", 100),
        "archival_days": model.get("archival_days", 365),
    }


def _compute_needs_api_and_translate(ctx: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    """Compute cross-cutting needs_api and needs_translate flags from assembled context."""
    complex_constraints = ctx["complex_constraints"]
    needs_translate = bool(complex_constraints)

    if ctx.get("has_approval") or ctx.get("has_document_verification"):
        needs_translate = True

    has_temporal = any(c.get("type") == "temporal" for c in complex_constraints)
    has_domain_constraints = any(
        c.get("type", "").startswith("pk_")
        or c.get("type", "").startswith("ac_year_")
        or c.get("type", "").startswith("ac_term_")
        or c.get("type", "").startswith("doc_file_")
        for c in complex_constraints
    )
    needs_api = bool(
        ctx["computed_fields"] or ctx["onchange_fields"] or ctx["constrained_fields"]
        or ctx["sequence_fields"] or has_temporal or ctx["has_create_override"]
        or ctx["cron_methods"] or ctx.get("is_bulk") or ctx.get("is_cacheable")
        or ctx.get("is_archival") or ctx.get("has_audit") or has_domain_constraints
    )

    return {"needs_api": needs_api, "needs_translate": needs_translate}




def _auto_display_name_pattern(fields: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Determine a display_name_pattern for models without a 'name' field.

    Returns (pattern, depends_fields) or ("", []) if no suitable pattern found.

    Strategy:
    1. Look for a 'reference' field -> use "{reference}" or "[{reference}] {first_char}"
    2. Otherwise use the first Char field -> "{first_char}"
    3. Fallback -> "#{id}"
    """
    field_names = {f.get("name") for f in fields}
    has_name = "name" in field_names

    if has_name:
        return ("", [])

    # Find reference field
    reference_field = next(
        (f for f in fields if f.get("name") == "reference" and f.get("type") == "Char"),
        None,
    )

    # Find first Char field (excluding reference, internal, parent_path)
    skip_names = {"reference", "parent_path"}
    first_char = next(
        (f for f in fields
         if f.get("type") == "Char"
         and f.get("name") not in skip_names
         and not f.get("internal")),
        None,
    )

    if reference_field and first_char:
        pattern = "[{" + reference_field["name"] + "}] {" + first_char["name"] + "}"
        return (pattern, [reference_field["name"], first_char["name"]])

    if reference_field:
        pattern = "{" + reference_field["name"] + "}"
        return (pattern, [reference_field["name"]])

    if first_char:
        pattern = "{" + first_char["name"] + "}"
        return (pattern, [first_char["name"]])

    # No suitable field — skip auto display_name (Odoo's default is fine)
    return ("", [])

def _build_model_context(spec: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    """Build the template context for a single model from the module spec.

    PIPE-02: Delegates to focused sub-builders, then merges results.
    Order matters: field_ctx may update 'fields', workflow_ctx may extend it further.
    """
    ctx: dict[str, Any] = {}

    ctx.update(_build_base_context(spec, model))
    ctx.update(_build_field_context(model, ctx["fields"]))
    # workflow_ctx may extend fields (hierarchy injections) — use updated fields
    ctx.update(_build_workflow_context(spec, model, ctx["fields"]))
    ctx.update(_build_approval_context(model))
    ctx.update(_build_audit_context(model))
    ctx.update(_build_webhook_context(model))
    ctx.update(_build_document_context(spec, model, ctx["complex_constraints"]))

    cron_methods = [
        c for c in spec.get("cron_jobs", [])
        if c.get("model_name") == model["name"]
    ]
    ctx.update(_build_performance_context(spec, model, cron_methods))
    ctx.update(_compute_needs_api_and_translate(ctx, model))

    # TMPL-01: Related count stat buttons
    related_counts = model.get("related_counts", [])
    for rc in related_counts:
        ctx["computed_fields"].append({
            "name": rc["field"],
            "type": "Integer",
            "compute": f"_compute_{rc['field']}",
            "string": rc.get("label") or rc["field"].replace("_count", "").replace("_", " ").title(),
            "store": False,
        })
    ctx["related_counts"] = related_counts

    # TMPL-05: display_name_pattern -> _compute_display_name
    if pattern := model.get("display_name_pattern"):
        depends_fields = re.findall(r'\{(\w+)\}', pattern)
        ctx["display_name_pattern"] = pattern
        ctx["display_name_depends"] = depends_fields
    elif spec.get("odoo_version", "19.0") >= "19.0":
        # NEW-04: Auto _compute_display_name for nameless models (Odoo 19.0+)
        auto_pattern, auto_depends = _auto_display_name_pattern(ctx["fields"])
        if auto_pattern:
            ctx["display_name_pattern"] = auto_pattern
            ctx["display_name_depends"] = auto_depends

    return ctx


def _build_extension_context(
    spec: dict[str, Any], extension: dict[str, Any]
) -> dict[str, Any]:
    """Build template context for a single extension model (_inherit).

    Args:
        spec: Full module specification dictionary (preprocessed).
        extension: Single extension dict from spec["extends"].

    Returns:
        Context dictionary suitable for rendering extension_model.py.j2.
    """
    base_model = extension["base_model"]
    base_model_var = _to_python_var(base_model)
    class_name = _to_class(base_model)
    module_name = spec.get("module_name", "")

    fields = extension.get("add_fields", [])
    computed_fields = extension.get("add_computed", [])
    methods = extension.get("add_methods", [])

    # Build SQL constraints from add_constraints
    sql_constraints: list[dict[str, Any]] = []
    for constraint in extension.get("add_constraints", []):
        c_type = constraint.get("type", "check")
        c_fields = constraint.get("fields", [])
        c_name = constraint.get("name", "")
        c_rule = constraint.get("rule", "")

        if c_type == "unique":
            definition = f"UNIQUE({', '.join(c_fields)})"
        else:
            definition = f"CHECK({', '.join(c_fields)})"

        sql_constraints.append({
            "name": c_name,
            "definition": definition,
            "message": c_rule,
        })

    needs_api = bool(computed_fields or methods)

    return {
        "module_name": module_name,
        "base_model": base_model,
        "base_model_var": base_model_var,
        "class_name": class_name,
        "fields": fields,
        "computed_fields": computed_fields,
        "sql_constraints": sql_constraints,
        "methods": methods,
        "needs_api": needs_api,
    }


def _build_extension_view_context(
    spec: dict[str, Any],
    extension: dict[str, Any],
    view_ext: dict[str, Any],
) -> dict[str, Any]:
    """Build template context for a single extension view (xpath inheritance).

    Args:
        spec: Full module specification dictionary (preprocessed).
        extension: Single extension dict from spec["extends"].
        view_ext: Single view_extension dict from extension["view_extensions"].

    Returns:
        Context dictionary suitable for rendering extension_views.xml.j2.
    """
    base_model = extension["base_model"]
    base_model_var = _to_python_var(base_model)
    module_name = spec.get("module_name", "")
    base_view = view_ext.get("base_view", "")

    # Infer view_type from base_view suffix: "_form" -> "form", "_tree" -> "tree"
    view_type = "form"  # default
    for suffix in ("_form", "_tree", "_search", "_kanban", "_graph", "_pivot"):
        if suffix in base_view:
            view_type = suffix.lstrip("_")
            break

    view_record_id = f"view_{base_model_var}_{view_type}_inherit_{module_name}"
    view_name = f"{base_model}.{view_type}.inherit.{module_name}"
    inherit_id_ref = base_view

    # Process insertions
    insertions: list[dict[str, Any]] = []
    for ins in view_ext.get("insertions", []):
        if hasattr(ins, "model_dump"):
            ins_dict = ins.model_dump(exclude_none=True)
        else:
            ins_dict = dict(ins)
        insertions.append({
            "xpath": ins_dict.get("xpath", ""),
            "position": ins_dict.get("position", "after"),
            "fields": ins_dict.get("fields", []),
            "content": ins_dict.get("content"),
            "page_name": ins_dict.get("page_name"),
            "page_string": ins_dict.get("page_string"),
        })

    return {
        "module_name": module_name,
        "base_model": base_model,
        "model_name": base_model,
        "view_record_id": view_record_id,
        "view_name": view_name,
        "inherit_id_ref": inherit_id_ref,
        "insertions": insertions,
    }


def _compute_manifest_data(
    spec: dict[str, Any],
    data_files: list[str],
    wizard_view_files: list[str],
    has_company_modules: bool = False,
) -> list[str]:
    """Compute the canonical manifest data file list.

    Canonical load order:
    1. security/security.xml (groups, categories)
    2. security/ir.model.access.csv (ACLs reference groups)
    3. security/record_rules.xml (only if has_company_modules)
    4. data files (sequences, data, cron, reports, mail templates)
    5. wizard view files (define wizard actions — BEFORE model views)
    6. per-model view files (*_views.xml, *_action.xml — may reference wizard actions)
    7. dashboard view files (graph, pivot, kanban, cohort)
    8. views/menu.xml (references all actions — LAST)

    Args:
        spec: Full module specification dictionary.
        data_files: List of data file paths relative to module root (e.g., ["data/sequences.xml"]).
        wizard_view_files: List of wizard view file paths (e.g., ["views/confirm_wizard_wizard_form.xml"]).
        has_company_modules: Whether any model has a company_id Many2one field.

    Returns:
        Ordered list of file paths for the manifest data section.
    """
    manifest_files: list[str] = [
        "security/security.xml",
        "security/ir.model.access.csv",
    ]
    if has_company_modules:
        manifest_files.append("security/record_rules.xml")

    manifest_files.extend(data_files)

    # Phase 40: mail template data file (after data files, before views)
    if any(m.get("has_notifications") for m in spec.get("models", [])):
        manifest_files.append("data/mail_template_data.xml")

    # Wizard views define ir.actions.act_window records that model views
    # may reference via %(module.wizard_action_id)d in button definitions.
    # They MUST be loaded before model views to avoid External ID errors.
    manifest_files.extend(wizard_view_files)

    for model in spec.get("models", []):
        model_var = _to_python_var(model["name"])
        manifest_files.append(f"views/{model_var}_views.xml")
        manifest_files.append(f"views/{model_var}_action.xml")

    # Phase 31: dashboard view files (after model views, before menu)
    dashboard_models_seen: set[str] = set()
    for dashboard in spec.get("dashboards", []):
        model_xml = _to_xml_id(dashboard["model_name"])
        if model_xml not in dashboard_models_seen:
            dashboard_models_seen.add(model_xml)
            manifest_files.append(f"views/{model_xml}_graph.xml")
            manifest_files.append(f"views/{model_xml}_pivot.xml")
            # Phase 63: kanban/cohort views (conditionally rendered by renderer.py)
            if dashboard.get("kanban") or dashboard.get("kanban_fields"):
                manifest_files.append(f"views/{model_xml}_kanban.xml")
            if dashboard.get("cohort_date_start"):
                manifest_files.append(f"views/{model_xml}_cohort.xml")

    manifest_files.append("views/menu.xml")

    return manifest_files


def _compute_view_files(spec: dict[str, Any]) -> list[str]:
    """Compute the list of view file paths for the manifest data section.

    Args:
        spec: Full module specification dictionary.

    Returns:
        List of view file relative paths (e.g., ["item_views.xml", ...]).
    """
    view_files = []
    for model in spec.get("models", []):
        model_var = _to_python_var(model["name"])
        view_files.append(f"{model_var}_views.xml")
        view_files.append(f"{model_var}_action.xml")
    view_files.append("menu.xml")
    return view_files


def _build_module_context(spec: dict[str, Any], module_name: str) -> dict[str, Any]:
    """Build the shared module-level template context from the spec."""
    models = spec.get("models", [])
    spec_wizards = spec.get("wizards", [])
    has_seq = any(
        any(f.get("type") == "Char" and f.get("name") in SEQUENCE_FIELD_NAMES and f.get("required")
            for f in m.get("fields", []))
        for m in models
    )
    has_company = any(
        any(f.get("name") == "company_id" and f.get("type") == "Many2one" for f in m.get("fields", []))
        for m in models
    )
    data_files: list[str] = []
    if has_seq:
        data_files.append("data/sequences.xml")
    data_files.append("data/data.xml")
    # Phase 30: cron data file
    if spec.get("cron_jobs"):
        data_files.append("data/cron_data.xml")
    # Phase 31: report data files
    for report in spec.get("reports", []):
        data_files.append(f"data/report_{report['xml_id']}.xml")
        data_files.append(f"data/report_{report['xml_id']}_template.xml")
    # Phase 49: extra data files from localization preprocessors
    data_files.extend(spec.get("extra_data_files", []))
    wiz_files = [f"views/{_to_xml_id(w['name'])}_wizard_form.xml" for w in spec_wizards]
    # Phase 32: import/export wizard detection
    import_export_models = [m for m in models if m.get("import_export")]
    has_import_export = bool(import_export_models)
    # Add import wizard form view files to manifest
    for m in import_export_models:
        wiz_files.append(f"views/{_to_xml_id(m['name'])}_import_wizard_form.xml")
    # Build import_export_wizards list for ACL generation
    import_export_wizards = [
        {"name": f"{m['name']}.import.wizard"} for m in import_export_models
    ]
    has_record_rules = any(m.get("record_rule_scopes") for m in models)
    manifest_files = _compute_manifest_data(
        spec, data_files, wiz_files,
        has_company_modules=has_company or has_record_rules,
    )
    # Phase 59: extension model files for init_models.py.j2
    extension_model_files = spec.get("extension_model_files", [])
    has_extensions = spec.get("has_extensions", False)

    # Phase 59: add extension view files to manifest_files
    if has_extensions:
        for ext in spec.get("extends", []):
            ext_base_var = _to_python_var(ext.get("base_model", ""))
            if ext.get("view_extensions"):
                manifest_files.append(f"views/{ext_base_var}_views.xml")

    # Phase 63: bulk operation manifest files
    has_bulk_operations = spec.get("has_bulk_operations", False)
    if has_bulk_operations:
        for bop in spec.get("bulk_operations", []):
            wiz_var = _to_python_var(bop["wizard_model"])
            manifest_files.append(f"views/{wiz_var}_wizard_form.xml")
        pass  # JS handled via manifest_assets below

    # Phase 62: portal manifest files
    has_portal = spec.get("has_portal", False)
    if has_portal:
        portal_pages = spec.get("portal_pages", [])
        portal_view_files: set[str] = set()
        for p in portal_pages:
            if p.get("show_in_home", True):
                portal_view_files.add("views/portal_home.xml")
            portal_view_files.add(f"views/portal_{p['id']}.xml")
        portal_view_files.add("security/portal_rules.xml")
        manifest_files.extend(sorted(portal_view_files))

    # Build asset bundle declarations (JS/CSS loaded via web.assets_backend)
    manifest_assets: list[dict[str, str]] = []
    if has_bulk_operations:
        manifest_assets.append({
            "bundle": "web.assets_backend",
            "path": "static/src/js/bulk_progress.js",
        })

    ctx: dict[str, Any] = {
        "module_name": module_name,
        "module_title": spec.get("module_title", module_name.replace("_", " ").title()),
        "module_technical_name": module_name,
        "summary": spec.get("summary", ""),
        "author": spec.get("author", ""),
        "website": spec.get("website", ""),
        "license": spec.get("license", "LGPL-3"),
        "category": spec.get("category", "Uncategorized"),
        "odoo_version": spec.get("odoo_version", "19.0"),
        "depends": spec.get("depends", ["base"]),
        "application": spec.get("application", True),
        "models": models,
        "view_files": _compute_view_files(spec),
        "manifest_files": manifest_files,
        "manifest_assets": manifest_assets,
        "has_wizards": bool(spec_wizards) or has_import_export,
        "spec_wizards": spec_wizards,
        "has_controllers": bool(spec.get("controllers")) or has_portal,
        "has_import_export": has_import_export,
        "import_export_wizards": import_export_wizards,
        "security_roles": spec.get("security_roles", []),
        "has_record_rules": has_record_rules,
        # Phase 38 keys
        "has_audit_log": spec.get("has_audit_log", False),
        # Phase 39 keys
        "has_approval_models": any(m.get("has_approval") for m in models),
        # Phase 40 keys
        "has_notification_models": any(m.get("has_notifications") for m in models),
        "has_webhook_models": any(m.get("has_webhooks") for m in models),
        # Phase 42: Context7 documentation hints (StrictUndefined-safe default)
        "c7_hints": {},
        # Phase 52 keys
        "has_document_models": any(m.get("has_document_verification") for m in models),
        # Phase 59: extension keys
        "extension_model_files": extension_model_files,
        "has_extensions": has_extensions,
        # Phase 62: portal keys
        "has_portal": has_portal,
        # Phase 63: bulk operation keys
        "has_bulk_operations": has_bulk_operations,
        # Integration keys (amil schema alignment)
        "workflows": spec.get("workflow", []),
        "business_rules": spec.get("business_rules", []),
        "view_hints": spec.get("view_hints", []),
    }
    # NEW-08: settings manifest files
    has_settings = bool(spec.get("settings"))
    if has_settings:
        manifest_files.append("views/res_config_settings_view.xml")
    ctx["has_settings"] = has_settings

    # Phase 52: VERSION_GATES for Odoo version-conditional template rendering (DOMN-04)
    ctx["version_gates"] = _VERSION_GATES

    # NEW-07: Auto-detect external dependencies from model code
    ext_deps = _detect_external_dependencies(spec)
    if ext_deps:
        ctx["external_dependencies"] = {"python": ext_deps}
    elif has_import_export:
        ctx["external_dependencies"] = {"python": ["openpyxl"]}
    return ctx
