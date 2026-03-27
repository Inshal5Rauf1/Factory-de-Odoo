"""Unit tests for EnvironmentVerifier with mocked OdooClient.

Tests are fully unit-level (no Docker required). OdooClient is replaced by
MagicMock passed directly to EnvironmentVerifier constructor (constructor
injection -- same pattern as test_mcp_server.py).

Test classes:
  TestVerifierNoClient          -- client=None returns [] for all methods
  TestModelInheritCheck         -- _inherit verification
  TestRelationalComodelCheck    -- comodel_name verification
  TestFieldOverrideCheck        -- field override type-check (MCP-03 criterion #3)
  TestViewFieldCheck            -- view field name verification (MCP-04)
  TestViewInheritTarget         -- inherited view target verification (MCP-04)
  TestIntegrationWithRenderModule -- render_module() tuple return + verifier wiring
  TestBuildVerifierFromEnv      -- factory function env var handling
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from amil_utils.verifier import EnvironmentVerifier, VerificationWarning, build_verifier_from_env


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client():
    """Bare MagicMock substituting for OdooClient."""
    client = MagicMock()
    client.search_read.return_value = []
    return client


@pytest.fixture
def verifier(mock_client):
    """EnvironmentVerifier with a mocked OdooClient."""
    return EnvironmentVerifier(client=mock_client)


# ---------------------------------------------------------------------------
# TestVerifierNoClient
# ---------------------------------------------------------------------------


class TestVerifierNoClient:
    """When client=None, all methods return Result.ok([]) (graceful no-op)."""

    def test_no_client_verify_model_returns_empty(self):
        v = EnvironmentVerifier(client=None)
        result = v.verify_model_spec({"name": "my.model", "inherit": "hr.employee"})
        assert result.success
        assert result.data == []

    def test_no_client_verify_view_returns_empty(self):
        v = EnvironmentVerifier(client=None)
        result = v.verify_view_spec("my.model", ["name", "employee_id"])
        assert result.success
        assert result.data == []

    def test_default_constructor_is_no_op(self):
        """EnvironmentVerifier() with no args behaves like client=None."""
        v = EnvironmentVerifier()
        result_m = v.verify_model_spec({"name": "test.model"})
        result_v = v.verify_view_spec("test.model", ["name"])
        assert result_m.success and result_m.data == []
        assert result_v.success and result_v.data == []


# ---------------------------------------------------------------------------
# TestModelInheritCheck
# ---------------------------------------------------------------------------


class TestModelInheritCheck:
    """Tests for _inherit base model verification."""

    def test_inherit_exists_returns_no_warnings(self, verifier, mock_client):
        mock_client.search_read.return_value = [{"model": "hr.employee"}]
        result = verifier.verify_model_spec({"name": "my.model", "inherit": "hr.employee"})
        assert result.success
        assert result.data == []

    def test_inherit_missing_returns_warning(self, verifier, mock_client):
        mock_client.search_read.return_value = []
        result = verifier.verify_model_spec({"name": "my.model", "inherit": "missing.model"})
        assert result.success
        assert len(result.data) == 1
        assert result.data[0].check_type == "model_inherit"
        assert "missing.model" in result.data[0].message

    def test_inherit_list_missing_returns_warning(self, verifier, mock_client):
        """_inherit as list: missing model in the list emits a warning."""
        mock_client.search_read.return_value = []
        result = verifier.verify_model_spec({
            "name": "my.model",
            "inherit": ["missing.model"],
        })
        assert result.success
        assert len(result.data) == 1
        assert result.data[0].check_type == "model_inherit"

    def test_mail_thread_always_skipped(self, verifier, mock_client):
        """mail.thread must be skipped without querying OdooClient."""
        result = verifier.verify_model_spec({
            "name": "my.model",
            "inherit": "mail.thread",
        })
        assert result.success
        assert result.data == []
        mock_client.search_read.assert_not_called()

    def test_mail_activity_mixin_always_skipped(self, verifier, mock_client):
        """mail.activity.mixin must be skipped without querying OdooClient."""
        result = verifier.verify_model_spec({
            "name": "my.model",
            "inherit": "mail.activity.mixin",
        })
        assert result.success
        assert result.data == []
        mock_client.search_read.assert_not_called()

    def test_no_inherit_returns_empty(self, verifier, mock_client):
        result = verifier.verify_model_spec({"name": "my.model", "fields": []})
        assert result.success
        assert result.data == []


# ---------------------------------------------------------------------------
# TestRelationalComodelCheck
# ---------------------------------------------------------------------------


class TestRelationalComodelCheck:
    """Tests for relational field comodel_name verification."""

    def test_many2one_comodel_exists(self, verifier, mock_client):
        mock_client.search_read.return_value = [{"model": "res.partner"}]
        model = {
            "name": "sale.order",
            "fields": [{"name": "partner_id", "type": "Many2one", "comodel_name": "res.partner"}],
        }
        result = verifier.verify_model_spec(model)
        assert result.success
        assert result.data == []

    def test_many2one_comodel_missing(self, verifier, mock_client):
        mock_client.search_read.return_value = []
        model = {
            "name": "my.model",
            "fields": [{"name": "ref_id", "type": "Many2one", "comodel_name": "missing.model"}],
        }
        result = verifier.verify_model_spec(model)
        assert result.success
        assert len(result.data) == 1
        assert result.data[0].check_type == "field_comodel"

    def test_one2many_comodel_missing(self, verifier, mock_client):
        mock_client.search_read.return_value = []
        model = {
            "name": "my.model",
            "fields": [{"name": "line_ids", "type": "One2many", "comodel_name": "missing.line"}],
        }
        result = verifier.verify_model_spec(model)
        assert result.success
        assert len(result.data) == 1
        assert result.data[0].check_type == "field_comodel"

    def test_many2many_comodel_missing(self, verifier, mock_client):
        mock_client.search_read.return_value = []
        model = {
            "name": "my.model",
            "fields": [{"name": "tag_ids", "type": "Many2many", "comodel_name": "missing.tag"}],
        }
        result = verifier.verify_model_spec(model)
        assert result.success
        assert len(result.data) == 1
        assert result.data[0].check_type == "field_comodel"

    def test_duplicate_comodel_queried_once(self, verifier, mock_client):
        """Two fields with same comodel: OdooClient is queried only once."""
        mock_client.search_read.return_value = [{"model": "res.partner"}]
        model = {
            "name": "my.model",
            "fields": [
                {"name": "partner_id", "type": "Many2one", "comodel_name": "res.partner"},
                {"name": "partner_id2", "type": "Many2one", "comodel_name": "res.partner"},
            ],
        }
        result = verifier.verify_model_spec(model)
        assert result.success
        # search_read called only once for ir.model (de-duplicated)
        assert mock_client.search_read.call_count == 1

    def test_non_relational_fields_not_checked(self, verifier, mock_client):
        """Char, Integer, Boolean etc. do not trigger comodel checks."""
        model = {
            "name": "my.model",
            "fields": [
                {"name": "name", "type": "Char"},
                {"name": "qty", "type": "Integer"},
            ],
        }
        result = verifier.verify_model_spec(model)
        assert result.success
        mock_client.search_read.assert_not_called()


# ---------------------------------------------------------------------------
# TestFieldOverrideCheck  (MCP-03 criterion #3)
# ---------------------------------------------------------------------------


class TestFieldOverrideCheck:
    """Tests for field override type mismatch verification.

    MCP-03 criterion #3: If a field spec has `override: True`, verify the field
    exists in Odoo and that its ttype matches the spec type.
    """

    def test_field_override_matching_ttype_passes(self, verifier, mock_client):
        """Override with matching ttype returns no warnings."""
        # Odoo reports job_title as 'char'
        mock_client.search_read.return_value = [{"name": "job_title", "ttype": "char"}]
        model = {
            "name": "hr.employee",
            "fields": [
                {"name": "job_title", "type": "Char", "override": True},
            ],
        }
        result = verifier.verify_model_spec(model)
        assert result.success
        assert result.data == []

    def test_field_override_mismatched_ttype_warns(self, verifier, mock_client):
        """Override with type mismatch: Odoo has 'many2one', spec has 'Char'."""
        mock_client.search_read.return_value = [{"name": "job_title", "ttype": "many2one"}]
        model = {
            "name": "hr.employee",
            "fields": [
                {"name": "job_title", "type": "Char", "override": True},
            ],
        }
        result = verifier.verify_model_spec(model)
        assert result.success
        assert len(result.data) == 1
        assert result.data[0].check_type == "field_override"
        assert "job_title" in result.data[0].subject

    def test_field_override_nonexistent_field_warns(self, verifier, mock_client):
        """Override of a field that does not exist in Odoo emits a warning."""
        mock_client.search_read.return_value = []  # field not found
        model = {
            "name": "hr.employee",
            "fields": [
                {"name": "phantom_field", "type": "Char", "override": True},
            ],
        }
        result = verifier.verify_model_spec(model)
        assert result.success
        assert len(result.data) == 1
        assert result.data[0].check_type == "field_override"
        assert "phantom_field" in result.data[0].subject


# ---------------------------------------------------------------------------
# TestViewFieldCheck
# ---------------------------------------------------------------------------


class TestViewFieldCheck:
    """Tests for view field name verification against live Odoo schema."""

    def test_all_fields_exist(self, verifier, mock_client):
        mock_client.search_read.return_value = [{"name": "name"}, {"name": "partner_id"}]
        result = verifier.verify_view_spec("sale.order", ["name", "partner_id"])
        assert result.success
        assert result.data == []

    def test_missing_field_returns_warning(self, verifier, mock_client):
        mock_client.search_read.return_value = [{"name": "name"}]
        result = verifier.verify_view_spec("sale.order", ["name", "nonexistent_field"])
        assert result.success
        assert len(result.data) == 1
        assert result.data[0].check_type == "view_field"
        assert "nonexistent_field" in result.data[0].message

    def test_model_not_in_odoo_skips_field_check(self, verifier, mock_client):
        """New model not yet in Odoo: ir.model.fields returns [] -- skip silently."""
        mock_client.search_read.return_value = []
        result = verifier.verify_view_spec("new.model", ["name", "description"])
        assert result.success
        assert result.data == []

    def test_odoo_error_degrades_gracefully(self, verifier, mock_client):
        """Exception from OdooClient returns Result.fail (infrastructure error)."""
        mock_client.search_read.side_effect = ConnectionRefusedError("Odoo down")
        result = verifier.verify_view_spec("sale.order", ["name"])
        assert not result.success
        assert len(result.errors) > 0

    def test_empty_field_list_returns_empty(self, verifier, mock_client):
        """No fields to check: return Result.ok([]) without querying Odoo."""
        result = verifier.verify_view_spec("sale.order", [])
        assert result.success
        assert result.data == []
        mock_client.search_read.assert_not_called()


# ---------------------------------------------------------------------------
# TestViewInheritTarget
# ---------------------------------------------------------------------------


class TestViewInheritTarget:
    """Tests for inherited view target existence verification."""

    def test_existing_target_returns_no_warnings(self, verifier, mock_client):
        # First call: ir.model.fields for view field check -> "name" exists
        # Second call: ir.ui.view for inherited view target check -> view exists
        mock_client.search_read.side_effect = [
            [{"name": "name"}],           # ir.model.fields: "name" field exists
            [{"name": "some.view"}],       # ir.ui.view: target model has views
        ]
        result = verifier.verify_view_spec(
            "hr.employee", ["name"], inherited_view_target="hr.employee"
        )
        assert result.success
        assert result.data == []

    def test_missing_target_returns_warning(self, verifier, mock_client):
        mock_client.search_read.return_value = []
        result = verifier.verify_view_spec(
            "my.model", ["name"], inherited_view_target="missing.target"
        )
        assert result.success
        assert len(result.data) == 1
        assert result.data[0].check_type == "view_inherit_target"
        assert "missing.target" in result.data[0].subject

    def test_no_inherited_target_no_extra_query(self, verifier, mock_client):
        """Without inherited_view_target, _check_view_target is not called."""
        mock_client.search_read.return_value = [{"name": "name"}]
        result = verifier.verify_view_spec("sale.order", ["name"])
        assert result.success
        # Only one call: for view fields (ir.model.fields)
        assert mock_client.search_read.call_count == 1


# ---------------------------------------------------------------------------
# TestIntegrationWithRenderModule
# ---------------------------------------------------------------------------


class TestIntegrationWithRenderModule:
    """Integration tests: render_module() tuple return and verifier wiring."""

    def test_render_module_with_verifier_returns_warnings(self, tmp_path, mock_client):
        from amil_utils.renderer import get_template_dir, render_module

        mock_client.search_read.return_value = []  # all checks fail -> warnings

        spec = {
            "module_name": "test_verify",
            "models": [{
                "name": "my.model",
                "inherit": "hr.employee",
                "fields": [{"name": "name", "type": "Char", "string": "Name"}],
            }],
        }
        verifier = EnvironmentVerifier(client=mock_client)
        files, warnings = render_module(spec, get_template_dir(), tmp_path, verifier=verifier)
        assert len(files) > 0  # generation proceeded
        assert any(w.check_type == "model_inherit" for w in warnings)

    def test_render_module_without_verifier_backward_compat(self, tmp_path):
        """render_module() without verifier still returns (files, []) tuple."""
        from amil_utils.renderer import get_template_dir, render_module

        spec = {
            "module_name": "test_noverify",
            "models": [{"name": "simple.model", "fields": []}],
        }
        files, warnings = render_module(spec, get_template_dir(), tmp_path)
        assert len(files) > 0
        assert warnings == []

    def test_render_module_returns_tuple_type(self, tmp_path):
        """render_module() must return a 2-tuple in all code paths."""
        from amil_utils.renderer import get_template_dir, render_module

        spec = {"module_name": "test_tuple", "models": []}
        result = render_module(spec, get_template_dir(), tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 2
        files, warnings = result
        assert isinstance(files, list)
        assert isinstance(warnings, list)


# ---------------------------------------------------------------------------
# TestBuildVerifierFromEnv
# ---------------------------------------------------------------------------


class TestBuildVerifierFromEnv:
    """Tests for build_verifier_from_env() factory function."""

    def test_no_odoo_url_returns_no_op_verifier(self):
        """When ODOO_URL is not set, returns EnvironmentVerifier with client=None."""
        env = {k: v for k, v in os.environ.items() if k != "ODOO_URL"}
        with patch.dict(os.environ, env, clear=True):
            v = build_verifier_from_env()
        assert isinstance(v, EnvironmentVerifier)
        result = v.verify_model_spec({"name": "x", "inherit": "y"})
        assert result.success and result.data == []

    def test_odoo_url_set_but_client_raises_returns_no_op(self):
        """When ODOO_URL is set but OdooClient raises, return no-op verifier."""
        env = {
            "ODOO_URL": "http://localhost:9999",
            "ODOO_DB": "test_db",
            "ODOO_USER": "admin",
            "ODOO_API_KEY": "admin",
        }
        # OdooClient is imported lazily inside build_verifier_from_env.
        # Patch it at the odoo_client module level.
        with patch.dict(os.environ, env):
            with patch(
                "amil_utils.mcp.odoo_client.OdooClient",
                side_effect=Exception("Connection refused"),
            ):
                v = build_verifier_from_env()
        assert isinstance(v, EnvironmentVerifier)
        result = v.verify_model_spec({"name": "x"})
        assert result.success and result.data == []
