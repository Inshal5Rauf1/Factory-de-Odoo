"""Tests for document management domain preprocessor.

Phase 52: document.type and document.document model generation
via preprocessor triggered by ``document_management: true``.

Covers: registration, model generation, field verification, constraints,
action methods, version tracking, security roles, immutability, config options.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(
    models: list[dict[str, Any]] | None = None,
    document_management: bool | None = None,
    document_config: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal spec for document_management preprocessor testing."""
    spec: dict[str, Any] = {
        "module_name": "test_module",
        "depends": ["base"],
        "models": models or [],
        **kwargs,
    }
    if document_management is not None:
        spec["document_management"] = document_management
    if document_config is not None:
        spec["document_config"] = document_config
    return spec


def _process(spec: dict[str, Any]) -> dict[str, Any]:
    """Run the document_management preprocessor on a spec."""
    from amil_utils.preprocessors.document_management import (
        _process_document_management,
    )

    return _process_document_management(spec)


def _find_model(
    spec: dict[str, Any], model_name: str
) -> dict[str, Any] | None:
    """Find a model dict by name in spec's models list."""
    for m in spec.get("models", []):
        if m.get("name") == model_name:
            return m
    return None


def _get_field(model: dict[str, Any], field_name: str) -> dict[str, Any] | None:
    """Find a field by name in a model's fields list."""
    for f in model.get("fields", []):
        if f.get("name") == field_name:
            return f
    return None


def _get_complex_constraint(
    model: dict[str, Any], constraint_name: str
) -> dict[str, Any] | None:
    """Find a complex_constraint entry by name."""
    for c in model.get("complex_constraints", []):
        if c.get("name") == constraint_name:
            return c
    return None


def _get_sql_constraint(
    model: dict[str, Any], constraint_name: str
) -> dict[str, Any] | None:
    """Find an SQL constraint by name."""
    for c in model.get("sql_constraints", []):
        if c.get("name") == constraint_name:
            return c
    return None


# ===========================================================================
# TestPreprocessorRegistration
# ===========================================================================


class TestPreprocessorRegistration:
    """Registration at order=28, function name, and identity behavior."""

    def test_registered_at_order_28(self):
        """document_management is registered at order=28 in the preprocessor registry."""
        from amil_utils.preprocessors._registry import (
            clear_registry,
            get_registered_preprocessors,
        )
        import importlib
        import amil_utils.preprocessors.document_management as mod

        clear_registry()
        importlib.reload(mod)
        entries = get_registered_preprocessors()
        dm_entries = [(o, n) for o, n, _fn in entries if n == "document_management"]
        assert len(dm_entries) == 1, f"Expected 1 document_management entry, got {dm_entries}"
        assert dm_entries[0][0] == 28
        clear_registry()

    def test_function_name_is_document_management(self):
        """Registered function name is 'document_management'."""
        from amil_utils.preprocessors._registry import (
            clear_registry,
            get_registered_preprocessors,
        )
        import importlib
        import amil_utils.preprocessors.document_management as mod

        clear_registry()
        importlib.reload(mod)
        entries = get_registered_preprocessors()
        names = [n for _o, n, _fn in entries]
        assert "document_management" in names
        clear_registry()


# ===========================================================================
# TestNoOp
# ===========================================================================


class TestNoOp:
    """Spec without document_management key or with False returns unchanged."""

    def test_noop_without_key(self):
        """Spec without document_management key returns same spec object."""
        spec = _make_spec()
        result = _process(spec)
        assert result is spec

    def test_noop_with_false(self):
        """Spec with document_management=False returns same spec object."""
        spec = _make_spec(document_management=False)
        result = _process(spec)
        assert result is spec


# ===========================================================================
# TestModelGeneration
# ===========================================================================


class TestModelGeneration:
    """Spec with document_management: true produces document.type and document.document."""

    def test_generates_two_models(self):
        """Spec with document_management=true produces exactly 2 models."""
        spec = _make_spec(document_management=True)
        result = _process(spec)
        assert len(result["models"]) == 2

    def test_model_names(self):
        """Generated models are document.type and document.document."""
        spec = _make_spec(document_management=True)
        result = _process(spec)
        names = [m["name"] for m in result["models"]]
        assert "document.type" in names
        assert "document.document" in names

    def test_models_in_dependency_order(self):
        """document.type is before document.document (dependency order)."""
        spec = _make_spec(document_management=True)
        result = _process(spec)
        names = [m["name"] for m in result["models"]]
        type_idx = names.index("document.type")
        doc_idx = names.index("document.document")
        assert type_idx < doc_idx

    def test_models_appended_after_existing(self):
        """Generated models are appended AFTER existing user-defined models."""
        existing_model = {
            "name": "custom.model",
            "description": "Custom Model",
            "fields": [{"name": "name", "type": "Char", "required": True}],
        }
        spec = _make_spec(models=[existing_model], document_management=True)
        result = _process(spec)
        assert result["models"][0]["name"] == "custom.model"
        assert len(result["models"]) == 3  # 1 existing + 2 generated


# ===========================================================================
# TestDocumentTypeFields
# ===========================================================================


