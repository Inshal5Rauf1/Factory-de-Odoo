"""Tests for error pattern library and diagnosis engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amil_utils.validation.error_patterns import diagnose_errors, load_error_patterns


class TestLoadPatterns:
    """Tests for load_error_patterns()."""

    def test_load_patterns_returns_tuple_of_dicts(self) -> None:
        """load_error_patterns() returns a tuple of dicts."""
        patterns = load_error_patterns()
        assert isinstance(patterns, tuple)
        assert len(patterns) > 0
        assert all(isinstance(p, dict) for p in patterns)

    def test_load_patterns_count(self) -> None:
        """Pattern library has at least 20 patterns."""
        patterns = load_error_patterns()
        assert len(patterns) >= 20

    def test_load_patterns_required_fields(self) -> None:
        """Each pattern has required fields: id, regex, explanation, suggestion, severity."""
        patterns = load_error_patterns()
        required_fields = {"id", "regex", "explanation", "suggestion", "severity"}
        for pattern in patterns:
            missing = required_fields - set(pattern.keys())
            assert not missing, f"Pattern {pattern.get('id', '?')} missing fields: {missing}"

    def test_load_patterns_unique_ids(self) -> None:
        """All pattern IDs are unique."""
        patterns = load_error_patterns()
        ids = [p["id"] for p in patterns]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"

    def test_pattern_severity_levels(self) -> None:
        """All patterns have severity in ('error', 'warning', 'info')."""
        patterns = load_error_patterns()
        valid_severities = {"error", "warning", "info"}
        for pattern in patterns:
            assert pattern["severity"] in valid_severities, (
                f"Pattern {pattern['id']} has invalid severity: {pattern['severity']}"
            )

    def test_json_file_is_valid(self) -> None:
        """The JSON data file is valid and parseable."""
        json_path = (
            Path(__file__).parent.parent
            / "src"
            / "amil_utils"
            / "validation"
            / "data"
            / "error_patterns.json"
        )
        assert json_path.exists(), f"JSON file not found: {json_path}"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)


class TestDiagnoseFieldNotFound:
    """Tests for field-not-found pattern matching."""

    def test_diagnose_field_not_found(self) -> None:
        """Log with KeyError matches field-not-found pattern."""
        log = """
Traceback (most recent call last):
  File "/odoo/addons/my_module/models/sale.py", line 42, in _compute_total
    value = record['missing_field']
KeyError: 'missing_field'
"""
        results = diagnose_errors(log)
        assert len(results) >= 1
        matched_ids = [r for r in results if "field" in r.lower() or "KeyError" in r]
        assert len(matched_ids) >= 1, f"Expected field-not-found match, got: {results}"


class TestDiagnoseXmlParseError:
    """Tests for XML parse error pattern matching."""

    def test_diagnose_xml_parse_error(self) -> None:
        """Log with ParseError or XMLSyntaxError matches xml-parse-error pattern."""
        log = """
2024-01-15 10:30:00,000 1 ERROR test_db odoo.tools.convert: ParseError: "mismatched tag"
  File "/odoo/addons/my_module/views/sale_view.xml", line 15
lxml.etree.XMLSyntaxError: Opening and ending tag mismatch: field line 10 and form
"""
        results = diagnose_errors(log)
        assert len(results) >= 1
        matched = [r for r in results if "XML" in r or "parse" in r.lower() or "syntax" in r.lower()]
        assert len(matched) >= 1, f"Expected xml-parse-error match, got: {results}"


class TestDiagnoseAccessDenied:
    """Tests for access-denied pattern matching."""

    def test_diagnose_access_denied(self) -> None:
        """Log with AccessError matches access-denied pattern."""
        log = """
2024-01-15 10:30:00,000 1 ERROR test_db odoo.http: AccessError
odoo.exceptions.AccessError: You are not allowed to access 'Sale Order' (sale.order) records.
"""
        results = diagnose_errors(log)
        assert len(results) >= 1
        matched = [r for r in results if "access" in r.lower() or "permission" in r.lower()]
        assert len(matched) >= 1, f"Expected access-denied match, got: {results}"


class TestDiagnoseModuleNotFound:
    """Tests for module-not-found pattern matching."""

    def test_diagnose_module_not_found(self) -> None:
        """Log with 'No module named' matches module-not-found pattern."""
        log = """
Traceback (most recent call last):
  File "/odoo/odoo/modules/module.py", line 100, in load_module
    importlib.import_module('odoo.addons.missing_module')
