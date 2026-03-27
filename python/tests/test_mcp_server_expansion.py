"""Tests for Gap 7 MCP server expansion tools.

Tests the 3 new tools: get_view_inheritance_chain, get_model_relations,
find_field_conflicts. Follows existing test_mcp_server.py patterns —
mocks _get_client() to avoid real XML-RPC connections.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from amil_utils.mcp.server import (
    find_field_conflicts,
    get_model_relations,
    get_view_inheritance_chain,
)


@pytest.fixture()
def mock_client():
    """Return a MagicMock OdooClient with patched _get_client."""
    client = MagicMock()
    with patch("amil_utils.mcp.server._get_client", return_value=client):
        yield client


class TestGetViewInheritanceChain:
    def test_base_and_inherited(self, mock_client):
        mock_client.search_read.return_value = [
            {"name": "partner.form", "inherit_id": False, "priority": 16,
             "arch": "<form/>", "xml_id": "base.view_partner_form", "type": "form"},
            {"name": "crm.partner.form", "inherit_id": [42, "partner.form"],
             "priority": 20, "arch": "<xpath/>", "xml_id": "crm.view_partner_form", "type": "form"},
            {"name": "sale.partner.form", "inherit_id": [42, "partner.form"],
             "priority": 25, "arch": "<xpath/>", "xml_id": "sale.view_partner_form", "type": "form"},
        ]
        result = get_view_inheritance_chain("res.partner", "form")
        assert "BASE: partner.form" in result
        assert "INHERITS: crm.partner.form" in result
        assert "INHERITS: sale.partner.form" in result
        assert "Total views: 3" in result

    def test_no_views(self, mock_client):
        mock_client.search_read.return_value = []
        result = get_view_inheritance_chain("nonexistent.model", "form")
        assert "No form views found" in result


class TestGetModelRelations:
    def test_outgoing_and_incoming(self, mock_client):
        mock_client.search_read.side_effect = [
            [{"name": "partner_id", "ttype": "many2one",
              "relation": "res.partner", "field_description": "Partner"}],
            [{"name": "order_ids", "ttype": "one2many",
              "model": "sale.order", "field_description": "Orders"}],
        ]
        result = get_model_relations("sale.order.line")
        assert "partner_id (many2one)" in result
        assert "sale.order.order_ids (one2many)" in result
        assert "Outgoing (1 fields" in result
        assert "Incoming (1 fields" in result

    def test_no_relations(self, mock_client):
        mock_client.search_read.side_effect = [[], []]
        result = get_model_relations("simple.model")
        assert "(none)" in result


class TestFindFieldConflicts:
    def test_field_exists(self, mock_client):
        mock_client.search_read.return_value = [
            {"name": "x_score", "ttype": "float",
             "field_description": "Score", "modules": "custom_module"},
        ]
        result = find_field_conflicts("res.partner", "x_score")
        assert result.startswith("CONFLICT:")
        assert "x_score" in result
        assert "float" in result

    def test_field_clear(self, mock_client):
        mock_client.search_read.return_value = []
        result = find_field_conflicts("res.partner", "x_new_field")
        assert result.startswith("CLEAR:")
        assert "x_new_field" in result


class TestNewToolsErrorHandling:
    def test_all_new_tools_handle_connection_error(self):
        with patch("amil_utils.mcp.server._get_client",
                   side_effect=ConnectionRefusedError("Connection refused")):
            r1 = get_view_inheritance_chain("res.partner")
            r2 = get_model_relations("res.partner")
            r3 = find_field_conflicts("res.partner", "name")
            assert "ERROR:" in r1
            assert "ERROR:" in r2
            assert "ERROR:" in r3


class TestParameterValidation:
    """S5: Validate MCP tool parameters before XML-RPC calls."""

    def test_invalid_model_name_rejected(self):
        assert "ERROR:" in get_view_inheritance_chain("")
        assert "ERROR:" in get_view_inheritance_chain("UPPER.Case")
        assert "ERROR:" in get_view_inheritance_chain("has spaces")
        assert "ERROR:" in get_model_relations("")
        assert "ERROR:" in find_field_conflicts("", "name")

    def test_invalid_view_type_rejected(self):
        result = get_view_inheritance_chain("res.partner", "nonexistent")
        assert "ERROR:" in result
        assert "Invalid view_type" in result

    def test_invalid_field_name_rejected(self):
        assert "ERROR:" in find_field_conflicts("res.partner", "")
        assert "ERROR:" in find_field_conflicts("res.partner", "Has Spaces")
        assert "ERROR:" in find_field_conflicts("res.partner", "123bad")

    def test_valid_params_pass_validation(self, mock_client):
        mock_client.search_read.return_value = []
        # These should reach the XML-RPC layer (no validation error)
        r1 = get_view_inheritance_chain("res.partner", "form")
        assert "ERROR:" not in r1 or "Cannot connect" in r1
        mock_client.search_read.side_effect = [[], []]
        r2 = get_model_relations("sale.order.line")
        assert "ERROR:" not in r2 or "Cannot connect" in r2
