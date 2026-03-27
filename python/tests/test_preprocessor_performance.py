"""Tests for the performance preprocessor."""

from __future__ import annotations

from typing import Any

import pytest

from amil_utils.preprocessors.performance import (
    _process_performance,
    _validate_where_clause,
)


def _make_spec(
    models: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal spec dict."""
    return {"module_name": "test_mod", "models": models or [], **kwargs}


def _make_model(
    name: str = "test.model",
    fields: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal model dict."""
    return {"name": name, "fields": fields or [], **kwargs}


class TestProcessPerformance:
    """Tests for _process_performance."""

    def test_happy_path_index_enrichment(self):
        """Char, Many2one, Selection fields get index=True."""
        fields = [
            {"name": "title", "type": "Char"},
            {"name": "partner_id", "type": "Many2one"},
            {"name": "state", "type": "Selection"},
            {"name": "notes", "type": "Text"},
        ]
        model = _make_model(fields=fields)
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        assert result is not spec
        rf = result["models"][0]["fields"]
        field_map = {f["name"]: f for f in rf}
        assert field_map["title"].get("index") is True
        assert field_map["partner_id"].get("index") is True
        assert field_map["state"].get("index") is True
        # Text is not indexable
        assert "index" not in field_map["notes"]

    def test_company_id_gets_index(self):
        """company_id field gets index=True for record rule domain optimization."""
        fields = [
            {"name": "company_id", "type": "Many2one"},
            {"name": "description", "type": "Text"},
        ]
        model = _make_model(fields=fields)
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rf = result["models"][0]["fields"]
        company_field = next(f for f in rf if f["name"] == "company_id")
        assert company_field["index"] is True

    def test_order_fields_get_index(self):
        """Fields referenced in model order get index=True."""
        fields = [
            {"name": "priority", "type": "Integer"},
            {"name": "create_date", "type": "Datetime"},
        ]
        model = _make_model(fields=fields, order="priority desc, create_date")
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rf = result["models"][0]["fields"]
        field_map = {f["name"]: f for f in rf}
        assert field_map["priority"].get("index") is True
        assert field_map["create_date"].get("index") is True

    def test_model_order_validation(self):
        """model_order is set with validated order parts."""
        fields = [
            {"name": "priority", "type": "Integer"},
            {"name": "name", "type": "Char"},
        ]
        model = _make_model(fields=fields, order="priority desc, name asc")
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert rm["model_order"] == "priority desc, name asc"

    def test_order_invalid_field_excluded(self):
        """Order referencing non-existent field is excluded from model_order."""
        fields = [{"name": "name", "type": "Char"}]
        model = _make_model(fields=fields, order="name, nonexistent desc")
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert rm["model_order"] == "name"

    def test_computed_field_store_enrichment(self):
        """Computed fields visible in tree/search get store=True."""
        fields = [
            {"name": "total", "type": "Float", "compute": "_compute_total"},
            {"name": "notes", "type": "Text", "compute": "_compute_notes"},
        ]
        model = _make_model(fields=fields)
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rf = result["models"][0]["fields"]
        field_map = {f["name"]: f for f in rf}
        # total is Float (not One2many/Html/Text), so it appears in tree view fields
        assert field_map["total"].get("store") is True
        # Text is excluded from tree fields, but it's not in search fields either
        # (search fields require Char/Many2one/Selection type)

    def test_computed_field_already_stored_not_duplicated(self):
        """Computed fields with store=True already set are not modified."""
        fields = [
            {"name": "total", "type": "Float", "compute": "_compute_total", "store": True},
        ]
        model = _make_model(fields=fields)
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rf = result["models"][0]["fields"]
        assert rf[0]["store"] is True

    def test_unique_together_sql_constraints(self):
        """unique_together generates _sql_constraints."""
        fields = [
            {"name": "name", "type": "Char"},
            {"name": "company_id", "type": "Many2one"},
        ]
        model = _make_model(
            fields=fields,
            unique_together=[{"fields": ["name", "company_id"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert "sql_constraints" in rm
        constraints = rm["sql_constraints"]
        assert len(constraints) == 1
        c = constraints[0]
        assert c["name"] == "unique_name_company_id"
        assert c["definition"] == "UNIQUE(name, company_id)"

    def test_unique_together_custom_message(self):
        """unique_together respects custom message."""
        fields = [{"name": "code", "type": "Char"}]
        model = _make_model(
            fields=fields,
            unique_together=[{
                "fields": ["code"],
                "message": "Code must be unique!",
            }],
        )
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        c = result["models"][0]["sql_constraints"][0]
        assert c["message"] == "Code must be unique!"

    def test_unique_together_missing_field_skipped(self):
        """unique_together referencing non-existent field is skipped."""
        fields = [{"name": "name", "type": "Char"}]
        model = _make_model(
            fields=fields,
            unique_together=[{"fields": ["name", "nonexistent"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        # sql_constraints should be empty since the constraint was skipped
        assert rm.get("sql_constraints", []) == []

    def test_composite_index_hints(self):
        """index_hints generate composite_indexes."""
        fields = [
            {"name": "state", "type": "Selection"},
            {"name": "date", "type": "Date"},
        ]
        model = _make_model(
            fields=fields,
            index_hints=[{"fields": ["state", "date"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert "composite_indexes" in rm
        idx = rm["composite_indexes"][0]
        assert idx["name"] == "idx_state_date"
        assert idx["fields"] == ["state", "date"]

    def test_composite_index_custom_name(self):
        """index_hints with explicit name use that name."""
        fields = [
            {"name": "state", "type": "Selection"},
            {"name": "date", "type": "Date"},
        ]
        model = _make_model(
            fields=fields,
            index_hints=[{"fields": ["state", "date"], "name": "my_custom_idx"}],
        )
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        idx = result["models"][0]["composite_indexes"][0]
        assert idx["name"] == "my_custom_idx"

    def test_composite_index_missing_field_skipped(self):
        """index_hints referencing non-existent fields are skipped."""
        fields = [{"name": "state", "type": "Selection"}]
        model = _make_model(
            fields=fields,
            index_hints=[{"fields": ["state", "nonexistent"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert "composite_indexes" not in rm

    def test_composite_index_with_where_clause(self):
        """index_hints with safe where clause are accepted."""
        fields = [
            {"name": "state", "type": "Selection"},
            {"name": "active", "type": "Boolean"},
        ]
        model = _make_model(
            fields=fields,
            index_hints=[{
                "fields": ["state"],
                "where": "active = True",
            }],
        )
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        idx = result["models"][0]["composite_indexes"][0]
        assert idx["where"] == "active = True"

    def test_composite_index_unsafe_where_skipped(self):
        """index_hints with SQL injection in where clause are skipped."""
        fields = [{"name": "state", "type": "Selection"}]
        model = _make_model(
            fields=fields,
            index_hints=[{
                "fields": ["state"],
                "where": "1=1; DROP TABLE users",
            }],
        )
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert "composite_indexes" not in rm

    def test_transient_model_defaults(self):
        """TransientModel gets default transient_max_hours and transient_max_count."""
        model = _make_model(transient=True)
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert rm["transient_max_hours"] == 1.0
        assert rm["transient_max_count"] == 0

    def test_transient_model_custom_values(self):
        """TransientModel respects custom max_hours and max_count."""
        model = _make_model(
            transient=True,
            transient_max_hours=2.5,
            transient_max_count=500,
        )
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert rm["transient_max_hours"] == 2.5
        assert rm["transient_max_count"] == 500

    def test_read_group_fields(self):
        """Selection/Many2one fields with index get read_group_fields.

        Date/Datetime fields only appear in read_group_fields if they have
        index=True (e.g. from being in model order or domain fields).
        """
        fields = [
            {"name": "state", "type": "Selection"},
            {"name": "partner_id", "type": "Many2one"},
            {"name": "start_date", "type": "Date"},
            {"name": "notes", "type": "Text"},
        ]
        model = _make_model(fields=fields)
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert "read_group_fields" in rm
        rg = rm["read_group_fields"]
        # Selection and Many2one get index=True via search fields
        assert "state" in rg
        assert "partner_id" in rg
        # Date does not get index=True (not in search fields, order, or domain)
        assert "start_date" not in rg
        assert "notes" not in rg

    def test_read_group_fields_date_with_order(self):
        """Date field in model order gets index and appears in read_group_fields."""
        fields = [
            {"name": "start_date", "type": "Date"},
        ]
        model = _make_model(fields=fields, order="start_date desc")
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert "read_group_fields" in rm
        assert "start_date" in rm["read_group_fields"]

    def test_empty_spec_no_models(self):
        """Empty models list returns spec unchanged."""
        spec = _make_spec(models=[])

        result = _process_performance(spec)

        assert result is spec

    def test_model_no_fields(self):
        """Model with no fields does not crash."""
        model = _make_model(fields=[])
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rm = result["models"][0]
        assert rm["fields"] == []

    def test_immutability_input_not_mutated(self):
        """Input spec and field dicts are not mutated."""
        fields = [{"name": "title", "type": "Char"}]
        model = _make_model(fields=fields)
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        # Original field should not have index
        assert "index" not in fields[0]
        # Result field should
        assert result["models"][0]["fields"][0].get("index") is True

    def test_internal_fields_not_indexed(self):
        """Fields marked internal are excluded from search field index."""
        fields = [
            {"name": "internal_code", "type": "Char", "internal": True},
        ]
        model = _make_model(fields=fields)
        spec = _make_spec(models=[model])

        result = _process_performance(spec)

        rf = result["models"][0]["fields"]
        assert "index" not in rf[0]


class TestValidateWhereClause:
    """Tests for _validate_where_clause."""

    def test_none_is_safe(self):
        assert _validate_where_clause(None) is True

    def test_empty_string_is_safe(self):
        assert _validate_where_clause("") is True

    def test_simple_predicate_is_safe(self):
        assert _validate_where_clause("active = True") is True

    def test_drop_is_dangerous(self):
        assert _validate_where_clause("1=1; DROP TABLE users") is False

    def test_delete_is_dangerous(self):
        assert _validate_where_clause("DELETE FROM users") is False

    def test_union_is_dangerous(self):
        assert _validate_where_clause("1=1 UNION SELECT * FROM users") is False

    def test_semicolon_is_dangerous(self):
        assert _validate_where_clause("active = True;") is False

    def test_comment_is_dangerous(self):
        assert _validate_where_clause("active = True -- comment") is False

    def test_non_string_is_unsafe(self):
        assert _validate_where_clause(42) is False  # type: ignore[arg-type]