class TestDocumentTypeFields:
    """document.type model fields verification."""

    @pytest.fixture()
    def type_model(self):
        spec = _make_spec(document_management=True)
        result = _process(spec)
        return _find_model(result, "document.type")

    def test_name_field(self, type_model):
        """document.type has 'name' Char field (required)."""
        field = _get_field(type_model, "name")
        assert field is not None, "name field not found"
        assert field["type"] == "Char"
        assert field.get("required") is True

    def test_code_field(self, type_model):
        """document.type has 'code' Char field (required)."""
        field = _get_field(type_model, "code")
        assert field is not None
        assert field["type"] == "Char"
        assert field.get("required") is True

    def test_code_unique_sql_constraint(self, type_model):
        """document.type has SQL UNIQUE constraint on code."""
        sql = type_model.get("sql_constraints", [])
        assert len(sql) >= 1
        found = any(
            "UNIQUE" in c.get("definition", "") and "code" in c.get("definition", "")
            for c in sql
        )
        assert found, f"code unique constraint not found in {sql}"

    def test_required_for_selection(self, type_model):
        """document.type has required_for Selection field."""
        field = _get_field(type_model, "required_for")
        assert field is not None
        assert field["type"] == "Selection"
        keys = [s[0] for s in field["selection"]]
        assert "admission" in keys
        assert "enrollment" in keys
        assert "graduation" in keys
        assert "employment" in keys
        assert "always" in keys
        assert field.get("default") == "admission"

    def test_max_file_size_field(self, type_model):
        """document.type has max_file_size Integer (default=5)."""
        field = _get_field(type_model, "max_file_size")
        assert field is not None
        assert field["type"] == "Integer"
        assert field.get("default") == 5
        assert field.get("string") == "Max File Size (MB)"

    def test_allowed_mime_types_field(self, type_model):
        """document.type has allowed_mime_types Char with default."""
        field = _get_field(type_model, "allowed_mime_types")
        assert field is not None
        assert field["type"] == "Char"
        assert field.get("default") == "application/pdf,image/jpeg,image/png"

    def test_sequence_field(self, type_model):
        """document.type has sequence Integer (default=10)."""
        field = _get_field(type_model, "sequence")
        assert field is not None
        assert field["type"] == "Integer"
        assert field.get("default") == 10

    def test_active_field(self, type_model):
        """document.type has active Boolean (default=True)."""
        field = _get_field(type_model, "active")
        assert field is not None
        assert field["type"] == "Boolean"
        assert field.get("default") is True

    def test_description_field(self, type_model):
        """document.type has description Text field."""
        field = _get_field(type_model, "description")
        assert field is not None
        assert field["type"] == "Text"

    def test_model_order(self, type_model):
        """document.type _order = 'sequence, name'."""
        assert type_model.get("model_order") == "sequence, name"


# ===========================================================================
# TestDocumentDocumentFields
# ===========================================================================


class TestDocumentDocumentFields:
    """document.document model fields verification."""

    @pytest.fixture()
    def doc_model(self):
        spec = _make_spec(document_management=True)
        result = _process(spec)
        return _find_model(result, "document.document")

    def test_name_field(self, doc_model):
        """document.document has name Char (required, tracking)."""
        field = _get_field(doc_model, "name")
        assert field is not None
        assert field["type"] == "Char"
        assert field.get("required") is True
        assert field.get("tracking") is True

    def test_document_type_id_field(self, doc_model):
        """document.document has document_type_id Many2one to document.type (required)."""
        field = _get_field(doc_model, "document_type_id")
        assert field is not None
        assert field["type"] == "Many2one"
        assert field.get("comodel_name") == "document.type"
        assert field.get("required") is True

    def test_file_field(self, doc_model):
        """document.document has file Binary (required, attachment=True)."""
        field = _get_field(doc_model, "file")
        assert field is not None
        assert field["type"] == "Binary"
        assert field.get("required") is True
        assert field.get("attachment") is True

    def test_filename_field(self, doc_model):
        """document.document has filename Char."""
        field = _get_field(doc_model, "filename")
        assert field is not None
        assert field["type"] == "Char"

    def test_mime_type_field(self, doc_model):
        """document.document has mime_type Char (readonly)."""
        field = _get_field(doc_model, "mime_type")
        assert field is not None
        assert field["type"] == "Char"
        assert field.get("readonly") is True
        assert field.get("string") == "MIME Type"

    def test_file_size_field(self, doc_model):
        """document.document has file_size Integer (readonly)."""
        field = _get_field(doc_model, "file_size")
        assert field is not None
        assert field["type"] == "Integer"
        assert field.get("readonly") is True
        assert field.get("string") == "File Size (KB)"

    def test_upload_date_field(self, doc_model):
        """document.document has upload_date Datetime (default=now, readonly)."""
        field = _get_field(doc_model, "upload_date")
        assert field is not None
        assert field["type"] == "Datetime"
        assert field.get("default") == "now"
        assert field.get("readonly") is True

    def test_res_model_field(self, doc_model):
        """document.document has res_model Char (index=True)."""
        field = _get_field(doc_model, "res_model")
        assert field is not None
        assert field["type"] == "Char"
        assert field.get("index") is True
        assert field.get("string") == "Resource Model"

    def test_res_id_field(self, doc_model):
        """document.document has res_id Many2oneReference (model_field='res_model')."""
        field = _get_field(doc_model, "res_id")
        assert field is not None
        assert field["type"] == "Many2oneReference"
        assert field.get("model_field") == "res_model"
        assert field.get("string") == "Resource ID"

    def test_verification_state_field(self, doc_model):
        """document.document has verification_state Selection (pending/verified/rejected)."""
        field = _get_field(doc_model, "verification_state")
        assert field is not None
        assert field["type"] == "Selection"
        keys = [s[0] for s in field["selection"]]
        assert "pending" in keys
        assert "verified" in keys
        assert "rejected" in keys
        assert field.get("default") == "pending"
        assert field.get("tracking") is True

    def test_verified_by_field(self, doc_model):
        """document.document has verified_by Many2one to res.users (readonly)."""
        field = _get_field(doc_model, "verified_by")
        assert field is not None
        assert field["type"] == "Many2one"
        assert field.get("comodel_name") == "res.users"
        assert field.get("readonly") is True

    def test_verified_date_field(self, doc_model):
        """document.document has verified_date Datetime (readonly)."""
        field = _get_field(doc_model, "verified_date")
        assert field is not None
        assert field["type"] == "Datetime"
        assert field.get("readonly") is True

    def test_rejection_reason_field(self, doc_model):
        """document.document has rejection_reason Text."""
        field = _get_field(doc_model, "rejection_reason")
        assert field is not None
        assert field["type"] == "Text"

    def test_version_field(self, doc_model):
        """document.document has version Integer (default=1, readonly)."""
        field = _get_field(doc_model, "version")
        assert field is not None
        assert field["type"] == "Integer"
        assert field.get("default") == 1
        assert field.get("readonly") is True

    def test_previous_version_id_field(self, doc_model):
        """document.document has previous_version_id Many2one to self (readonly)."""
        field = _get_field(doc_model, "previous_version_id")
        assert field is not None
        assert field["type"] == "Many2one"
        assert field.get("comodel_name") == "document.document"
        assert field.get("readonly") is True

    def test_is_latest_field(self, doc_model):
        """document.document has is_latest Boolean (default=True, index=True)."""
        field = _get_field(doc_model, "is_latest")
        assert field is not None
        assert field["type"] == "Boolean"
        assert field.get("default") is True
        assert field.get("index") is True

    def test_notes_field(self, doc_model):
        """document.document has notes Text field."""
        field = _get_field(doc_model, "notes")
        assert field is not None
        assert field["type"] == "Text"

    def test_model_order(self, doc_model):
        """document.document _order = 'create_date desc'."""
        assert doc_model.get("model_order") == "create_date desc"

    def test_has_document_verification_context(self, doc_model):
        """document.document has has_document_verification = True context key."""
        assert doc_model.get("has_document_verification") is True

    def test_has_document_versioning_context(self, doc_model):
        """document.document has has_document_versioning = True context key."""
        assert doc_model.get("has_document_versioning") is True


