"""Notification pattern processing for approval workflows."""

from __future__ import annotations

import logging
from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.utils.copy import deep_copy_model
from odoo_gen_utils.utils.validate import validate_identifier

logger = logging.getLogger(__name__)

# BUG-M17: Stable inter-preprocessor interface keys.
# These are the keys that the approval preprocessor guarantees to set.
# Other preprocessors should ONLY access approval data through these keys.
_APPROVAL_INTERFACE_KEYS = frozenset({
    "has_approval",
    "approval_levels",
    "approval_action_methods",
    "approval_submit_action",
    "approval_reject_action",
    "approval_reset_action",
    "approval_state_field_name",
    "on_reject",
    "reject_allowed_from",
})


def _get_approval_levels(model: dict[str, Any]) -> list[dict[str, Any]]:
    """BUG-M17: Safely extract approval levels from a model dict.

    Uses the stable interface key ``approval_levels`` set by the approval
    preprocessor. Returns empty list if the model has no approval or
    the key is missing.
    """
    if not model.get("has_approval"):
        return []
    return model.get("approval_levels", [])


def _get_approval_block(model: dict[str, Any]) -> dict[str, Any]:
    """BUG-M17: Safely extract the original approval config block.

    Falls back to empty dict if not present.
    """
    return model.get("approval", {})

# Technical/internal fields excluded from notification email body
_NOTIFICATION_EXCLUDE_NAMES = frozenset({
    "create_uid", "write_uid", "create_date", "write_date",
    "message_ids", "activity_ids", "parent_path", "state",
})

# Field types excluded from notification email body
_NOTIFICATION_EXCLUDE_TYPES = frozenset({"Binary", "One2many", "Many2many"})


def _resolve_recipient(
    recipient: str,
    module_name: str,
    security_roles: list[dict[str, Any]],
) -> str:
    """Resolve a recipient expression to an ``email_to`` template value.

    Supported recipient formats:
    - ``"creator"`` -- record's ``create_uid.partner_id``
    - ``"role:{name}"`` -- users in the named security group
    - ``"field:{field}"`` -- Many2one to ``res.users``/``res.partner`` on the model
    - ``"fixed:{email}"`` -- hardcoded email address

    Returns:
        The ``email_to`` string value.
    """
    if recipient == "creator":
        return "{{ object.create_uid.partner_id.email }}"

    if recipient.startswith("role:"):
        role_name = recipient[5:]
        group_ref = f"{module_name}.group_{module_name}_{role_name}"
        return (
            "{{ ','.join(env.ref('"
            + group_ref
            + "').users.mapped('email')) }}"
        )

    if recipient.startswith("field:"):
        field_name = recipient[6:]
        validate_identifier(field_name, "notification recipient field")
        return "{{ object." + field_name + ".email }}"

    if recipient.startswith("fixed:"):
        return recipient[6:]

    # Fallback -- treat as fixed
    return recipient


def _select_body_fields(
    model: dict[str, Any],
    max_fields: int = 4,
) -> list[dict[str, str]]:
    """Select fields suitable for an auto-generated notification email body.

    Priority:
    1. ``name``/``display_name`` first (always if present)
    2. Required fields
    3. Fields with a ``string`` attribute

    Excludes:
    - Binary, One2many, Many2many types
    - Computed fields (have ``compute`` key)
    - Technical field names (create_uid, write_uid, etc.)

    Returns:
        List of dicts with ``name`` and ``label`` keys.
    """
    fields = model.get("fields", [])
    candidates: list[dict[str, str]] = []
    priority_names: list[dict[str, str]] = []

    for field in fields:
        fname = field.get("name", "")
        ftype = field.get("type", "")

        # Skip excluded types
        if ftype in _NOTIFICATION_EXCLUDE_TYPES:
            continue
        # Skip excluded names
        if fname in _NOTIFICATION_EXCLUDE_NAMES:
            continue
        # Skip computed fields
        if field.get("compute"):
            continue

        label = field.get("string") or fname.replace("_", " ").title()
        entry = {"name": fname, "label": label}

        # Priority: name/display_name always first
        if fname in ("name", "display_name"):
            priority_names.append(entry)
        elif field.get("required"):
            candidates.insert(0, entry)
        elif field.get("string"):
            candidates.append(entry)
        else:
            candidates.append(entry)

    result = priority_names + candidates
    return result[:max_fields]