ModuleNotFoundError: No module named 'odoo.addons.missing_module'
"""
        results = diagnose_errors(log)
        assert len(results) >= 1
        matched = [r for r in results if "module" in r.lower() or "import" in r.lower() or "not found" in r.lower()]
        assert len(matched) >= 1, f"Expected module-not-found match, got: {results}"


class TestDiagnoseDeprecatedAttrs:
    """Tests for deprecated-attrs pattern matching (Odoo 17)."""

    def test_diagnose_deprecated_attrs(self) -> None:
        """Log/code with attrs= matches deprecated-attrs pattern."""
        log = """
2024-01-15 10:30:00,000 1 WARNING test_db odoo.addons.base.models.ir_ui_view:
Field 'partner_id' uses deprecated 'attrs' attribute in view definition.
attrs="{'invisible': [('state', '!=', 'draft')]}"
"""
        results = diagnose_errors(log)
        assert len(results) >= 1
        matched = [r for r in results if "attrs" in r.lower() or "deprecated" in r.lower()]
        assert len(matched) >= 1, f"Expected deprecated-attrs match, got: {results}"


class TestDiagnoseMultipleMatches:
    """Tests for multiple pattern matches."""

    def test_diagnose_multiple_matches(self) -> None:
        """Log with multiple error types returns multiple diagnosis entries."""
        log = """
2024-01-15 10:30:00,000 1 ERROR test_db odoo.http: AccessError
odoo.exceptions.AccessError: You are not allowed to access records.

lxml.etree.XMLSyntaxError: Opening and ending tag mismatch

Traceback (most recent call last):
  File "/odoo/addons/my_module/models/sale.py", line 42
KeyError: 'missing_field'
"""
        results = diagnose_errors(log)
        assert len(results) >= 2, f"Expected at least 2 matches, got {len(results)}: {results}"


class TestDiagnoseNoMatch:
    """Tests for unrecognized error fallback."""

    def test_diagnose_no_match(self) -> None:
        """Log with unrecognized error returns raw traceback with file highlighted."""
        log = """
Traceback (most recent call last):
  File "/odoo/addons/my_module/models/sale.py", line 99, in obscure_method
    something.very_unusual_error()
VeryUnusualException: This is a custom exception nobody has seen before
"""
        results = diagnose_errors(log)
        assert len(results) >= 1
        # Should contain the raw traceback
        combined = " ".join(results)
        assert "traceback" in combined.lower() or "VeryUnusualException" in combined


class TestDiagnoseEmptyLog:
    """Tests for empty log input."""

    def test_diagnose_empty_log(self) -> None:
        """Empty log returns empty tuple."""
        results = diagnose_errors("")
        assert results == ()

    def test_diagnose_none_like_log(self) -> None:
        """Whitespace-only log returns empty tuple."""
        results = diagnose_errors("   \n\n   ")
        assert results == ()


class TestDiagnoseDeprecatedTreeTag:
    """Tests for deprecated-tree-tag pattern."""

    def test_diagnose_deprecated_tree_tag(self) -> None:
        """Log referencing <tree> tag matches deprecated pattern."""
        log = """
2024-01-15 10:30:00,000 1 WARNING test_db odoo.addons.base.models.ir_ui_view:
View uses deprecated <tree> tag. Use <list> instead in Odoo 17.0.
"""
        results = diagnose_errors(log)
        assert len(results) >= 1
        matched = [r for r in results if "tree" in r.lower() or "list" in r.lower() or "deprecated" in r.lower()]
        assert len(matched) >= 1, f"Expected deprecated-tree-tag match, got: {results}"


class TestDiagnoseDeprecatedApiOne:
    """Tests for deprecated-api-one pattern."""

    def test_diagnose_deprecated_api_one(self) -> None:
        """Log referencing api.one matches deprecated pattern."""
        log = """
AttributeError: module 'odoo.api' has no attribute 'one'
@api.one was removed in Odoo 17.0. Use @api.depends or @api.model instead.
"""
        results = diagnose_errors(log)
        assert len(results) >= 1
        matched = [r for r in results if "api.one" in r.lower() or "deprecated" in r.lower()]
        assert len(matched) >= 1, f"Expected deprecated-api-one match, got: {results}"


class TestDiagnoseDeprecatedOpenerp:
    """Tests for deprecated-openerp-import pattern."""

    def test_diagnose_deprecated_openerp_import(self) -> None:
        """Log referencing 'from openerp' matches deprecated pattern."""
        log = """
Traceback (most recent call last):
  File "/odoo/addons/my_module/__init__.py", line 1, in <module>
    from openerp import models, fields, api
ModuleNotFoundError: No module named 'openerp'
"""
        results = diagnose_errors(log)
        assert len(results) >= 1
        matched = [r for r in results if "openerp" in r.lower() or "deprecated" in r.lower() or "odoo" in r.lower()]
        assert len(matched) >= 1, f"Expected deprecated-openerp-import match, got: {results}"