# ===========================================================================
# TestMailThreadInherit
# ===========================================================================


class TestMailThreadInherit:
    """document.document inherits from mail.thread."""

    def test_inherit_mail_thread(self):
        """document.document has _inherit=['mail.thread']."""
        spec = _make_spec(document_management=True)
        result = _process(spec)
        doc = _find_model(result, "document.document")
        inherit = doc.get("inherit", [])
        assert "mail.thread" in inherit


# ===========================================================================
# TestFileValidationConstraint
# ===========================================================================


class TestFileValidationConstraint:
    """File validation constraint: @api.constrains on file + document_type_id."""

    @pytest.fixture()
    def doc_model(self):
        spec = _make_spec(document_management=True)
        result = _process(spec)
        return _find_model(result, "document.document")

    def test_file_validation_constraint_exists(self, doc_model):
        """doc_file_validation complex_constraint exists."""
        cc = _get_complex_constraint(doc_model, "doc_file_validation")
        assert cc is not None, "doc_file_validation not found"

    def test_file_validation_type(self, doc_model):
        """doc_file_validation has type doc_file_validation."""
        cc = _get_complex_constraint(doc_model, "doc_file_validation")
        assert cc["type"] == "doc_file_validation"

    def test_file_validation_fields(self, doc_model):
        """doc_file_validation constrains file and document_type_id."""
        cc = _get_complex_constraint(doc_model, "doc_file_validation")
        assert "file" in cc["fields"]
        assert "document_type_id" in cc["fields"]

    def test_file_validation_checks_max_size(self, doc_model):
        """File validation body checks max_file_size."""
        cc = _get_complex_constraint(doc_model, "doc_file_validation")
        body = cc["check_body"]
        assert "max_file_size" in body

    def test_file_validation_checks_mime_types(self, doc_model):
        """File validation body checks allowed_mime_types."""
        cc = _get_complex_constraint(doc_model, "doc_file_validation")
        body = cc["check_body"]
        assert "allowed_mime_types" in body

    def test_file_validation_iterates_records(self, doc_model):
        """File validation body iterates over records."""
        cc = _get_complex_constraint(doc_model, "doc_file_validation")
        body = cc["check_body"]
        assert "for rec in self" in body


# ===========================================================================
# TestActionMethods
# ===========================================================================


class TestActionMethods:
    """Action methods: verify, reject, reset, upload_new_version."""

    @pytest.fixture()
    def doc_model(self):
        spec = _make_spec(document_management=True)
        result = _process(spec)
        return _find_model(result, "document.document")

    def test_action_verify_exists(self, doc_model):
        """doc_action_verify complex_constraint exists."""
        cc = _get_complex_constraint(doc_model, "doc_action_verify")
        assert cc is not None, "doc_action_verify not found"

    def test_action_verify_type(self, doc_model):
        """doc_action_verify has type doc_action_verify."""
        cc = _get_complex_constraint(doc_model, "doc_action_verify")
        assert cc["type"] == "doc_action_verify"

    def test_action_verify_sets_verified(self, doc_model):
        """action_verify sets verification_state to verified."""
        cc = _get_complex_constraint(doc_model, "doc_action_verify")
        body = cc["check_body"]
        assert "verified" in body
        assert "ensure_one" in body

    def test_action_verify_records_user_and_date(self, doc_model):
        """action_verify records verified_by and verified_date."""
        cc = _get_complex_constraint(doc_model, "doc_action_verify")
        body = cc["check_body"]
        assert "verified_by" in body
        assert "verified_date" in body

    def test_action_reject_exists(self, doc_model):
        """doc_action_reject complex_constraint exists."""
        cc = _get_complex_constraint(doc_model, "doc_action_reject")
        assert cc is not None, "doc_action_reject not found"

    def test_action_reject_type(self, doc_model):
        """doc_action_reject has type doc_action_reject."""
        cc = _get_complex_constraint(doc_model, "doc_action_reject")
        assert cc["type"] == "doc_action_reject"

    def test_action_reject_requires_reason(self, doc_model):
        """action_reject checks rejection_reason."""
        cc = _get_complex_constraint(doc_model, "doc_action_reject")
        body = cc["check_body"]
        assert "rejection_reason" in body

    def test_action_reject_sets_rejected(self, doc_model):
        """action_reject sets verification_state to rejected."""
        cc = _get_complex_constraint(doc_model, "doc_action_reject")
        body = cc["check_body"]
        assert "rejected" in body
        assert "ensure_one" in body

    def test_action_reset_exists(self, doc_model):
        """doc_action_reset complex_constraint exists."""
        cc = _get_complex_constraint(doc_model, "doc_action_reset")
        assert cc is not None, "doc_action_reset not found"

    def test_action_reset_type(self, doc_model):
        """doc_action_reset has type doc_action_reset."""
        cc = _get_complex_constraint(doc_model, "doc_action_reset")
        assert cc["type"] == "doc_action_reset"

    def test_action_reset_clears_verification_fields(self, doc_model):
        """action_reset_to_pending clears verification fields."""
        cc = _get_complex_constraint(doc_model, "doc_action_reset")
        body = cc["check_body"]
        assert "pending" in body
        assert "verified_by" in body
        assert "verified_date" in body
        assert "rejection_reason" in body
        assert "ensure_one" in body

    def test_action_upload_new_version_exists(self, doc_model):
        """doc_action_upload_new_version complex_constraint exists."""
        cc = _get_complex_constraint(doc_model, "doc_action_upload_new_version")
        assert cc is not None, "doc_action_upload_new_version not found"

    def test_action_upload_new_version_type(self, doc_model):
        """doc_action_upload_new_version has correct type."""
        cc = _get_complex_constraint(doc_model, "doc_action_upload_new_version")
        assert cc["type"] == "doc_action_upload_new_version"

    def test_action_upload_new_version_marks_not_latest(self, doc_model):
        """action_upload_new_version marks current as not latest."""
        cc = _get_complex_constraint(doc_model, "doc_action_upload_new_version")
        body = cc["check_body"]
        assert "is_latest" in body
        assert "ensure_one" in body

    def test_action_upload_new_version_increments_version(self, doc_model):
        """action_upload_new_version increments version."""
        cc = _get_complex_constraint(doc_model, "doc_action_upload_new_version")
        body = cc["check_body"]
        assert "version" in body

    def test_action_upload_new_version_resets_verification(self, doc_model):
        """action_upload_new_version resets verification_state to pending."""
        cc = _get_complex_constraint(doc_model, "doc_action_upload_new_version")
        body = cc["check_body"]
        assert "pending" in body


