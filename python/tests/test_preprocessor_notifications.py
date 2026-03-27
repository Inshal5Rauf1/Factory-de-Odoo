"""Tests for the notification_patterns preprocessor."""

from __future__ import annotations

from typing import Any

import pytest

from amil_utils.preprocessors.notifications import _process_notification_patterns


def _make_spec(
    models: list[dict[str, Any]] | None = None,
    module_name: str = "test_mod",
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal spec dict."""
    return {
        "module_name": module_name,
        "models": models or [],
        "security_roles": kwargs.pop("security_roles", []),
        **kwargs,
    }


def _approval_model(
    name: str = "test.request",
    *,
    levels: list[dict[str, Any]] | None = None,
    on_reject_notify: dict[str, Any] | None = None,
    fields: list[dict[str, Any]] | None = None,
    approval_action_methods: list[dict[str, Any]] | None = None,
    submit_action: dict[str, Any] | None = None,
    reject_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a model with approval configuration."""
    model: dict[str, Any] = {
        "name": name,
        "has_approval": True,
        "approval_levels": levels or [],
        "fields": fields or [
            {"name": "name", "type": "Char", "string": "Name"},
            {"name": "description", "type": "Text", "string": "Description"},
        ],
        "approval_action_methods": approval_action_methods or [],
    }
    approval: dict[str, Any] = {}
    if on_reject_notify:
        approval["on_reject_notify"] = on_reject_notify
    if approval:
        model["approval"] = approval
    if submit_action is not None:
        model["approval_submit_action"] = submit_action
    if reject_action is not None:
        model["approval_reject_action"] = reject_action
    return model


class TestProcessNotificationPatterns:
    """Tests for _process_notification_patterns."""

    def test_happy_path_level_0_notify(self):
        """Level-0 notify enriches the submit action with notification."""
        levels = [
            {
                "state": "pending",
                "label": "Pending Review",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "creator",
                    "subject": "Your request is pending",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
            approval_action_methods=[],
        )
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        assert result is not spec
        rm = result["models"][0]
        assert rm["has_notifications"] is True
        assert rm["needs_logger"] is True
        assert len(rm["notification_templates"]) == 1
        tmpl = rm["notification_templates"][0]
        assert tmpl["xml_id"] == "notif_pending"
        assert tmpl["subject"] == "Your request is pending"
        assert tmpl["dispatch_method"] == "mail_template"
        # Submit action should have notification sub-dict
        assert "notification" in rm["approval_submit_action"]
        notif = rm["approval_submit_action"]["notification"]
        assert notif["send_mail"] is True
        assert notif["template_xml_id"] == "notif_pending"

    def test_happy_path_level_1_notify(self):
        """Level >0 notify enriches the matching approval action method."""
        levels = [
            {"state": "pending", "label": "Pending"},
            {
                "state": "approved",
                "label": "Approved",
                "notify": {
                    "template": "notif_approved",
                    "recipients": "creator",
                    "subject": "Request approved",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
            approval_action_methods=[
                {"name": "action_approve_approved"},
            ],
        )
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        rm = result["models"][0]
        method = rm["approval_action_methods"][0]
        assert "notification" in method
        assert method["notification"]["template_xml_id"] == "notif_approved"

    def test_on_reject_notify(self):
        """on_reject_notify enriches the reject action."""
        model = _approval_model(
            levels=[{"state": "pending", "label": "Pending"}],
            on_reject_notify={
                "template": "notif_rejected",
                "recipients": "creator",
                "subject": "Request rejected",
            },
            submit_action={"name": "action_submit"},
            reject_action={"name": "action_reject"},
        )
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        rm = result["models"][0]
        assert "notification" in rm["approval_reject_action"]
        assert rm["approval_reject_action"]["notification"]["template_xml_id"] == "notif_rejected"
        # Reject template in notification_templates
        templates = rm["notification_templates"]
        assert any(t["xml_id"] == "notif_rejected" for t in templates)

    def test_mail_dependency_added(self):
        """'mail' is added to depends when mail_template dispatch is used."""
        levels = [
            {
                "state": "pending",
                "label": "Pending",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "creator",
                    "subject": "Pending",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[model], depends=["base"])

        result = _process_notification_patterns(spec)

        assert "mail" in result["depends"]
        assert "base" in result["depends"]

    def test_mail_dependency_not_duplicated(self):
        """'mail' is not duplicated if already in depends."""
        levels = [
            {
                "state": "pending",
                "label": "Pending",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "creator",
                    "subject": "Pending",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[model], depends=["base", "mail"])

        result = _process_notification_patterns(spec)

        assert result["depends"].count("mail") == 1

    def test_spec_level_flags(self):
        """has_notification_models set on spec when notifications exist."""
        levels = [
            {
                "state": "pending",
                "label": "Pending",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "creator",
                    "subject": "Pending",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        assert result["has_notification_models"] is True

    def test_activity_dispatch(self):
        """mail_activity dispatch enriches template with activity fields."""
        levels = [
            {
                "state": "pending",
                "label": "Pending",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "creator",
                    "subject": "Pending",
                    "dispatch": "mail_activity",
                    "activity_type": "mail.mail_activity_data_warning",
                    "activity_summary": "Review needed",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        tmpl = result["models"][0]["notification_templates"][0]
        assert tmpl["dispatch_method"] == "mail_activity"
        assert tmpl["activity_type_xmlref"] == "mail.mail_activity_data_warning"
        assert tmpl["activity_summary"] == "Review needed"

    def test_empty_spec_no_models(self):
        """Empty models list returns spec unchanged."""
        spec = _make_spec(models=[])

        result = _process_notification_patterns(spec)

        assert result is spec

    def test_model_without_approval(self):
        """Models without has_approval pass through unchanged."""
        model = {"name": "test.simple", "fields": []}
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        assert result is spec

    def test_approval_model_without_notify(self):
        """Approval model with no notify blocks returns spec unchanged."""
        model = _approval_model(levels=[{"state": "pending", "label": "Pending"}])
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        assert result is spec

    def test_immutability_input_not_mutated(self):
        """Input spec and model dicts are not mutated."""
        levels = [
            {
                "state": "pending",
                "label": "Pending",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "creator",
                    "subject": "Pending",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[model])
        original_model_keys = set(model.keys())

        _process_notification_patterns(spec)

        # Original model should not gain new keys
        assert set(model.keys()) == original_model_keys
        assert "has_notifications" not in model

    def test_recipient_role_resolution(self):
        """role: recipient resolves to group-based email."""
        levels = [
            {
                "state": "pending",
                "label": "Pending",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "role:manager",
                    "subject": "Pending",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[model], module_name="my_mod")

        result = _process_notification_patterns(spec)

        tmpl = result["models"][0]["notification_templates"][0]
        assert "my_mod.group_my_mod_manager" in tmpl["email_to"]

    def test_recipient_field_resolution(self):
        """field: recipient resolves to object field email."""
        levels = [
            {
                "state": "pending",
                "label": "Pending",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "field:reviewer_id",
                    "subject": "Pending",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        tmpl = result["models"][0]["notification_templates"][0]
        assert "object.reviewer_id.email" in tmpl["email_to"]

    def test_recipient_fixed_resolution(self):
        """fixed: recipient resolves to literal email."""
        levels = [
            {
                "state": "pending",
                "label": "Pending",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "fixed:admin@example.com",
                    "subject": "Pending",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        tmpl = result["models"][0]["notification_templates"][0]
        assert tmpl["email_to"] == "admin@example.com"

    def test_body_fields_selection(self):
        """Body fields are selected from model fields, excluding technical ones."""
        fields = [
            {"name": "name", "type": "Char", "string": "Name"},
            {"name": "amount", "type": "Float", "string": "Amount", "required": True},
            {"name": "create_uid", "type": "Many2one"},
            {"name": "attachment", "type": "Binary"},
        ]
        levels = [
            {
                "state": "pending",
                "label": "Pending",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "creator",
                    "subject": "Pending",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            fields=fields,
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        tmpl = result["models"][0]["notification_templates"][0]
        field_names = [f["name"] for f in tmpl["body_fields"]]
        assert "name" in field_names
        assert "amount" in field_names
        assert "create_uid" not in field_names
        assert "attachment" not in field_names

    def test_automated_actions_for_mail_template(self):
        """Automated actions are generated for mail_template dispatch."""
        levels = [
            {
                "state": "pending",
                "label": "Pending",
                "notify": {
                    "template": "notif_pending",
                    "recipients": "creator",
                    "subject": "Pending",
                },
            },
        ]
        model = _approval_model(
            levels=levels,
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[model])

        result = _process_notification_patterns(spec)

        rm = result["models"][0]
        assert "notification_automated_actions" in rm
        actions = rm["notification_automated_actions"]
        assert len(actions) == 1
        assert actions[0]["template_xml_id"] == "notif_pending"

    def test_multiple_models_mixed(self):
        """Only models with approval + notify are enriched; others pass through."""
        simple_model = {"name": "test.simple", "fields": []}
        approval_no_notify = _approval_model(
            name="test.no_notify",
            levels=[{"state": "pending", "label": "Pending"}],
        )
        approval_with_notify = _approval_model(
            name="test.with_notify",
            levels=[
                {
                    "state": "pending",
                    "label": "Pending",
                    "notify": {
                        "template": "notif_pending",
                        "recipients": "creator",
                        "subject": "Pending",
                    },
                },
            ],
            submit_action={"name": "action_submit"},
        )
        spec = _make_spec(models=[simple_model, approval_no_notify, approval_with_notify])

        result = _process_notification_patterns(spec)

        assert len(result["models"]) == 3
        assert "has_notifications" not in result["models"][0]
        assert "has_notifications" not in result["models"][1]
        assert result["models"][2]["has_notifications"] is True
