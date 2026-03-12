"""Tests for preprocessor functions in amil_utils.preprocessors.

Phase 38: Unit tests for _process_audit_patterns.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pytest

from amil_utils.preprocessors import (
    _process_audit_patterns,
    _process_approval_patterns,
    _process_notification_patterns,
    _process_webhook_patterns,
)
from amil_utils.preprocessors.relationships import (
    _enrich_delegation,
    _enrich_hierarchical,
)
from amil_utils.preprocessors.webhooks import (
    _build_webhook_endpoint_model,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(
    models: list[dict[str, Any]] | None = None,
    security: dict[str, Any] | None = None,
    security_roles: list[dict[str, Any]] | None = None,
    module_name: str = "test_module",
) -> dict[str, Any]:
    """Build a minimal spec for audit preprocessor testing."""
    spec: dict[str, Any] = {
        "module_name": module_name,
        "depends": ["base"],
        "models": models or [],
    }
    if security is not None:
        spec["security"] = security
    if security_roles is not None:
        spec["security_roles"] = security_roles
    return spec


def _make_model(
    name: str = "test.model",
    fields: list[dict[str, Any]] | None = None,
    audit: bool = False,
    audit_exclude: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal model dict for testing."""
    model: dict[str, Any] = {
        "name": name,
        "description": name.replace(".", " ").title(),
        "fields": fields or [
            {"name": "name", "type": "Char", "required": True},
            {"name": "value", "type": "Integer"},
        ],
        **kwargs,
    }
    if audit:
        model["audit"] = True
    if audit_exclude is not None:
        model["audit_exclude"] = audit_exclude
    return model


def _make_security_roles(
    roles: list[str] | None = None,
    module_name: str = "test_module",
) -> list[dict[str, Any]]:
    """Build security_roles list matching _security_build_roles output."""
    roles = roles or ["user", "manager"]
    result = []
    for i, role_name in enumerate(roles):
        is_highest = i == len(roles) - 1
        result.append({
            "name": role_name,
            "label": role_name.replace("_", " ").title(),
            "xml_id": f"group_{module_name}_{role_name}",
            "implied_ids": "base.group_user" if i == 0 else f"group_{module_name}_{roles[i - 1]}",
            "is_highest": is_highest,
        })
    return result


# ---------------------------------------------------------------------------
# TestAuditPreprocessor
# ---------------------------------------------------------------------------