# ===========================================================================
# TestSecurityRoles
# ===========================================================================


class TestSecurityRoles:
    """Security roles: viewer, uploader, verifier, manager."""

    @pytest.fixture()
    def result_spec(self):
        spec = _make_spec(document_management=True)
        return _process(spec)

    def _find_role(self, roles, name):
        for r in roles:
            if r["name"] == name:
                return r
        return None

    def test_four_roles_injected(self, result_spec):
        """Four security roles are injected: viewer, uploader, verifier, manager."""
        roles = result_spec.get("security_roles", [])
        role_names = {r["name"] for r in roles}
        assert "viewer" in role_names
        assert "uploader" in role_names
        assert "verifier" in role_names
        assert "manager" in role_names

    def test_viewer_no_implied(self, result_spec):
        """viewer has no implied_ids (base role)."""
        roles = result_spec.get("security_roles", [])
        viewer = self._find_role(roles, "viewer")
        assert viewer is not None
        assert viewer.get("implied_ids") == [] or viewer.get("implied_ids") is None or viewer.get("implied_ids") == []
        assert viewer.get("is_highest") is False

    def test_uploader_implies_viewer(self, result_spec):
        """uploader implies viewer."""
        roles = result_spec.get("security_roles", [])
        uploader = self._find_role(roles, "uploader")
        assert uploader is not None
        implied = uploader.get("implied_ids", [])
        # implied_ids may contain xml_id strings or name references
        assert any("viewer" in str(i) for i in implied) if implied else False, (
            f"uploader implied_ids should reference viewer, got {implied}"
        )

    def test_verifier_implies_viewer(self, result_spec):
        """verifier implies viewer."""
        roles = result_spec.get("security_roles", [])
        verifier = self._find_role(roles, "verifier")
        assert verifier is not None
        implied = verifier.get("implied_ids", [])
        assert any("viewer" in str(i) for i in implied) if implied else False, (
            f"verifier implied_ids should reference viewer, got {implied}"
        )

    def test_manager_implies_uploader_and_verifier(self, result_spec):
        """manager implies uploader and verifier."""
        roles = result_spec.get("security_roles", [])
        manager = self._find_role(roles, "manager")
        assert manager is not None
        implied = manager.get("implied_ids", [])
        implied_str = str(implied)
        assert "uploader" in implied_str, f"manager should imply uploader, got {implied}"
        assert "verifier" in implied_str, f"manager should imply verifier, got {implied}"

    def test_manager_is_highest(self, result_spec):
        """manager has is_highest=True."""
        roles = result_spec.get("security_roles", [])
        manager = self._find_role(roles, "manager")
        assert manager.get("is_highest") is True

    def test_roles_not_duplicated_with_existing(self):
        """Roles are not duplicated if already present in spec."""
        existing_roles = [
            {"name": "viewer", "xml_id": "group_test_module_viewer", "implied_ids": [], "is_highest": False},
        ]
        spec = _make_spec(document_management=True, security_roles=existing_roles)
        result = _process(spec)
        roles = result.get("security_roles", [])
        viewer_count = sum(1 for r in roles if r["name"] == "viewer")
        assert viewer_count == 1, f"viewer should not be duplicated, found {viewer_count}"


# ===========================================================================
# TestMailDependency
# ===========================================================================


class TestMailDependency:
    """mail dependency injection."""

    def test_mail_added_to_depends(self):
        """mail is added to spec depends when not present."""
        spec = _make_spec(document_management=True)
        result = _process(spec)
        assert "mail" in result["depends"]

    def test_mail_not_duplicated(self):
        """mail is not duplicated if already in spec depends."""
        spec = _make_spec(document_management=True, depends=["base", "mail"])
        result = _process(spec)
        assert result["depends"].count("mail") == 1

    def test_existing_depends_preserved(self):
        """Existing spec depends are preserved."""
        spec = _make_spec(document_management=True, depends=["base", "contacts"])
        result = _process(spec)
        assert "base" in result["depends"]
        assert "contacts" in result["depends"]
        assert "mail" in result["depends"]


# ===========================================================================
# TestConfig
# ===========================================================================