@register_preprocessor(order=90, name="notification_patterns")
def _process_notification_patterns(spec: dict[str, Any]) -> dict[str, Any]:
    """Pre-process notification configuration on approval models.

    For each model with ``has_approval`` and approval levels containing ``notify``
    objects:
    1. Builds ``notification_templates`` list with template metadata
    2. Enriches ``approval_action_methods`` entries with ``notification`` sub-dict
    3. Enriches ``approval_submit_action`` (level 0 notify) and
       ``approval_reject_action`` (``on_reject_notify``)
    4. Sets ``has_notifications=True``, ``needs_logger=True`` on model
    5. Sets ``has_notification_models=True`` on spec
    6. Adds ``"mail"`` to ``spec["depends"]`` if not present

    Returns a new spec dict. Pure function -- does NOT mutate the input spec.
    """
    models = spec.get("models", [])
    module_name = spec["module_name"]
    security_roles = spec.get("security_roles", [])

    has_any_notifications = False
    new_models = []

    for model in models:
        if not model.get("has_approval"):
            new_models.append(model)
            continue

        # BUG-M17: Use stable interface helpers instead of reading internals
        approval_levels = _get_approval_levels(model)
        approval_block = _get_approval_block(model)

        # Check if any level has notify, or if on_reject_notify is present
        level_notifies = [
            (i, level.get("notify"))
            for i, level in enumerate(approval_levels)
            if level.get("notify")
        ]
        on_reject_notify = approval_block.get("on_reject_notify")

        if not level_notifies and not on_reject_notify:
            new_models.append(model)
            continue

        has_any_notifications = True

        # H2 fix: Always deep-copy to avoid mutation leaks
        new_model = deep_copy_model(model)
        new_model["approval_action_methods"] = [
            {**m} for m in model.get("approval_action_methods", [])
        ]
        if model.get("approval_submit_action"):
            new_model["approval_submit_action"] = {**model["approval_submit_action"]}
        if model.get("approval_reject_action"):
            new_model["approval_reject_action"] = {**model["approval_reject_action"]}

        notification_templates: list[dict[str, Any]] = []
        model_xml_id = model["name"].replace(".", "_")
        body_fields = _select_body_fields(model)

        # Process level notifies
        for level_idx, notify in level_notifies:
            template_name = notify["template"]
            xml_id = template_name
            email_to = _resolve_recipient(
                notify["recipients"], module_name, security_roles,
            )
            level = approval_levels[level_idx]
            state_label = level.get("label", level["state"].replace("_", " ").title())

            # FLAW-19: Dispatch metadata for actual mail sending
            dispatch_method = notify.get("dispatch", "mail_template")
            template_entry = {
                "xml_id": xml_id,
                "name": template_name.replace("_", " ").title(),
                "model_xml_id": model_xml_id,
                "subject": notify["subject"],
                "email_to": email_to,
                "body_intro": f"The record has been transitioned to {state_label}.",
                "body_fields": body_fields,
                "dispatch_method": dispatch_method,
            }
            # FLAW-19: Add activity creation spec if dispatch uses activities
            if dispatch_method == "mail_activity":
                template_entry["activity_type_xmlref"] = notify.get(
                    "activity_type", "mail.mail_activity_data_todo"
                )
                template_entry["activity_summary"] = notify.get(
                    "activity_summary",
                    f"Approval pending: {state_label}",
                )
            notification_templates.append(template_entry)

            notification_sub = {
                "template_xml_id": xml_id,
                "send_mail": dispatch_method == "mail_template",
                "create_activity": dispatch_method == "mail_activity",
                "email_to": email_to,
                "dispatch_method": dispatch_method,
            }

            # Level 0 notify enriches submit action
            if level_idx == 0:
                new_model["approval_submit_action"]["notification"] = notification_sub
            else:
                # Find the matching action method
                target_name = f"action_approve_{level['state']}"
                for method in new_model["approval_action_methods"]:
                    if method["name"] == target_name:
                        method["notification"] = notification_sub
                        break

        # Process on_reject_notify
        if on_reject_notify:
            template_name = on_reject_notify["template"]
            xml_id = template_name
            email_to = _resolve_recipient(
                on_reject_notify["recipients"], module_name, security_roles,
            )
            reject_dispatch = on_reject_notify.get("dispatch", "mail_template")
            template_entry = {
                "xml_id": xml_id,
                "name": template_name.replace("_", " ").title(),
                "model_xml_id": model_xml_id,
                "subject": on_reject_notify["subject"],
                "email_to": email_to,
                "body_intro": "The record has been rejected.",
                "body_fields": body_fields,
                "dispatch_method": reject_dispatch,
            }
            notification_templates.append(template_entry)

            notification_sub = {
                "template_xml_id": xml_id,
                "send_mail": reject_dispatch == "mail_template",
                "create_activity": reject_dispatch == "mail_activity",
                "email_to": email_to,
                "dispatch_method": reject_dispatch,
            }
            if new_model.get("approval_reject_action"):
                new_model["approval_reject_action"]["notification"] = notification_sub

        new_model["has_notifications"] = True
        new_model["has_notification_dispatch"] = True
        new_model["needs_logger"] = True
        new_model["notification_templates"] = notification_templates

        # FLAW-19: Build automated action specs for auto-dispatch
        automated_actions = []
        for tmpl in notification_templates:
            if tmpl["dispatch_method"] == "mail_template":
                automated_actions.append({
                    "name": f"auto_send_{tmpl['xml_id']}",
                    "type": "ir.actions.server",
                    "model_name": model["name"],
                    "template_xml_id": tmpl["xml_id"],
                    "trigger": "on_write",
                })
        if automated_actions:
            new_model["notification_automated_actions"] = automated_actions

        new_models.append(new_model)

    if not has_any_notifications:
        return spec

    # Mail dep: Only inject "mail" when at least one notification uses
    # mail_template dispatch. Activity-only notifications don't require it.
    needs_mail = any(
        tmpl.get("dispatch_method", "mail_template") == "mail_template"
        for m in new_models
        for tmpl in m.get("notification_templates", [])
    )

    new_spec = {
        **spec,
        "models": new_models,
        "has_notification_models": True,
    }

    if needs_mail:
        new_depends = list(spec.get("depends", []))
        if "mail" not in new_depends:
            new_depends.append("mail")
        new_spec["depends"] = new_depends

    return new_spec