class TestAuditPreprocessor:
    """Test _process_audit_patterns preprocessor."""

    def test_audit_true_enriches_model(self):
        """Spec with audit:true on one model produces has_audit, audit_fields, override_sources[write]=audit."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
                {"name": "email", "type": "Char"},
                {"name": "gpa", "type": "Float"},
            ],
            audit=True,
        )
        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(),
        )
        result = _process_audit_patterns(spec)

        # Find the enriched model
        enriched = next(m for m in result["models"] if m["name"] == "university.student")
        assert enriched["has_audit"] is True
        assert isinstance(enriched["audit_fields"], list)
        assert len(enriched["audit_fields"]) > 0
        # All audit_fields should be field dicts with "name" key
        field_names = {f["name"] for f in enriched["audit_fields"]}
        assert "name" in field_names
        assert "email" in field_names
        assert "gpa" in field_names
        # override_sources must include "audit" for "write"
        assert "audit" in enriched["override_sources"]["write"]
        assert enriched["has_write_override"] is True

    def test_audit_true_synthesizes_audit_log_model(self):
        """Spec with audit:true produces audit.trail.log companion model with correct fields."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
            ],
            audit=True,
        )
        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(),
        )
        result = _process_audit_patterns(spec)

        # Find synthesized audit.trail.log model
        audit_model = next(
            (m for m in result["models"] if m["name"] == "audit.trail.log"),
            None,
        )
        assert audit_model is not None, "audit.trail.log model not synthesized"

        # Verify required fields
        field_names = {f["name"] for f in audit_model["fields"]}
        assert "res_model" in field_names
        assert "res_id" in field_names
        assert "changes" in field_names
        assert "user_id" in field_names
        assert "operation" in field_names

        # Check specific field attributes
        res_model = next(f for f in audit_model["fields"] if f["name"] == "res_model")
        assert res_model["type"] == "Char"
        assert res_model.get("index") is True
        assert res_model.get("required") is True
        assert res_model.get("readonly") is True

        res_id = next(f for f in audit_model["fields"] if f["name"] == "res_id")
        assert res_id["type"] == "Many2oneReference"
        assert res_id.get("model_field") == "res_model"
        assert res_id.get("readonly") is True

        changes = next(f for f in audit_model["fields"] if f["name"] == "changes")
        assert changes["type"] == "Json"
        assert changes.get("readonly") is True

        user_id = next(f for f in audit_model["fields"] if f["name"] == "user_id")
        assert user_id["type"] == "Many2one"
        assert user_id.get("comodel_name") == "res.users"
        assert user_id.get("required") is True
        assert user_id.get("readonly") is True
        assert user_id.get("index") is True

        operation = next(f for f in audit_model["fields"] if f["name"] == "operation")
        assert operation["type"] == "Selection"
        assert operation.get("required") is True
        assert operation.get("readonly") is True
        # Should have write/create/unlink options
        selection_keys = {s[0] for s in operation.get("selection", [])}
        assert "write" in selection_keys
        assert "create" in selection_keys
        assert "unlink" in selection_keys

        # Metadata flags
        assert audit_model["_synthesized"] is True
        assert audit_model["_is_audit_log"] is True
        assert audit_model.get("chatter") is False
        assert audit_model.get("audit") is False

    def test_audit_auto_excludes_fields(self):
        """Auto-excluded fields (One2many, Many2many, Binary, message_ids, activity_ids, write_date, write_uid) never appear in audit_fields."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
                {"name": "email", "type": "Char"},
                {"name": "photo", "type": "Binary"},
                {"name": "tag_ids", "type": "Many2many", "comodel_name": "university.tag"},
                {"name": "enrollment_ids", "type": "One2many", "comodel_name": "university.enrollment"},
                {"name": "message_ids", "type": "One2many", "comodel_name": "mail.message"},
                {"name": "activity_ids", "type": "One2many", "comodel_name": "mail.activity"},
                {"name": "write_date", "type": "Datetime"},
                {"name": "write_uid", "type": "Many2one", "comodel_name": "res.users"},
            ],
            audit=True,
        )
        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(),
        )
        result = _process_audit_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "university.student")

        audit_field_names = {f["name"] for f in enriched["audit_fields"]}
        # Should include name and email
        assert "name" in audit_field_names
        assert "email" in audit_field_names
        # Should NOT include auto-excluded fields
        assert "photo" not in audit_field_names  # Binary
        assert "tag_ids" not in audit_field_names  # Many2many
        assert "enrollment_ids" not in audit_field_names  # One2many
        assert "message_ids" not in audit_field_names  # ALWAYS_EXCLUDE
        assert "activity_ids" not in audit_field_names  # ALWAYS_EXCLUDE
        assert "write_date" not in audit_field_names  # ALWAYS_EXCLUDE
        assert "write_uid" not in audit_field_names  # ALWAYS_EXCLUDE

    def test_audit_exclude_custom_fields(self):
        """Spec with audit_exclude: ['custom_field'] excludes custom_field from audit_fields."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
                {"name": "email", "type": "Char"},
                {"name": "internal_notes", "type": "Text"},
            ],
            audit=True,
            audit_exclude=["internal_notes"],
        )
        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(),
        )
        result = _process_audit_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "university.student")

        audit_field_names = {f["name"] for f in enriched["audit_fields"]}
        assert "name" in audit_field_names
        assert "email" in audit_field_names
        assert "internal_notes" not in audit_field_names

    def test_no_audit_returns_unchanged(self):
        """Spec with no audit:true on any model returns spec unchanged, no has_audit_log key."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
            ],
        )
        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(),
        )
        result = _process_audit_patterns(spec)

        # No has_audit_log on spec
        assert "has_audit_log" not in result
        # No audit.trail.log model
        model_names = {m["name"] for m in result["models"]}
        assert "audit.trail.log" not in model_names
        # Original model unchanged
        student = next(m for m in result["models"] if m["name"] == "university.student")
        assert "has_audit" not in student

    def test_auditor_role_injected_when_missing(self):
        """Spec with audit:true and no 'auditor' in security_roles injects auditor role."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
            ],
            audit=True,
        )
        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(roles=["user", "manager"]),
        )
        result = _process_audit_patterns(spec)

        role_names = [r["name"] for r in result["security_roles"]]
        assert "auditor" in role_names
        # Auditor should imply base.group_user (sibling of lowest, not in hierarchy chain)
        auditor = next(r for r in result["security_roles"] if r["name"] == "auditor")
        assert auditor["implied_ids"] == "base.group_user"

    def test_auditor_role_not_duplicated_when_exists(self):
        """Spec with audit:true and 'auditor' already in security_roles does not duplicate."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
            ],
            audit=True,
        )
        roles_with_auditor = _make_security_roles(roles=["user", "auditor", "manager"])
        spec = _make_spec(
            models=[model],
            security_roles=roles_with_auditor,
        )
        result = _process_audit_patterns(spec)

        auditor_count = sum(1 for r in result["security_roles"] if r["name"] == "auditor")
        assert auditor_count == 1

    def test_audit_log_model_gets_read_only_acl(self):
        """audit.trail.log gets security_acl with read-only for auditor+highest role, no access for others."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
            ],
            audit=True,
        )
        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(roles=["user", "manager"]),
        )
        result = _process_audit_patterns(spec)

        audit_model = next(m for m in result["models"] if m["name"] == "audit.trail.log")
        acl = audit_model.get("security_acl", [])
        assert len(acl) > 0, "security_acl not set on audit.trail.log"

        # Build lookup by role
        acl_by_role = {entry["role"]: entry for entry in acl}

        # Auditor should have read-only
        assert "auditor" in acl_by_role
        assert acl_by_role["auditor"]["perm_read"] == 1
        assert acl_by_role["auditor"]["perm_write"] == 0
        assert acl_by_role["auditor"]["perm_create"] == 0
        assert acl_by_role["auditor"]["perm_unlink"] == 0

        # Highest role (manager) should have read-only
        assert "manager" in acl_by_role
        assert acl_by_role["manager"]["perm_read"] == 1
        assert acl_by_role["manager"]["perm_write"] == 0
        assert acl_by_role["manager"]["perm_create"] == 0
        assert acl_by_role["manager"]["perm_unlink"] == 0

        # Other roles (user) should have NO access
        if "user" in acl_by_role:
            assert acl_by_role["user"]["perm_read"] == 0
            assert acl_by_role["user"]["perm_write"] == 0
            assert acl_by_role["user"]["perm_create"] == 0
            assert acl_by_role["user"]["perm_unlink"] == 0

    def test_synthesized_audit_log_metadata_flags(self):
        """Synthesized audit.trail.log has _synthesized=True, _is_audit_log=True, chatter=False."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
            ],
            audit=True,
        )
        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(),
        )
        result = _process_audit_patterns(spec)

        audit_model = next(m for m in result["models"] if m["name"] == "audit.trail.log")
        assert audit_model["_synthesized"] is True
        assert audit_model["_is_audit_log"] is True
        assert audit_model["chatter"] is False
        assert audit_model["audit"] is False

    def test_has_audit_log_set_on_spec(self):
        """When any model has audit:true, spec gets has_audit_log=True."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
            ],
            audit=True,
        )
        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(),
        )
        result = _process_audit_patterns(spec)
        assert result["has_audit_log"] is True

    def test_pure_function_does_not_mutate_input(self):
        """Preprocessor does not mutate original spec."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
            ],
            audit=True,
        )
        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(),
        )
        # Deep snapshot of original models
        original_model_names = [m["name"] for m in spec["models"]]

        _process_audit_patterns(spec)

        # Original spec should be unchanged
        current_model_names = [m["name"] for m in spec["models"]]
        assert current_model_names == original_model_names
        assert "has_audit_log" not in spec

    def test_multiple_audited_models(self):
        """Multiple models with audit:true all get enriched and share one audit.trail.log."""
        model1 = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
                {"name": "email", "type": "Char"},
            ],
            audit=True,
        )
        model2 = _make_model(
            name="university.course",
            fields=[
                {"name": "title", "type": "Char", "required": True},
                {"name": "credits", "type": "Integer"},
            ],
            audit=True,
        )
        spec = _make_spec(
            models=[model1, model2],
            security_roles=_make_security_roles(),
        )
        result = _process_audit_patterns(spec)

        student = next(m for m in result["models"] if m["name"] == "university.student")
        course = next(m for m in result["models"] if m["name"] == "university.course")
        assert student["has_audit"] is True
        assert course["has_audit"] is True

        # Only one audit.trail.log model
        audit_models = [m for m in result["models"] if m["name"] == "audit.trail.log"]
        assert len(audit_models) == 1

    def test_non_audited_model_unchanged(self):
        """Non-audited models are passed through unchanged."""
        audited = _make_model(
            name="university.student",
            fields=[{"name": "name", "type": "Char", "required": True}],
            audit=True,
        )
        non_audited = _make_model(
            name="university.course",
            fields=[{"name": "title", "type": "Char", "required": True}],
        )
        spec = _make_spec(
            models=[audited, non_audited],
            security_roles=_make_security_roles(),
        )
        result = _process_audit_patterns(spec)

        course = next(m for m in result["models"] if m["name"] == "university.course")
        assert "has_audit" not in course
        assert "audit_fields" not in course

    def test_preserves_existing_override_sources(self):
        """Audit preprocessor preserves existing override_sources from prior preprocessors."""
        model = _make_model(
            name="university.student",
            fields=[
                {"name": "name", "type": "Char", "required": True},
            ],
            audit=True,
        )
        # Simulate prior preprocessor having set override_sources
        model["override_sources"] = defaultdict(set)
        model["override_sources"]["write"].add("constraints")
        model["override_sources"]["create"].add("bulk")

        spec = _make_spec(
            models=[model],
            security_roles=_make_security_roles(),
        )
        result = _process_audit_patterns(spec)

        enriched = next(m for m in result["models"] if m["name"] == "university.student")
        # Both "constraints" and "audit" should be in write sources
        assert "constraints" in enriched["override_sources"]["write"]
        assert "audit" in enriched["override_sources"]["write"]
        # Create sources should be preserved
        assert "bulk" in enriched["override_sources"]["create"]


# ---------------------------------------------------------------------------
# Helpers for approval preprocessor tests
# ---------------------------------------------------------------------------


def _make_approval_spec(
    models: list[dict[str, Any]] | None = None,
    security_roles: list[dict[str, Any]] | None = None,
    module_name: str = "uni_fee",
) -> dict[str, Any]:
    """Build a minimal spec for approval preprocessor testing."""
    return {
        "module_name": module_name,
        "depends": ["base"],
        "models": models or [],
        "security_roles": security_roles or _make_security_roles(
            roles=["user", "editor", "hod", "dean", "manager"],
            module_name=module_name,
        ),
    }


def _make_approval_model(
    name: str = "fee.request",
    fields: list[dict[str, Any]] | None = None,
    approval: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal approval model dict for testing."""
    model: dict[str, Any] = {
        "name": name,
        "description": name.replace(".", " ").title(),
        "fields": fields or [
            {"name": "name", "type": "Char", "required": True},
            {"name": "amount", "type": "Float"},
            {"name": "notes", "type": "Text"},
        ],
        **kwargs,
    }
    if approval is not None:
        model["approval"] = approval
    return model