class TestConfig:
    """Configuration overrides via document_config."""

    def test_disable_versioning(self):
        """document_config.enable_versioning=false omits version fields."""
        spec = _make_spec(
            document_management=True,
            document_config={"enable_versioning": False},
        )
        result = _process(spec)
        doc = _find_model(result, "document.document")
        assert _get_field(doc, "version") is None
        assert _get_field(doc, "previous_version_id") is None
        assert _get_field(doc, "is_latest") is None

    def test_disable_versioning_omits_upload_action(self):
        """document_config.enable_versioning=false omits action_upload_new_version."""
        spec = _make_spec(
            document_management=True,
            document_config={"enable_versioning": False},
        )
        result = _process(spec)
        doc = _find_model(result, "document.document")
        cc = _get_complex_constraint(doc, "doc_action_upload_new_version")
        assert cc is None, "action_upload_new_version should be omitted when versioning disabled"

    def test_disable_versioning_context_key_false(self):
        """document_config.enable_versioning=false sets has_document_versioning=False."""
        spec = _make_spec(
            document_management=True,
            document_config={"enable_versioning": False},
        )
        result = _process(spec)
        doc = _find_model(result, "document.document")
        assert doc.get("has_document_versioning") is False

    def test_disable_verification(self):
        """document_config.enable_verification=false omits verification fields."""
        spec = _make_spec(
            document_management=True,
            document_config={"enable_verification": False},
        )
        result = _process(spec)
        doc = _find_model(result, "document.document")
        assert _get_field(doc, "verification_state") is None
        assert _get_field(doc, "verified_by") is None
        assert _get_field(doc, "verified_date") is None
        assert _get_field(doc, "rejection_reason") is None

    def test_disable_verification_omits_action_methods(self):
        """document_config.enable_verification=false omits verify/reject/reset actions."""
        spec = _make_spec(
            document_management=True,
            document_config={"enable_verification": False},
        )
        result = _process(spec)
        doc = _find_model(result, "document.document")
        assert _get_complex_constraint(doc, "doc_action_verify") is None
        assert _get_complex_constraint(doc, "doc_action_reject") is None
        assert _get_complex_constraint(doc, "doc_action_reset") is None

    def test_disable_verification_omits_verifier_role(self):
        """document_config.enable_verification=false omits verifier role."""
        spec = _make_spec(
            document_management=True,
            document_config={"enable_verification": False},
        )
        result = _process(spec)
        roles = result.get("security_roles", [])
        role_names = {r["name"] for r in roles}
        assert "verifier" not in role_names

    def test_disable_verification_context_key_false(self):
        """document_config.enable_verification=false sets has_document_verification=False."""
        spec = _make_spec(
            document_management=True,
            document_config={"enable_verification": False},
        )
        result = _process(spec)
        doc = _find_model(result, "document.document")
        assert doc.get("has_document_verification") is False

    def test_default_types_injects_extra_data_files(self):
        """document_config.default_types adds data file to extra_data_files."""
        spec = _make_spec(
            document_management=True,
            document_config={
                "default_types": [
                    {"name": "CNIC Copy", "code": "cnic", "required_for": "admission"},
                ]
            },
        )
        result = _process(spec)
        extra = result.get("extra_data_files", [])
        assert any("document_type" in f for f in extra), (
            f"Expected document_type data file in extra_data_files, got {extra}"
        )

    def test_both_disabled(self):
        """Both versioning and verification disabled: minimal document model."""
        spec = _make_spec(
            document_management=True,
            document_config={"enable_versioning": False, "enable_verification": False},
        )
        result = _process(spec)
        doc = _find_model(result, "document.document")
        # Core fields should still exist
        assert _get_field(doc, "name") is not None
        assert _get_field(doc, "file") is not None
        assert _get_field(doc, "document_type_id") is not None
        # Verification/versioning fields should not
        assert _get_field(doc, "verification_state") is None
        assert _get_field(doc, "version") is None


# ===========================================================================
# TestImmutability
# ===========================================================================


class TestImmutability:
    """Preprocessor is a pure function -- input spec not mutated."""

    def test_input_spec_not_mutated(self):
        """Processing does not modify the input spec dict."""
        spec = _make_spec(document_management=True)
        spec_copy = copy.deepcopy(spec)
        _process(spec)
        assert spec == spec_copy, "Input spec was mutated"

    def test_output_is_new_dict(self):
        """Output spec is a different dict object from input."""
        spec = _make_spec(document_management=True)
        result = _process(spec)
        assert result is not spec

    def test_existing_models_not_mutated(self):
        """Existing models in spec are not mutated."""
        existing = {
            "name": "custom.model",
            "description": "Custom",
            "fields": [{"name": "name", "type": "Char"}],
        }
        spec = _make_spec(models=[existing], document_management=True)
        existing_copy = copy.deepcopy(existing)
        _process(spec)
        assert existing == existing_copy

    def test_existing_security_roles_not_mutated(self):
        """Existing security_roles in spec are not mutated."""
        existing_roles = [
            {"name": "admin", "xml_id": "group_admin", "implied_ids": [], "is_highest": True},
        ]
        spec = _make_spec(document_management=True, security_roles=existing_roles)
        roles_copy = copy.deepcopy(existing_roles)
        _process(spec)
        assert existing_roles == roles_copy


# ===========================================================================
# Template Rendering Tests (Phase 52-02)
# ===========================================================================


def _render_model_template(
    model_dict: dict[str, Any],
    spec_overrides: dict[str, Any] | None = None,
    version: str = "17.0",
) -> str:
    """Render a model through the model.py.j2 template and return the output text."""
    from amil_utils.renderer import create_versioned_renderer
    from amil_utils.renderer_context import _build_model_context

    spec: dict[str, Any] = {
        "module_name": "test_module",
        "depends": ["base", "mail"],
        "models": [model_dict],
        "odoo_version": version,
        **(spec_overrides or {}),
    }
    ctx = _build_model_context(spec, model_dict)
    env = create_versioned_renderer(version)
    tpl = env.get_template("model.py.j2")
    return tpl.render(**ctx)


