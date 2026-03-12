"""Tests for i18n_extractor.py - Static .pot file generation for Odoo modules.

Tests for extract_python_strings(), extract_xml_strings(), extract_translatable_strings(),
and generate_pot() functions.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from amil_utils.i18n_extractor import (
    extract_python_strings,
    extract_translatable_strings,
    extract_xml_strings,
    generate_pot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_file(directory: Path, name: str, content: str) -> Path:
    """Write a file in the given directory and return its path."""
    file_path = directory / name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return file_path


# ---------------------------------------------------------------------------
# extract_python_strings
# ---------------------------------------------------------------------------


class TestExtractPythonStrings:
    def test_finds_double_quoted_underscore_call(self, tmp_path: Path) -> None:
        """extract_python_strings finds _("Hello") in a .py file."""
        py_file = _write_file(tmp_path, "file.py", 'x = _("Hello")\n')
        result = extract_python_strings(py_file)
        assert len(result) == 1
        assert result[0][0] == "Hello"
        assert result[0][1] == str(py_file)
        assert result[0][2] == 1

    def test_finds_single_quoted_underscore_call(self, tmp_path: Path) -> None:
        """extract_python_strings finds _('Single quotes') and handles both quote styles."""
        py_file = _write_file(tmp_path, "file.py", "x = _('Single quotes')\n")
        result = extract_python_strings(py_file)
        assert len(result) == 1
        assert result[0][0] == "Single quotes"

    def test_ignores_non_underscore_function_calls(self, tmp_path: Path) -> None:
        """extract_python_strings ignores non-_() function calls (e.g., str("foo"))."""
        py_file = _write_file(
            tmp_path,
            "file.py",
            'x = str("foo")\ny = print("bar")\nz = gettext("baz")\n',
        )
        result = extract_python_strings(py_file)
        assert result == []

    def test_finds_multiple_underscore_calls(self, tmp_path: Path) -> None:
        """extract_python_strings handles multiple _() calls in one file."""
        py_file = _write_file(
            tmp_path,
            "file.py",
            'a = _("First")\nb = _("Second")\nc = _("Third")\n',
        )
        result = extract_python_strings(py_file)
        assert len(result) == 3
        msgids = [r[0] for r in result]
        assert msgids == ["First", "Second", "Third"]

    def test_returns_empty_list_for_no_underscore_calls(self, tmp_path: Path) -> None:
        """extract_python_strings returns empty list for file with no _() calls."""
        py_file = _write_file(
            tmp_path,
            "file.py",
            "x = 42\ny = 'hello'\n",
        )
        result = extract_python_strings(py_file)
        assert result == []


# ---------------------------------------------------------------------------
# extract_python_strings — field string= patterns
# ---------------------------------------------------------------------------


class TestExtractFieldStrings:
    """Tests for fields.*(string="...") extraction in extract_python_strings."""

    def test_finds_fields_char_string(self, tmp_path: Path) -> None:
        """extract_python_strings finds fields.Char(string="Order Name")."""
        py_file = _write_file(
            tmp_path, "models/order.py",
            'from odoo import fields, models\n'
            '\n'
            'class Order(models.Model):\n'
            '    name = fields.Char(string="Order Name")\n',
        )
        result = extract_python_strings(py_file)
        assert len(result) == 1
        assert result[0][0] == "Order Name"

    def test_finds_many2one_with_positional_and_string(self, tmp_path: Path) -> None:
        """extract_python_strings finds fields.Many2one('res.partner', string="Customer")."""
        py_file = _write_file(
            tmp_path, "models/order.py",
            'from odoo import fields, models\n'
            '\n'
            'class Order(models.Model):\n'
            '    partner_id = fields.Many2one("res.partner", string="Customer")\n',
        )
        result = extract_python_strings(py_file)
        assert len(result) == 1
        assert result[0][0] == "Customer"

    def test_finds_selection_with_string(self, tmp_path: Path) -> None:
        """extract_python_strings finds fields.Selection([...], string="Status")."""
        py_file = _write_file(
            tmp_path, "models/order.py",
            'from odoo import fields, models\n'
            '\n'
            'class Order(models.Model):\n'
            '    state = fields.Selection(\n'
            '        [("draft", "Draft"), ("done", "Done")],\n'
            '        string="Status",\n'
            '    )\n',
        )
        result = extract_python_strings(py_file)
        assert len(result) == 1
        assert result[0][0] == "Status"

    def test_finds_multiple_field_types(self, tmp_path: Path) -> None:
        """extract_python_strings finds string= across Text, Boolean, Float field types."""
        py_file = _write_file(
            tmp_path, "models/order.py",
            'from odoo import fields, models\n'
            '\n'
            'class Order(models.Model):\n'
            '    note = fields.Text(string="Internal Notes")\n'
            '    active = fields.Boolean(string="Active")\n'
            '    amount = fields.Float(string="Total Amount")\n',
        )
        result = extract_python_strings(py_file)
        msgids = sorted(r[0] for r in result)
        assert msgids == ["Active", "Internal Notes", "Total Amount"]

    def test_ignores_field_without_string_keyword(self, tmp_path: Path) -> None:
        """extract_python_strings ignores fields.Char(required=True) with no string=."""
        py_file = _write_file(
            tmp_path, "models/order.py",
            'from odoo import fields, models\n'
            '\n'
            'class Order(models.Model):\n'
            '    name = fields.Char(required=True)\n'
            '    active = fields.Boolean(default=True)\n',
        )
        result = extract_python_strings(py_file)
        assert result == []

    def test_ignores_help_keyword_not_string(self, tmp_path: Path) -> None:
        """extract_python_strings ignores help= keyword (only string= matters)."""
        py_file = _write_file(
            tmp_path, "models/order.py",
            'from odoo import fields, models\n'
            '\n'
            'class Order(models.Model):\n'
            '    name = fields.Char(help="Enter the order name")\n',
        )
        result = extract_python_strings(py_file)
        assert result == []

    def test_coexists_with_underscore_calls(self, tmp_path: Path) -> None:
        """extract_python_strings finds both _() calls and fields.*(string=...) in same file."""
        py_file = _write_file(
            tmp_path, "models/order.py",
            'from odoo import _, fields, models\n'
            '\n'
            'class Order(models.Model):\n'
            '    name = fields.Char(string="Order Name")\n'
            '\n'
            '    def action_confirm(self):\n'
            '        raise UserError(_("Cannot confirm"))\n',
        )
        result = extract_python_strings(py_file)
        msgids = sorted(r[0] for r in result)
        assert msgids == ["Cannot confirm", "Order Name"]

    def test_field_string_has_correct_line_number(self, tmp_path: Path) -> None:
        """extract_python_strings returns correct line number for field string= entries."""
        py_file = _write_file(
            tmp_path, "models/order.py",
            'from odoo import fields, models\n'
            '\n'
            'class Order(models.Model):\n'
            '    name = fields.Char(string="Name")\n'
            '    desc = fields.Text(string="Description")\n',
        )
        result = extract_python_strings(py_file)
        lines = {r[0]: r[2] for r in result}
        assert lines["Name"] == 4
        assert lines["Description"] == 5

    def test_extract_translatable_includes_field_strings(self, tmp_path: Path) -> None:
        """extract_translatable_strings includes field string= entries from .py files."""
        _write_file(
            tmp_path / "models", "order.py",
            'from odoo import fields, models\n'
            '\n'
            'class Order(models.Model):\n'
            '    name = fields.Char(string="Order Name")\n',
        )
        result = extract_translatable_strings(tmp_path)
        msgids = [r[0] for r in result]
        assert "Order Name" in msgids


# ---------------------------------------------------------------------------
# extract_xml_strings
# ---------------------------------------------------------------------------


class TestExtractXmlStrings:
    def test_finds_string_attribute(self, tmp_path: Path) -> None:
        """extract_xml_strings finds string="Label" attributes in XML elements."""
        xml_file = _write_file(
            tmp_path,
            "view.xml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<odoo>\n"
            '  <field name="name" string="Label"/>\n'
            "</odoo>\n",
        )
        result = extract_xml_strings(xml_file)
        assert len(result) == 1
        assert result[0][0] == "Label"
        assert result[0][1] == str(xml_file)

    def test_finds_label_element_text(self, tmp_path: Path) -> None:
        """extract_xml_strings finds text content inside label elements."""
        xml_file = _write_file(
            tmp_path,
            "view.xml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<odoo>\n"
            "  <label>My Label Text</label>\n"
            "</odoo>\n",
        )
        result = extract_xml_strings(xml_file)
        assert len(result) == 1
        assert result[0][0] == "My Label Text"

    def test_returns_empty_list_for_no_translatable_strings(self, tmp_path: Path) -> None:
        """extract_xml_strings returns empty list for XML with no translatable strings."""
        xml_file = _write_file(
            tmp_path,
            "view.xml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<odoo>\n"
            '  <field name="name"/>\n'
            "</odoo>\n",
        )
        result = extract_xml_strings(xml_file)
        assert result == []

    def test_handles_malformed_xml_gracefully(self, tmp_path: Path) -> None:
        """extract_xml_strings handles malformed XML gracefully (returns empty, no crash)."""
        xml_file = _write_file(
            tmp_path,
            "bad.xml",
            "<odoo><unclosed>\n",
        )
        result = extract_xml_strings(xml_file)
        assert result == []

    def test_line_number_is_zero_for_xml(self, tmp_path: Path) -> None:
        """ElementTree does not track line numbers reliably; use 0 as line for XML entries."""
        xml_file = _write_file(
            tmp_path,
            "view.xml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<odoo>\n"
            '  <field name="x" string="Test"/>\n'
            "</odoo>\n",
        )
        result = extract_xml_strings(xml_file)
        assert len(result) == 1
        assert result[0][2] == 0


# ---------------------------------------------------------------------------
# extract_translatable_strings
# ---------------------------------------------------------------------------


class TestExtractTranslatableStrings:
    def test_scans_directory_finds_py_and_xml(self, tmp_path: Path) -> None:
        """extract_translatable_strings scans a directory, finds strings from both .py and .xml files."""
        _write_file(
            tmp_path / "models",
            "order.py",
            'from odoo import _\nx = _("Order Name")\n',
        )
        _write_file(
            tmp_path / "views",
            "order_views.xml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<odoo>\n"
            '  <field name="name" string="Order Label"/>\n'
            "</odoo>\n",
        )
        result = extract_translatable_strings(tmp_path)
        msgids = [r[0] for r in result]
        assert "Order Name" in msgids
        assert "Order Label" in msgids
        assert len(result) == 2


# ---------------------------------------------------------------------------
# generate_pot
# ---------------------------------------------------------------------------


class TestGeneratePot:
    def test_produces_valid_pot_header(self) -> None:
        """generate_pot creates valid POT content with standard Odoo header (Project-Id-Version: Odoo Server 19.0)."""
        pot = generate_pot("test_module", [])
        assert "Project-Id-Version: Odoo Server 19.0" in pot
        assert "MIME-Version: 1.0" in pot
        assert "Content-Type: text/plain; charset=UTF-8" in pot

    def test_includes_msgid_entries(self) -> None:
        """generate_pot includes msgid entries for each extracted string."""
        strings = [
            ("Hello", "models/order.py", 5),
            ("World", "views/form.xml", 0),
        ]
        pot = generate_pot("test_module", strings)
        assert 'msgid "Hello"' in pot
        assert 'msgid "World"' in pot
        assert 'msgstr ""' in pot

    def test_empty_strings_still_produces_header(self) -> None:
        """generate_pot with empty string list still produces valid POT header (never skip generation)."""
        pot = generate_pot("test_module", [])
        assert pot.strip() != ""
        assert "Project-Id-Version: Odoo Server 19.0" in pot
        assert 'msgid ""' in pot
        assert 'msgstr ""' in pot

    def test_includes_source_references(self) -> None:
        """generate_pot includes #: file:line source references in POT entries."""
        strings = [("Hello", "models/order.py", 5)]
        pot = generate_pot("test_module", strings)
        assert "#: models/order.py:5" in pot

    def test_deduplicates_identical_msgids(self) -> None:
        """generate_pot deduplicates identical msgid strings (merges source references)."""
        strings = [
            ("Hello", "models/order.py", 5),
            ("Hello", "models/sale.py", 10),
        ]
        pot = generate_pot("test_module", strings)
        # Should have only one msgid "Hello" entry
        assert pot.count('msgid "Hello"') == 1
        # Both source references should be present
        assert "#: models/order.py:5" in pot
        assert "#: models/sale.py:10" in pot

    def test_pot_header_comment_includes_module_name(self) -> None:
        """POT header comment includes module name."""
        pot = generate_pot("my_sales", [])
        assert "my_sales" in pot