def _default_approval_block() -> dict[str, Any]:
    """Return a standard 3-level approval block."""
    return {
        "levels": [
            {"state": "submitted", "role": "editor", "next": "approved_hod", "label": "Submitted"},
            {"state": "approved_hod", "role": "hod", "next": "approved_dean", "label": "HOD Approved"},
            {"state": "approved_dean", "role": "dean", "next": "done", "label": "Dean Approved"},
        ],
        "on_reject": "draft",
        "reject_allowed_from": ["approved_hod", "approved_dean"],
        "lock_after": "draft",
        "editable_fields": ["notes", "rejection_reason"],
    }


# ---------------------------------------------------------------------------
# TestApprovalPreprocessor
# ---------------------------------------------------------------------------


class TestApprovalPreprocessor:
    """Test _process_approval_patterns preprocessor."""

    def test_approval_enriches_model_has_approval_true(self):
        """Spec with approval block produces has_approval=True on enriched model."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["has_approval"] is True

    def test_draft_auto_prepended_as_first_state(self):
        """Draft state is auto-prepended as first Selection value."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        state_field = next(f for f in enriched["fields"] if f["name"] == "state")
        selection = state_field["selection"]
        assert selection[0] == ("draft", "Draft")

    def test_all_level_states_in_selection_in_order(self):
        """All level states appear in synthesized Selection in order."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        state_field = next(f for f in enriched["fields"] if f["name"] == "state")
        keys = [s[0] for s in state_field["selection"]]
        # draft, submitted, approved_hod, approved_dean, done
        assert keys == ["draft", "submitted", "approved_hod", "approved_dean", "done"]

    def test_terminal_state_appended_from_last_level_next(self):
        """Terminal state (last level's 'next') is appended after all levels."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        state_field = next(f for f in enriched["fields"] if f["name"] == "state")
        keys = [s[0] for s in state_field["selection"]]
        assert keys[-1] == "done"

    def test_on_reject_rejected_appends_rejected_state(self):
        """on_reject='rejected' appends ('rejected', 'Rejected') to Selection."""
        approval = _default_approval_block()
        approval["on_reject"] = "rejected"
        model = _make_approval_model(approval=approval)
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        state_field = next(f for f in enriched["fields"] if f["name"] == "state")
        keys = [s[0] for s in state_field["selection"]]
        assert "rejected" in keys
        assert state_field["selection"][-1] == ("rejected", "Rejected")

    def test_on_reject_draft_no_rejected_state(self):
        """on_reject='draft' does NOT append rejected state."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        state_field = next(f for f in enriched["fields"] if f["name"] == "state")
        keys = [s[0] for s in state_field["selection"]]
        assert "rejected" not in keys

    def test_action_methods_one_per_level(self):
        """approval_action_methods list has one entry per approval level."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        methods = enriched["approval_action_methods"]
        assert len(methods) == 3  # 3 levels

    def test_action_method_has_required_keys(self):
        """Each action method dict has name, from_state, to_state, group_xml_id, role_label, from_state_label, button_label."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        methods = enriched["approval_action_methods"]
        required_keys = {"name", "from_state", "to_state", "group_xml_id", "role_label", "from_state_label", "button_label"}
        for method in methods:
            assert required_keys.issubset(method.keys()), f"Missing keys in {method}"

    def test_action_method_first_level_from_draft(self):
        """First action method transitions FROM previous state TO current level state."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        methods = enriched["approval_action_methods"]
        first = methods[0]
        # First level: from "draft" -> to "submitted" (wait, actually per plan,
        # the action transitions FROM previous state TO current level state)
        # Level 0: state=submitted, from_state=draft, to_state=submitted
        assert first["from_state"] == "draft"
        assert first["to_state"] == "submitted"

    def test_role_resolution_uses_module_group_format(self):
        """Role resolution uses {module_name}.group_{module_name}_{role} format."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        methods = enriched["approval_action_methods"]
        # First level has role "editor" -> uni_fee.group_uni_fee_editor
        assert methods[0]["group_xml_id"] == "uni_fee.group_uni_fee_editor"

    def test_explicit_group_override_takes_priority(self):
        """Explicit group override takes priority over role-based resolution."""
        approval = _default_approval_block()
        approval["levels"][1]["group"] = "account.group_account_manager"
        model = _make_approval_model(approval=approval)
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        methods = enriched["approval_action_methods"]
        assert methods[1]["group_xml_id"] == "account.group_account_manager"

    def test_reject_action_generated_when_reject_allowed_from_nonempty(self):
        """Reject action is generated when reject_allowed_from is non-empty."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["approval_reject_action"] is not None

    def test_reset_action_always_generated(self):
        """Reset action (action_reset_to_draft) is always generated."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["approval_reset_action"] is not None
        assert enriched["approval_reset_action"]["name"] == "action_reset_to_draft"

    def test_submit_action_generated(self):
        """Submit action is generated for draft -> first level transition."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        submit = enriched["approval_submit_action"]
        assert submit is not None
        assert submit["name"] == "action_submit"
        assert submit["from_state"] == "draft"
        assert submit["to_state"] == "submitted"

    def test_validates_roles_exist_in_security_roles(self):
        """Preprocessor validates all roles exist in security_roles (raises ValueError for unknown roles)."""
        approval = _default_approval_block()
        # Use a role that doesn't exist in security_roles
        approval["levels"][0]["role"] = "nonexistent_role"
        model = _make_approval_model(approval=approval)
        spec = _make_approval_spec(models=[model])
        with pytest.raises(ValueError, match="nonexistent_role"):
            _process_approval_patterns(spec)

    def test_skips_models_without_approval_block(self):
        """Preprocessor skips models without approval block (returns unchanged)."""
        model = _make_approval_model()  # No approval
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert "has_approval" not in enriched

    def test_no_approval_models_returns_spec_unchanged(self):
        """Spec with no approval models returns spec unchanged."""
        model = _make_approval_model()  # No approval
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        assert result is spec  # Same object -- no changes needed

    def test_override_sources_write_contains_approval(self):
        """override_sources['write'] contains 'approval'."""
        model = _make_approval_model(approval=_default_approval_block())
        model["override_sources"] = defaultdict(set)
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert "approval" in enriched["override_sources"]["write"]

    def test_has_write_override_true_for_approval(self):
        """has_write_override is True for approval models."""
        model = _make_approval_model(approval=_default_approval_block())
        model["override_sources"] = defaultdict(set)
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["has_write_override"] is True

    def test_needs_translate_set_true(self):
        """needs_translate flag is set True on approval models."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["needs_translate"] is True

    def test_existing_state_field_replaced(self):
        """Existing state field in model is replaced by synthesized one."""
        model = _make_approval_model(
            fields=[
                {"name": "name", "type": "Char", "required": True},
                {"name": "state", "type": "Selection", "selection": [("a", "A"), ("b", "B")]},
                {"name": "amount", "type": "Float"},
            ],
            approval=_default_approval_block(),
        )
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        state_fields = [f for f in enriched["fields"] if f["name"] == "state"]
        assert len(state_fields) == 1
        # Should be the synthesized one, not the original
        assert state_fields[0]["selection"][0] == ("draft", "Draft")

    def test_lock_after_defaults_to_draft(self):
        """lock_after defaults to 'draft' when not specified."""
        approval = _default_approval_block()
        del approval["lock_after"]
        model = _make_approval_model(approval=approval)
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["lock_after"] == "draft"

    def test_editable_fields_defaults_to_empty(self):
        """editable_fields defaults to empty list when not specified."""
        approval = _default_approval_block()
        del approval["editable_fields"]
        model = _make_approval_model(approval=approval)
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["editable_fields"] == []

    def test_approval_record_rules_has_two_entries(self):
        """approval_record_rules contains two entries (draft_owner and manager_full)."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert len(enriched["approval_record_rules"]) == 2

    def test_record_rule_scopes_includes_approval(self):
        """record_rule_scopes includes 'approval' scope."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert "approval" in enriched.get("record_rule_scopes", [])

    def test_pure_function_does_not_mutate_input(self):
        """Preprocessor does not mutate original spec."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        original_model_names = [m["name"] for m in spec["models"]]
        _process_approval_patterns(spec)
        current_model_names = [m["name"] for m in spec["models"]]
        assert current_model_names == original_model_names

    def test_preserves_existing_override_sources(self):
        """Approval preprocessor preserves existing override_sources from prior preprocessors."""
        model = _make_approval_model(approval=_default_approval_block())
        model["override_sources"] = defaultdict(set)
        model["override_sources"]["write"].add("constraints")
        model["override_sources"]["create"].add("bulk")
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert "constraints" in enriched["override_sources"]["write"]
        assert "approval" in enriched["override_sources"]["write"]
        assert "bulk" in enriched["override_sources"]["create"]

    def test_state_field_attributes(self):
        """Synthesized state field has default='draft', tracking=True, required=True."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        state_field = next(f for f in enriched["fields"] if f["name"] == "state")
        assert state_field["default"] == "draft"
        assert state_field["tracking"] is True
        assert state_field["required"] is True

    def test_approval_state_field_name_always_state(self):
        """approval_state_field_name is always 'state'."""
        model = _make_approval_model(approval=_default_approval_block())
        spec = _make_approval_spec(models=[model])
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["approval_state_field_name"] == "state"

    def test_role_validation_skipped_when_group_explicit(self):
        """Role validation is skipped when 'group' is explicitly provided."""
        approval = _default_approval_block()
        # Set a non-existent role but provide explicit group
        approval["levels"][0]["role"] = "nonexistent_role"
        approval["levels"][0]["group"] = "some_module.group_something"
        model = _make_approval_model(approval=approval)
        spec = _make_approval_spec(models=[model])
        # Should NOT raise ValueError because group is explicitly provided
        result = _process_approval_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["has_approval"] is True


# ---------------------------------------------------------------------------
# Helpers for notification/webhook preprocessor tests
# ---------------------------------------------------------------------------


def _make_notify_approval_block(
    notify_on_levels: list[int] | None = None,
    on_reject_notify: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a 3-level approval block with optional notify on specified levels."""
    levels = [
        {"state": "submitted", "role": "editor", "next": "approved_hod", "label": "Submitted"},
        {"state": "approved_hod", "role": "hod", "next": "approved_dean", "label": "HOD Approved"},
        {"state": "approved_dean", "role": "dean", "next": "done", "label": "Dean Approved"},
    ]
    if notify_on_levels is not None:
        for idx in notify_on_levels:
            if idx == 0:
                levels[0]["notify"] = {
                    "template": "email_fee_waiver_submitted",
                    "recipients": "role:hod",
                    "subject": "Fee Waiver Submitted: {{ object.name }}",
                }
            elif idx == 1:
                levels[1]["notify"] = {
                    "template": "email_fee_waiver_approved_hod",
                    "recipients": "role:dean",
                    "subject": "Fee Waiver Approved by HOD: {{ object.name }}",
                }
            elif idx == 2:
                levels[2]["notify"] = {
                    "template": "email_fee_waiver_approved_dean",
                    "recipients": "creator",
                    "subject": "Fee Waiver Final Approval: {{ object.name }}",
                }
    block: dict[str, Any] = {
        "levels": levels,
        "on_reject": "draft",
        "reject_allowed_from": ["approved_hod", "approved_dean"],
        "lock_after": "draft",
        "editable_fields": ["notes"],
    }
    if on_reject_notify is not None:
        block["on_reject_notify"] = on_reject_notify
    return block


def _make_notify_spec(
    models: list[dict[str, Any]] | None = None,
    security_roles: list[dict[str, Any]] | None = None,
    module_name: str = "uni_fee",
    depends: list[str] | None = None,
) -> dict[str, Any]:
    """Build a spec for notification preprocessor testing.

    The spec already has approval preprocessor run on it (so models are enriched
    with approval_action_methods, approval_submit_action, etc.).
    """
    spec: dict[str, Any] = {
        "module_name": module_name,
        "depends": depends or ["base"],
        "models": models or [],
        "security_roles": security_roles or _make_security_roles(
            roles=["user", "editor", "hod", "dean", "manager"],
            module_name=module_name,
        ),
    }
    # Pre-process approval so notification preprocessor has enriched data
    return _process_approval_patterns(spec)


def _make_notify_model(
    name: str = "fee.request",
    fields: list[dict[str, Any]] | None = None,
    approval: dict[str, Any] | None = None,
    webhooks: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a model dict for notification/webhook testing."""
    model: dict[str, Any] = {
        "name": name,
        "description": name.replace(".", " ").title(),
        "fields": fields or [
            {"name": "name", "type": "Char", "required": True, "string": "Request Name"},
            {"name": "amount", "type": "Float", "required": True, "string": "Amount"},
            {"name": "notes", "type": "Text", "string": "Notes"},
            {"name": "student_id", "type": "Many2one", "comodel_name": "res.partner", "string": "Student"},
            {"name": "supervisor_id", "type": "Many2one", "comodel_name": "res.users", "string": "Supervisor"},
        ],
        **kwargs,
    }
    if approval is not None:
        model["approval"] = approval
    if webhooks is not None:
        model["webhooks"] = webhooks
    return model


# ---------------------------------------------------------------------------
# TestNotificationPreprocessor
# ---------------------------------------------------------------------------


class TestNotificationPreprocessor:
    """Test _process_notification_patterns preprocessor."""

    def test_no_approval_no_change(self):
        """Spec without approval returns unchanged."""
        model = _make_notify_model()
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": _make_security_roles(
                roles=["user", "editor", "hod", "dean", "manager"],
                module_name="uni_fee",
            ),
        }
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert "has_notifications" not in enriched or enriched.get("has_notifications") is False

    def test_approval_without_notify_no_change(self):
        """Approval levels without notify objects produce no notification metadata."""
        approval = _make_notify_approval_block(notify_on_levels=None)
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert not enriched.get("has_notifications")

    def test_notify_on_level_enriches_action_method(self):
        """A level with notify object adds notification sub-dict to the corresponding approval_action_methods entry."""
        approval = _make_notify_approval_block(notify_on_levels=[1])
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        # Level 1 (index 1) = approved_hod -> action_approve_approved_hod
        method = next(
            m for m in enriched["approval_action_methods"]
            if m["name"] == "action_approve_approved_hod"
        )
        assert "notification" in method
        assert "template_xml_id" in method["notification"]

    def test_notify_on_first_level_enriches_submit(self):
        """Notify on levels[0] enriches approval_submit_action with notification."""
        approval = _make_notify_approval_block(notify_on_levels=[0])
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        submit = enriched["approval_submit_action"]
        assert "notification" in submit
        assert "template_xml_id" in submit["notification"]

    def test_on_reject_notify_enriches_reject_action(self):
        """on_reject_notify at approval root enriches approval_reject_action with notification."""
        approval = _make_notify_approval_block(
            notify_on_levels=[0],
            on_reject_notify={
                "template": "email_fee_waiver_rejected",
                "recipients": "creator",
                "subject": "Fee Waiver Rejected: {{ object.name }}",
            },
        )
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        reject = enriched["approval_reject_action"]
        assert "notification" in reject
        assert "template_xml_id" in reject["notification"]

    def test_notification_templates_list(self):
        """All notify objects produce a flat notification_templates list on the model."""
        approval = _make_notify_approval_block(notify_on_levels=[0, 1])
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        templates = enriched["notification_templates"]
        assert len(templates) == 2
        for t in templates:
            assert "xml_id" in t
            assert "name" in t
            assert "subject" in t
            assert "email_to" in t

    def test_mail_dependency_added(self):
        """Notification presence adds 'mail' to spec['depends'] if not already present."""
        approval = _make_notify_approval_block(notify_on_levels=[0])
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model], depends=["base"])
        result = _process_notification_patterns(spec)
        assert "mail" in result["depends"]

    def test_mail_dependency_not_duplicated(self):
        """If 'mail' already in depends, it is not added again."""
        approval = _make_notify_approval_block(notify_on_levels=[0])
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model], depends=["base", "mail"])
        result = _process_notification_patterns(spec)
        assert result["depends"].count("mail") == 1

    def test_has_notifications_flag(self):
        """Model gets has_notifications=True when any level has notify."""
        approval = _make_notify_approval_block(notify_on_levels=[0])
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["has_notifications"] is True

    def test_needs_logger_flag(self):
        """Model gets needs_logger=True when has_notifications."""
        approval = _make_notify_approval_block(notify_on_levels=[0])
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["needs_logger"] is True

    def test_recipient_creator(self):
        """'creator' resolves to email_to with create_uid.partner_id.email."""
        approval = _make_notify_approval_block(
            notify_on_levels=[],
            on_reject_notify={
                "template": "email_rejected",
                "recipients": "creator",
                "subject": "Rejected",
            },
        )
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        reject = enriched["approval_reject_action"]
        assert "create_uid.partner_id.email" in reject["notification"]["email_to"]

    def test_recipient_role(self):
        """'role:hod' resolves to email_to with group-based expression."""
        approval = _make_notify_approval_block(notify_on_levels=[0])
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        submit = enriched["approval_submit_action"]
        email_to = submit["notification"]["email_to"]
        assert "group_uni_fee_hod" in email_to

    def test_recipient_field(self):
        """'field:supervisor_id' resolves to email_to with object.supervisor_id.email."""
        approval = _make_notify_approval_block(notify_on_levels=[])
        approval["levels"][0]["notify"] = {
            "template": "email_notify_supervisor",
            "recipients": "field:supervisor_id",
            "subject": "Notification",
        }
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        submit = enriched["approval_submit_action"]
        assert "object.supervisor_id.email" in submit["notification"]["email_to"]

    def test_recipient_fixed(self):
        """'fixed:admin@test.com' resolves to email_to='admin@test.com'."""
        approval = _make_notify_approval_block(notify_on_levels=[])
        approval["levels"][0]["notify"] = {
            "template": "email_notify_admin",
            "recipients": "fixed:admin@test.com",
            "subject": "Admin Notification",
        }
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        submit = enriched["approval_submit_action"]
        assert submit["notification"]["email_to"] == "admin@test.com"

    def test_body_fields_selection(self):
        """body_fields excludes Binary, O2m, M2m, computed, technical fields; includes name + up to 3-4 fields."""
        approval = _make_notify_approval_block(notify_on_levels=[0])
        model = _make_notify_model(
            approval=approval,
            fields=[
                {"name": "name", "type": "Char", "required": True, "string": "Name"},
                {"name": "amount", "type": "Float", "required": True, "string": "Amount"},
                {"name": "notes", "type": "Text", "string": "Notes"},
                {"name": "photo", "type": "Binary", "string": "Photo"},
                {"name": "tag_ids", "type": "Many2many", "comodel_name": "tag", "string": "Tags"},
                {"name": "line_ids", "type": "One2many", "comodel_name": "line", "string": "Lines"},
                {"name": "total", "type": "Float", "compute": "_compute_total", "string": "Total"},
                {"name": "create_uid", "type": "Many2one", "comodel_name": "res.users"},
                {"name": "write_date", "type": "Datetime"},
            ],
        )
        spec = _make_notify_spec(models=[model])
        result = _process_notification_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        templates = enriched["notification_templates"]
        assert len(templates) >= 1
        body_fields = templates[0]["body_fields"]
        field_names = {f["name"] for f in body_fields}
        # Should include name and amount
        assert "name" in field_names
        # Should NOT include excluded types
        assert "photo" not in field_names
        assert "tag_ids" not in field_names
        assert "line_ids" not in field_names
        assert "total" not in field_names  # computed
        assert "create_uid" not in field_names
        assert "write_date" not in field_names
        # Max fields constraint
        assert len(body_fields) <= 5

    def test_pure_function(self):
        """Input spec is not mutated."""
        approval = _make_notify_approval_block(notify_on_levels=[0, 1])
        model = _make_notify_model(approval=approval)
        spec = _make_notify_spec(models=[model])
        original_model_names = [m["name"] for m in spec["models"]]
        original_depends = list(spec["depends"])
        _process_notification_patterns(spec)
        assert [m["name"] for m in spec["models"]] == original_model_names
        assert spec["depends"] == original_depends


# ---------------------------------------------------------------------------
# TestWebhookPreprocessor
# ---------------------------------------------------------------------------


class TestWebhookPreprocessor:
    """Test _process_webhook_patterns preprocessor."""

    def test_no_webhooks_no_change(self):
        """Spec without webhooks returns unchanged."""
        model = _make_notify_model()
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [],
        }
        result = _process_webhook_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert not enriched.get("has_webhooks")

    def test_on_create_adds_create_override(self):
        """webhooks.on_create=true adds 'webhooks' to override_sources['create']."""
        model = _make_notify_model(
            webhooks={"on_create": True, "on_write": [], "on_unlink": False},
        )
        model["override_sources"] = defaultdict(set)
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [],
        }
        result = _process_webhook_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert "webhooks" in enriched["override_sources"]["create"]

    def test_on_write_adds_write_override(self):
        """webhooks.on_write=['state','amount'] adds 'webhooks' to override_sources['write']."""
        model = _make_notify_model(
            webhooks={"on_create": False, "on_write": ["state", "amount"], "on_unlink": False},
        )
        model["override_sources"] = defaultdict(set)
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [],
        }
        result = _process_webhook_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert "webhooks" in enriched["override_sources"]["write"]

    def test_webhook_watched_fields(self):
        """on_write field list stored as webhook_watched_fields on model."""
        model = _make_notify_model(
            webhooks={"on_create": False, "on_write": ["state", "amount"], "on_unlink": False},
        )
        model["override_sources"] = defaultdict(set)
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [],
        }
        result = _process_webhook_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["webhook_watched_fields"] == ["state", "amount"]

    def test_has_webhooks_flag(self):
        """Model gets has_webhooks=True."""
        model = _make_notify_model(
            webhooks={"on_create": True, "on_write": [], "on_unlink": False},
        )
        model["override_sources"] = defaultdict(set)
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [],
        }
        result = _process_webhook_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["has_webhooks"] is True

    def test_webhook_config(self):
        """webhook_config dict stored on model with on_create, on_write, on_unlink keys."""
        model = _make_notify_model(
            webhooks={"on_create": True, "on_write": ["state"], "on_unlink": True},
        )
        model["override_sources"] = defaultdict(set)
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [],
        }
        result = _process_webhook_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        config = enriched["webhook_config"]
        assert config["on_create"] is True
        assert config["on_write"] == ["state"]
        assert config["on_unlink"] is True

    def test_on_unlink_stub(self):
        """on_unlink=true sets webhook_on_unlink=True on model."""
        model = _make_notify_model(
            webhooks={"on_create": False, "on_write": [], "on_unlink": True},
        )
        model["override_sources"] = defaultdict(set)
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [],
        }
        result = _process_webhook_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert enriched["webhook_on_unlink"] is True

    def test_override_sources_merge_with_audit(self):
        """When audit already added 'audit' to override_sources['write'], webhooks adds 'webhooks' alongside without clobbering."""
        model = _make_notify_model(
            webhooks={"on_create": False, "on_write": ["state"], "on_unlink": False},
        )
        model["override_sources"] = defaultdict(set)
        model["override_sources"]["write"].add("audit")
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [],
        }
        result = _process_webhook_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert "audit" in enriched["override_sources"]["write"]
        assert "webhooks" in enriched["override_sources"]["write"]

    def test_override_sources_merge_with_approval(self):
        """When approval already added 'approval' to override_sources['write'], webhooks coexists."""
        model = _make_notify_model(
            webhooks={"on_create": True, "on_write": ["state"], "on_unlink": False},
        )
        model["override_sources"] = defaultdict(set)
        model["override_sources"]["write"].add("approval")
        model["override_sources"]["create"].add("bulk")
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [],
        }
        result = _process_webhook_patterns(spec)
        enriched = next(m for m in result["models"] if m["name"] == "fee.request")
        assert "approval" in enriched["override_sources"]["write"]
        assert "webhooks" in enriched["override_sources"]["write"]
        assert "bulk" in enriched["override_sources"]["create"]
        assert "webhooks" in enriched["override_sources"]["create"]

    def test_pure_function(self):
        """Input spec is not mutated."""
        model = _make_notify_model(
            webhooks={"on_create": True, "on_write": ["state"], "on_unlink": True},
        )
        model["override_sources"] = defaultdict(set)
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [],
        }
        original_model_names = [m["name"] for m in spec["models"]]
        _process_webhook_patterns(spec)
        assert [m["name"] for m in spec["models"]] == original_model_names
        assert not spec["models"][0].get("has_webhooks")


# ---------------------------------------------------------------------------
# Commit 6: Delegation enrichment tests
# ---------------------------------------------------------------------------


class TestEnrichDelegation:
    """Tests for _enrich_delegation from relationships.py."""

    def test_adds_many2one_field(self):
        """Delegation injects a Many2one field with delegate=True."""
        model = {"name": "uni.student", "fields": []}
        models = [model]
        rel = {
            "type": "delegation",
            "model": "uni.student",
            "delegate_model": "res.partner",
            "delegate_field": "partner_id",
        }
        _enrich_delegation(models, rel)
        field_names = [f["name"] for f in model["fields"]]
        assert "partner_id" in field_names
        partner_field = next(f for f in model["fields"] if f["name"] == "partner_id")
        assert partner_field["type"] == "Many2one"
        assert partner_field["comodel_name"] == "res.partner"
        assert partner_field["delegate"] is True

    def test_sets_inherits(self):
        """Delegation sets _inherits mapping on the target model."""
        model = {"name": "uni.student", "fields": []}
        models = [model]
        rel = {
            "type": "delegation",
            "model": "uni.student",
            "delegate_model": "res.partner",
            "delegate_field": "partner_id",
        }
        _enrich_delegation(models, rel)
        assert model["_inherits"] == {"res.partner": "partner_id"}
        assert model["has_delegation"] is True

    def test_skips_existing_field(self):
        """Delegation does not duplicate an already-present delegate field."""
        model = {
            "name": "uni.student",
            "fields": [
                {"name": "partner_id", "type": "Many2one", "comodel_name": "res.partner"},
            ],
        }
        models = [model]
        rel = {
            "type": "delegation",
            "model": "uni.student",
            "delegate_model": "res.partner",
            "delegate_field": "partner_id",
        }
        _enrich_delegation(models, rel)
        partner_fields = [f for f in model["fields"] if f["name"] == "partner_id"]
        assert len(partner_fields) == 1

    def test_unknown_model_noop(self):
        """Delegation is a no-op when the target model doesn't exist."""
        model = {"name": "uni.student", "fields": []}
        models = [model]
        rel = {
            "type": "delegation",
            "model": "nonexistent.model",
            "delegate_model": "res.partner",
            "delegate_field": "partner_id",
        }
        _enrich_delegation(models, rel)
        assert not model.get("_inherits")
        assert not model.get("has_delegation")


class TestEnrichHierarchical:
    """Tests for _enrich_hierarchical from relationships.py."""

    def test_injects_parent_child_fields(self):
        """Hierarchical enrichment adds parent_id, parent_path, child_ids."""
        model = {"name": "uni.department", "fields": []}
        models = [model]
        rel = {
            "type": "hierarchical",
            "model": "uni.department",
            "string": "Parent Department",
        }
        _enrich_hierarchical(models, rel)
        field_names = {f["name"] for f in model["fields"]}
        assert "parent_id" in field_names
        assert "parent_path" in field_names
        assert "child_ids" in field_names
        assert model["hierarchical"] is True
        assert model["_parent_name"] == "parent_id"


# ---------------------------------------------------------------------------
# Commit 7: Webhook endpoint synthesis tests
# ---------------------------------------------------------------------------


class TestBuildWebhookEndpointModel:
    """Tests for _build_webhook_endpoint_model from webhooks.py."""

    def test_model_synthesis(self):
        """Synthesized model has correct name and required fields."""
        model = _build_webhook_endpoint_model("test_module")
        assert model["name"] == "webhook.endpoint"
        assert model["_synthesized"] is True
        field_names = {f["name"] for f in model["fields"]}
        assert "url" in field_names
        assert "secret_token" in field_names
        assert "events" in field_names
        assert "target_model" in field_names
        assert "active" in field_names
        assert "max_retries" in field_names
        assert "retry_delay_seconds" in field_names

    def test_retry_defaults(self):
        """Synthesized model has sensible retry defaults."""
        model = _build_webhook_endpoint_model("test_module")
        max_retries_field = next(
            f for f in model["fields"] if f["name"] == "max_retries"
        )
        assert max_retries_field["default"] == 3
        retry_delay_field = next(
            f for f in model["fields"] if f["name"] == "retry_delay_seconds"
        )
        assert retry_delay_field["default"] == 60


class TestWebhookMailActivityDispatch:
    """Tests for mail_activity dispatch in notification patterns."""

    def test_mail_activity_dispatch_sets_activity_fields(self):
        """When dispatch is mail_activity, template entry has activity fields."""
        model = _make_notify_model(
            approval={
                "levels": [
                    {
                        "state": "manager_approved",
                        "role": "manager",
                        "next": "approved",
                        "notify": {
                            "template": "tmpl_mgr",
                            "recipients": "creator",
                            "subject": "Approved",
                            "dispatch": "mail_activity",
                            "activity_summary": "Review needed",
                        },
                    },
                ],
                "on_reject": "draft",
            },
        )
        spec = {
            "module_name": "uni_fee",
            "depends": ["base"],
            "models": [model],
            "security_roles": [{"name": "manager", "label": "Manager"}],
        }
        # First run approval to enrich model
        spec = _process_approval_patterns(spec)
        result = _process_notification_patterns(spec)
        enriched = result["models"][0]
        assert enriched.get("has_notifications") is True
        templates = enriched.get("notification_templates", [])
        assert len(templates) >= 1
        tmpl = templates[0]
        assert tmpl["dispatch_method"] == "mail_activity"
        assert tmpl.get("activity_summary") == "Review needed"
        # mail_activity dispatch should NOT inject "mail" into depends
        assert "mail" not in result.get("depends", [])