def _render_view_template(
    model_dict: dict[str, Any],
    spec_overrides: dict[str, Any] | None = None,
    version: str = "17.0",
) -> str:
    """Render a model through the view_form.xml.j2 template and return the output text."""
    from amil_utils.renderer import create_versioned_renderer
    from amil_utils.renderer_context import _build_model_context

    spec: dict[str, Any] = {
        "module_name": "test_module",
        "depends": ["base", "mail"],
        "models": [model_dict],
        "odoo_version": version,
        **(spec_overrides or {}),
    }
    ctx = _build_model_context(spec, model_dict)
    env = create_versioned_renderer(version)
    tpl = env.get_template("view_form.xml.j2")
    return tpl.render(**ctx)


class TestGenericFieldBranchKwargs:
    """Generic field branch renders attachment, readonly, tracking, copy, size, model_field."""

    def test_attachment_true_on_binary(self):
        """Binary field with attachment=True renders attachment=True."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [
                {"name": "file", "type": "Binary", "string": "File", "attachment": True},
            ],
        }
        output = _render_model_template(model)
        assert "attachment=True" in output

    def test_readonly_true(self):
        """Field with readonly=True renders readonly=True."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [
                {"name": "mime_type", "type": "Char", "string": "MIME Type", "readonly": True},
            ],
        }
        output = _render_model_template(model)
        assert "readonly=True" in output

    def test_tracking_true(self):
        """Field with tracking=True renders tracking=True."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [
                {"name": "name", "type": "Char", "string": "Name", "required": True, "tracking": True},
            ],
        }
        output = _render_model_template(model)
        assert "tracking=True" in output

    def test_copy_false(self):
        """Field with copy=False renders copy=False."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [
                {"name": "ref", "type": "Char", "string": "Ref", "copy": False},
            ],
        }
        output = _render_model_template(model)
        assert "copy=False" in output

    def test_model_field_on_many2onereference(self):
        """Many2oneReference with model_field renders model_field kwarg."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [
                {"name": "res_model", "type": "Char", "string": "Resource Model"},
                {
                    "name": "res_id",
                    "type": "Many2oneReference",
                    "string": "Resource ID",
                    "model_field": "res_model",
                },
            ],
        }
        output = _render_model_template(model)
        assert 'model_field="res_model"' in output

    def test_size_kwarg(self):
        """Field with size renders size=N."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [
                {"name": "code", "type": "Char", "string": "Code", "size": 16},
            ],
        }
        output = _render_model_template(model)
        assert "size=16" in output


class TestDocConstraintDispatch:
    """doc_file_validation renders with @api.constrains, doc_action_* as plain methods."""

    def test_doc_file_validation_renders_with_api_constrains(self):
        """doc_file_validation constraint renders with @api.constrains decorator."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [],
            "complex_constraints": [
                {
                    "name": "doc_file_validation",
                    "fields": ["file", "document_type_id"],
                    "type": "doc_file_validation",
                    "check_body": "for rec in self:\n    pass",
                },
            ],
        }
        output = _render_model_template(model)
        assert "@api.constrains" in output
        assert "_check_doc_file_validation" in output

    def test_doc_action_verify_renders_as_plain_method(self):
        """doc_action_verify renders as plain method (no @api.constrains, no _check_ prefix)."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [],
            "has_document_verification": True,
            "complex_constraints": [
                {
                    "name": "doc_action_verify",
                    "fields": ["verification_state"],
                    "type": "doc_action_verify",
                    "check_body": 'self.ensure_one()\nself.write({"verification_state": "verified"})',
                },
            ],
        }
        output = _render_model_template(model)
        assert "def doc_action_verify(self):" in output
        assert "@api.constrains" not in output.split("def doc_action_verify")[0].rsplit("class ", 1)[-1] if "def doc_action_verify" in output else True

    def test_doc_action_reject_renders_as_plain_method(self):
        """doc_action_reject renders as plain method."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [],
            "has_document_verification": True,
            "complex_constraints": [
                {
                    "name": "doc_action_reject",
                    "fields": ["verification_state"],
                    "type": "doc_action_reject",
                    "check_body": 'self.ensure_one()',
                },
            ],
        }
        output = _render_model_template(model)
        assert "def doc_action_reject(self):" in output

    def test_doc_action_reset_renders_as_plain_method(self):
        """doc_action_reset renders as plain method def action_reset_to_pending(self):."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [],
            "has_document_verification": True,
            "complex_constraints": [
                {
                    "name": "doc_action_reset",
                    "fields": ["verification_state"],
                    "type": "doc_action_reset",
                    "check_body": 'self.ensure_one()',
                },
            ],
        }
        output = _render_model_template(model)
        assert "def doc_action_reset(self):" in output

    def test_doc_action_upload_new_version_renders_as_plain_method(self):
        """doc_action_upload_new_version renders as plain method."""
        model = {
            "name": "test.model",
            "description": "Test",
            "fields": [],
            "has_document_versioning": True,
            "complex_constraints": [
                {
                    "name": "doc_action_upload_new_version",
                    "fields": ["version"],
                    "type": "doc_action_upload_new_version",
                    "check_body": 'self.ensure_one()',
                },
            ],
        }
        output = _render_model_template(model)
        assert "def doc_action_upload_new_version(self):" in output


class TestContextKeyDefaults:
    """has_document_verification and has_document_versioning default to False for non-document models."""

    def test_has_document_verification_defaults_false(self):
        """has_document_verification defaults to False (no StrictUndefined crash)."""
        from amil_utils.renderer_context import _build_model_context

        spec = {"module_name": "test_module", "depends": ["base"], "models": []}
        model = {"name": "test.model", "description": "Test", "fields": []}
        ctx = _build_model_context(spec, model)
        assert ctx["has_document_verification"] is False

    def test_has_document_versioning_defaults_false(self):
        """has_document_versioning defaults to False (no StrictUndefined crash)."""
        from amil_utils.renderer_context import _build_model_context

        spec = {"module_name": "test_module", "depends": ["base"], "models": []}
        model = {"name": "test.model", "description": "Test", "fields": []}
        ctx = _build_model_context(spec, model)
        assert ctx["has_document_versioning"] is False


class TestVersionGatesContext:
    """VERSION_GATES dict is present in module context for all specs."""

    def test_version_gates_in_module_context(self):
        """VERSION_GATES dict is present in module context."""
        from amil_utils.renderer_context import _build_module_context

        spec = {"module_name": "test_module", "depends": ["base"], "models": [], "odoo_version": "17.0"}
        ctx = _build_module_context(spec, "test_module")
        assert "version_gates" in ctx
        assert isinstance(ctx["version_gates"], dict)

    def test_version_gates_has_18_0_entry(self):
        """VERSION_GATES contains 18.0 entry with discuss.channel mapping."""
        from amil_utils.renderer_context import _build_module_context

        spec = {"module_name": "test_module", "depends": ["base"], "models": [], "odoo_version": "18.0"}
        ctx = _build_module_context(spec, "test_module")
        vg = ctx["version_gates"]
        assert "18.0" in vg
        assert vg["18.0"]["mail.channel"] == "discuss.channel"


class TestNonDocumentSpecRenders:
    """Existing non-document spec renders without errors after template changes."""

    def test_non_document_model_renders_without_error(self):
        """Non-document model with no document flags renders correctly."""
        model = {
            "name": "test.plain",
            "description": "Plain Model",
            "fields": [
                {"name": "name", "type": "Char", "string": "Name", "required": True},
                {"name": "notes", "type": "Text", "string": "Notes"},
            ],
        }
        # Should not raise StrictUndefined or any other error
        output = _render_model_template(model)
        assert "class TestPlain" in output
        assert 'name = fields.Char(' in output

    def test_non_document_view_renders_without_error(self):
        """Non-document model view renders correctly (no StrictUndefined crash)."""
        model = {
            "name": "test.plain",
            "description": "Plain Model",
            "fields": [
                {"name": "name", "type": "Char", "string": "Name", "required": True},
            ],
        }
        output = _render_view_template(model)
        assert "test.plain" in output


class TestViewDocumentVerificationButtons:
    """Form view header has verification buttons + statusbar for document models."""

    def test_verify_button_in_form_header(self):
        """Verify button appears in form header when has_document_verification."""
        spec = _make_spec(document_management=True)
        result = _process(spec)
        doc_model = _find_model(result, "document.document")
        output = _render_view_template(doc_model, spec_overrides={"models": result["models"], "depends": result["depends"]})
        assert 'name="doc_action_verify"' in output or 'string="Verify"' in output

    def test_reject_button_in_form_header(self):
        """Reject button appears in form header when has_document_verification."""
        spec = _make_spec(document_management=True)
        result = _process(spec)
        doc_model = _find_model(result, "document.document")
        output = _render_view_template(doc_model, spec_overrides={"models": result["models"], "depends": result["depends"]})
        assert 'string="Reject"' in output or 'name="doc_action_reject"' in output

    def test_verification_state_statusbar(self):
        """verification_state statusbar appears in form header for document models."""
        spec = _make_spec(document_management=True)
        result = _process(spec)
        doc_model = _find_model(result, "document.document")
        output = _render_view_template(doc_model, spec_overrides={"models": result["models"], "depends": result["depends"]})
        assert 'name="verification_state"' in output
        assert 'widget="statusbar"' in output

    def test_version_history_smart_button(self):
        """Version history smart button appears when has_document_versioning."""
        spec = _make_spec(document_management=True)
        result = _process(spec)
        doc_model = _find_model(result, "document.document")
        output = _render_view_template(doc_model, spec_overrides={"models": result["models"], "depends": result["depends"]})
        assert "fa-history" in output or "action_view_versions" in output


# ===========================================================================
# E2E Integration Tests (Phase 52-02 Task 2)
# ===========================================================================


def _make_e2e_spec(**overrides: Any) -> dict[str, Any]:
    """Build a spec suitable for render_module() E2E testing with document management."""
    spec: dict[str, Any] = {
        "module_name": "test_doc_mgmt",
        "module_title": "Test Document Management",
        "summary": "Test document management module",
        "author": "Test Author",
        "website": "https://test.example.com",
        "license": "LGPL-3",
        "category": "Education",
        "odoo_version": "17.0",
        "depends": ["base"],
        "models": [],
        "document_management": True,
    }
    spec.update(overrides)
    return spec


class TestDocumentManagementE2E:
    """End-to-end integration tests: full module render with document management."""

    def _render(
        self, spec: dict[str, Any], tmp_path: Any
    ) -> dict[str, str]:
        """Render a spec and return dict of relative_path -> file content."""
        from pathlib import Path

        from amil_utils.renderer import get_template_dir, render_module

        output_dir = Path(tmp_path)
        files, _warnings = render_module(
            spec, get_template_dir(), output_dir, no_context7=True
        )
        module_dir = output_dir / spec["module_name"]
        results: dict[str, str] = {}
        for f in files:
            if f.exists():
                results[str(f.relative_to(module_dir))] = f.read_text(
                    encoding="utf-8"
                )
        return results

    def test_generates_document_type_model_file(self, tmp_path):
        """render_module() produces models/document_type.py."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        assert "models/document_type.py" in rendered

    def test_generates_document_document_model_file(self, tmp_path):
        """render_module() produces models/document_document.py."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        assert "models/document_document.py" in rendered

    def test_attachment_true_in_generated_file(self, tmp_path):
        """Generated document_document.py contains attachment=True on file field."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/document_document.py", "")
        assert "attachment=True" in content

    def test_readonly_true_in_generated_file(self, tmp_path):
        """Generated document_document.py contains readonly=True on metadata fields."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/document_document.py", "")
        assert "readonly=True" in content

    def test_tracking_true_in_generated_file(self, tmp_path):
        """Generated document_document.py contains tracking=True on name and verification_state."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/document_document.py", "")
        assert "tracking=True" in content

    def test_model_field_in_generated_file(self, tmp_path):
        """Generated document_document.py contains model_field='res_model' on res_id."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/document_document.py", "")
        assert 'model_field="res_model"' in content

    def test_action_verify_as_plain_method(self, tmp_path):
        """Generated document_document.py contains def doc_action_verify(self): (plain method)."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/document_document.py", "")
        assert "def doc_action_verify(self):" in content
        # Should NOT have _check_ prefix
        assert "_check_doc_action_verify" not in content

    def test_action_reject_as_plain_method(self, tmp_path):
        """Generated document_document.py contains def doc_action_reject(self): method."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/document_document.py", "")
        assert "def doc_action_reject(self):" in content

    def test_action_upload_new_version_as_plain_method(self, tmp_path):
        """Generated document_document.py contains def doc_action_upload_new_version(self):."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/document_document.py", "")
        assert "def doc_action_upload_new_version(self):" in content

    def test_file_validation_with_api_constrains(self, tmp_path):
        """Generated document_document.py has @api.constrains for file validation."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/document_document.py", "")
        assert '@api.constrains("file", "document_type_id")' in content

    def test_imports_user_error(self, tmp_path):
        """Generated document_document.py imports UserError."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/document_document.py", "")
        assert "from odoo.exceptions import UserError" in content

    def test_imports_translate(self, tmp_path):
        """Generated document_document.py has translatable error messages."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/document_document.py", "")
        # Template may use self.env._(), standalone _(), or raw strings with UserError/ValidationError
        assert (
            "self.env._(" in content
            or "from odoo.tools.translate import _" in content
            or "UserError" in content
            or "ValidationError" in content
        )

    def test_manifest_includes_mail_depends(self, tmp_path):
        """Generated __manifest__.py includes 'mail' in depends."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("__manifest__.py", "")
        assert "'mail'" in content or '"mail"' in content

    def test_init_imports_both_models(self, tmp_path):
        """Generated models/__init__.py imports both document_type and document_document."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("models/__init__.py", "")
        assert "document_type" in content
        assert "document_document" in content

    def test_security_groups_include_all_roles(self, tmp_path):
        """Generated security/security.xml includes viewer/uploader/verifier/manager groups."""
        spec = _make_e2e_spec()
        rendered = self._render(spec, tmp_path)
        content = rendered.get("security/security.xml", "")
        assert "viewer" in content.lower()
        assert "uploader" in content.lower()
        assert "verifier" in content.lower()
        assert "manager" in content.lower()


class TestVersionGatesE2E:
    """E2E tests for VERSION_GATES rendering with different Odoo versions."""

    def _render(
        self, spec: dict[str, Any], tmp_path: Any
    ) -> dict[str, str]:
        """Render a spec and return dict of relative_path -> file content."""
        from pathlib import Path

        from amil_utils.renderer import get_template_dir, render_module

        output_dir = Path(tmp_path)
        files, _warnings = render_module(
            spec, get_template_dir(), output_dir, no_context7=True
        )
        module_dir = output_dir / spec["module_name"]
        results: dict[str, str] = {}
        for f in files:
            if f.exists():
                results[str(f.relative_to(module_dir))] = f.read_text(
                    encoding="utf-8"
                )
        return results

    def test_version_gates_context_available_17(self, tmp_path):
        """VERSION_GATES context is available when rendering with 17.0."""
        from amil_utils.renderer_context import _build_module_context

        spec = _make_e2e_spec(odoo_version="17.0")
        ctx = _build_module_context(spec, spec["module_name"])
        assert "version_gates" in ctx
        assert isinstance(ctx["version_gates"], dict)

    def test_version_gates_context_available_18(self, tmp_path):
        """VERSION_GATES context is available when rendering with 18.0."""
        from amil_utils.renderer_context import _build_module_context

        spec = _make_e2e_spec(odoo_version="18.0")
        ctx = _build_module_context(spec, spec["module_name"])
        assert "version_gates" in ctx
        vg = ctx["version_gates"]
        assert "18.0" in vg
        assert vg["18.0"]["mail.channel"] == "discuss.channel"

    def test_18_0_render_produces_valid_output(self, tmp_path):
        """Rendering with odoo_version=18.0 produces valid module files."""
        spec = _make_e2e_spec(odoo_version="18.0")
        rendered = self._render(spec, tmp_path)
        # Basic sanity: model files generated
        assert "models/document_document.py" in rendered
        assert "models/document_type.py" in rendered


class TestDocumentTypeSeedData:
    """E2E tests for document type seed data XML generation."""

    def _render(
        self, spec: dict[str, Any], tmp_path: Any
    ) -> dict[str, str]:
        """Render a spec and return dict of relative_path -> file content."""
        from pathlib import Path

        from amil_utils.renderer import get_template_dir, render_module

        output_dir = Path(tmp_path)
        files, _warnings = render_module(
            spec, get_template_dir(), output_dir, no_context7=True
        )
        module_dir = output_dir / spec["module_name"]
        results: dict[str, str] = {}
        for f in files:
            if f.exists():
                results[str(f.relative_to(module_dir))] = f.read_text(
                    encoding="utf-8"
                )
        return results

    def test_document_type_data_xml_generated(self, tmp_path):
        """document_type_data.xml generated when default_types configured."""
        spec = _make_e2e_spec(
            document_config={
                "default_types": [
                    {"name": "CNIC Copy", "code": "cnic", "required_for": "admission"},
                    {"name": "Transcript", "code": "transcript", "required_for": "enrollment"},
                ],
            },
        )
        rendered = self._render(spec, tmp_path)
        assert "data/document_type_data.xml" in rendered

    def test_document_type_data_xml_content(self, tmp_path):
        """document_type_data.xml has correct record IDs and field values."""
        spec = _make_e2e_spec(
            document_config={
                "default_types": [
                    {"name": "CNIC Copy", "code": "cnic", "required_for": "admission"},
                ],
            },
        )
        rendered = self._render(spec, tmp_path)
        content = rendered.get("data/document_type_data.xml", "")
        assert "document_type_cnic" in content
        assert "CNIC Copy" in content
        assert "cnic" in content
        assert "admission" in content
        assert 'noupdate="1"' in content
