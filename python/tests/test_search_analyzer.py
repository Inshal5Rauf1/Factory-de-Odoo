"""Unit tests for search/analyzer.py — Odoo module structure analysis.

Uses tmp_path fixtures to create realistic module directory trees
with Python model files, XML views, security files, and manifests.
"""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from amil_utils.search.analyzer import (
    ModuleAnalysis,
    _extract_inherit_only,
    _extract_models_from_file,
    _extract_security_groups,
    _extract_view_types,
    analyze_module,
    format_analysis_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_MANIFEST = dedent("""\
    {
        'name': 'Test Module',
        'version': '17.0.1.0.0',
        'category': 'Sales',
        'depends': ['base', 'sale'],
        'data': [
            'security/ir.model.access.csv',
            'views/test_views.xml',
        ],
    }
""")


def _write_model_file(models_dir: Path, filename: str, content: str) -> Path:
    """Write a Python model file into the models directory."""
    filepath = models_dir / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _make_module(
    tmp_path: Path,
    *,
    manifest: str = _SAMPLE_MANIFEST,
    model_files: dict[str, str] | None = None,
    view_xml: str | None = None,
    security_xml: str | None = None,
    has_wizards: bool = False,
    has_tests: bool = False,
) -> Path:
    """Create a complete mock Odoo module directory tree."""
    mod = tmp_path / "test_module"
    mod.mkdir()

    # __manifest__.py
    (mod / "__manifest__.py").write_text(manifest, encoding="utf-8")

    # models/
    if model_files:
        models_dir = mod / "models"
        models_dir.mkdir()
        (models_dir / "__init__.py").write_text("", encoding="utf-8")
        for fname, content in model_files.items():
            _write_model_file(models_dir, fname, content)

    # views/
    if view_xml:
        views_dir = mod / "views"
        views_dir.mkdir()
        (views_dir / "test_views.xml").write_text(view_xml, encoding="utf-8")

    # security/
    if security_xml:
        sec_dir = mod / "security"
        sec_dir.mkdir()
        (sec_dir / "security.xml").write_text(
            security_xml, encoding="utf-8"
        )

    # Optional directories
    if has_wizards:
        (mod / "wizards").mkdir()
    if has_tests:
        (mod / "tests").mkdir()

    return mod


# ---------------------------------------------------------------------------
# ModuleAnalysis dataclass
# ---------------------------------------------------------------------------


class TestModuleAnalysis:
    """ModuleAnalysis is a frozen dataclass with expected fields."""

    def test_frozen(self) -> None:
        analysis = ModuleAnalysis(
            module_name="m",
            manifest={},
            model_names=(),
            model_fields={},
            field_types={},
            view_types={},
            security_groups=(),
            data_files=(),
            has_wizards=False,
            has_tests=False,
        )
        with pytest.raises(AttributeError):
            analysis.module_name = "other"  # type: ignore[misc]

    def test_inherited_models_defaults_empty(self) -> None:
        analysis = ModuleAnalysis(
            module_name="m",
            manifest={},
            model_names=(),
            model_fields={},
            field_types={},
            view_types={},
            security_groups=(),
            data_files=(),
            has_wizards=False,
            has_tests=False,
        )
        assert analysis.inherited_models == ()


# ---------------------------------------------------------------------------
# _extract_models_from_file
# ---------------------------------------------------------------------------


class TestExtractModelsFromFile:
    """Test AST-based model and field extraction from Python files."""

    def test_single_model_with_fields(self, tmp_path: Path) -> None:
        code = dedent("""\
            from odoo import models, fields

            class SaleOrder(models.Model):
                _name = 'sale.order'

                name = fields.Char(required=True)
                amount = fields.Float(digits=(16, 2))
                partner_id = fields.Many2one('res.partner')
        """)
        f = tmp_path / "sale_order.py"
        f.write_text(code, encoding="utf-8")

        results = _extract_models_from_file(f)
        assert len(results) == 1
        model_name, fields_map = results[0]
        assert model_name == "sale.order"
        assert fields_map == {
            "name": "Char",
            "amount": "Float",
            "partner_id": "Many2one",
        }

    def test_multiple_models_in_one_file(self, tmp_path: Path) -> None:
        code = dedent("""\
            from odoo import models, fields

            class ModelA(models.Model):
                _name = 'test.model_a'
                title = fields.Char()

            class ModelB(models.Model):
                _name = 'test.model_b'
                value = fields.Integer()
        """)
        f = tmp_path / "multi.py"
        f.write_text(code, encoding="utf-8")

        results = _extract_models_from_file(f)
        assert len(results) == 2
        names = {r[0] for r in results}
        assert names == {"test.model_a", "test.model_b"}

    def test_class_without_name_ignored(self, tmp_path: Path) -> None:
        code = dedent("""\
            from odoo import models, fields

            class Mixin(models.AbstractModel):
                # No _name assignment
                some_field = fields.Boolean()
        """)
        f = tmp_path / "mixin.py"
        f.write_text(code, encoding="utf-8")

        results = _extract_models_from_file(f)
        assert results == []

    def test_syntax_error_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.py"
        f.write_text("def broken(:\n    pass", encoding="utf-8")

        results = _extract_models_from_file(f)
        assert results == []

    def test_non_field_assignments_ignored(self, tmp_path: Path) -> None:
        code = dedent("""\
            from odoo import models, fields

            class TestModel(models.Model):
                _name = 'test.model'
                _description = 'Test'

                name = fields.Char()
                # This is not a field assignment
                some_constant = 42
                another = "string"
        """)
        f = tmp_path / "test_model.py"
        f.write_text(code, encoding="utf-8")

        results = _extract_models_from_file(f)
        assert len(results) == 1
        _, fields_map = results[0]
        assert fields_map == {"name": "Char"}

    def test_all_field_types_detected(self, tmp_path: Path) -> None:
        """Every recognized Odoo field type is properly extracted."""
        field_lines = []
        expected = {}
        for i, ftype in enumerate(sorted([
            "Char", "Text", "Html", "Integer", "Float", "Monetary",
            "Boolean", "Date", "Datetime", "Binary", "Image",
            "Selection", "Reference", "Many2one", "One2many", "Many2many",
        ])):
            fname = f"f_{ftype.lower()}"
            field_lines.append(f"    {fname} = fields.{ftype}()")
            expected[fname] = ftype

        code = (
            "from odoo import models, fields\n\n"
            "class AllTypes(models.Model):\n"
            "    _name = 'test.all_types'\n"
            + "\n".join(field_lines) + "\n"
        )
        f = tmp_path / "all_types.py"
        f.write_text(code, encoding="utf-8")

        results = _extract_models_from_file(f)
        assert len(results) == 1
        _, fields_map = results[0]
        assert fields_map == expected


# ---------------------------------------------------------------------------
# _extract_inherit_only
# ---------------------------------------------------------------------------


class TestExtractInheritOnly:
    """Test detection of _inherit-only model extensions."""

    def test_inherit_string(self, tmp_path: Path) -> None:
        code = dedent("""\
            from odoo import models, fields

            class ResPartnerExt(models.Model):
                _inherit = 'res.partner'
                custom_field = fields.Char()
        """)
        f = tmp_path / "ext.py"
        f.write_text(code, encoding="utf-8")

        result = _extract_inherit_only(f)
        assert result == ["res.partner"]

    def test_inherit_list(self, tmp_path: Path) -> None:
        code = dedent("""\
            from odoo import models, fields

            class MultiInherit(models.Model):
                _inherit = ['mail.thread', 'mail.activity.mixin']
        """)
        f = tmp_path / "multi.py"
        f.write_text(code, encoding="utf-8")

        result = _extract_inherit_only(f)
        assert result == ["mail.thread", "mail.activity.mixin"]

    def test_inherit_with_name_excluded(self, tmp_path: Path) -> None:
        """Classes with both _name and _inherit are new models, not extensions."""
        code = dedent("""\
            from odoo import models, fields

            class NewModel(models.Model):
                _name = 'custom.model'
                _inherit = ['mail.thread']
                name = fields.Char()
        """)
        f = tmp_path / "new.py"
        f.write_text(code, encoding="utf-8")

        result = _extract_inherit_only(f)
        assert result == []

    def test_syntax_error_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.py"
        f.write_text("class Bad(:\n  pass", encoding="utf-8")
        assert _extract_inherit_only(f) == []


# ---------------------------------------------------------------------------
# _extract_view_types
# ---------------------------------------------------------------------------


_VIEW_XML = dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <odoo>
        <record id="view_partner_form" model="ir.ui.view">
            <field name="name">res.partner.form</field>
            <field name="model">res.partner</field>
            <field name="arch" type="xml">
                <form string="Partner">
                    <field name="name"/>
                </form>
            </field>
        </record>
        <record id="view_partner_tree" model="ir.ui.view">
            <field name="name">res.partner.tree</field>
            <field name="model">res.partner</field>
            <field name="arch" type="xml">
                <tree string="Partners">
                    <field name="name"/>
                </tree>
            </field>
        </record>
        <record id="view_partner_search" model="ir.ui.view">
            <field name="name">res.partner.search</field>
            <field name="model">res.partner</field>
            <field name="arch" type="xml">
                <search string="Search">
                    <field name="name"/>
                </search>
            </field>
        </record>
    </odoo>
""")


class TestExtractViewTypes:
    """Test XML parsing for view type extraction."""

    def test_extracts_form_tree_search(self, tmp_path: Path) -> None:
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        (views_dir / "partner_views.xml").write_text(
            _VIEW_XML, encoding="utf-8"
        )

        result = _extract_view_types(views_dir)
        assert "res.partner" in result
        types = result["res.partner"]
        assert "form" in types
        assert "tree" in types
        assert "search" in types

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        result = _extract_view_types(tmp_path / "nonexistent")
        assert result == {}

    def test_invalid_xml_skipped(self, tmp_path: Path) -> None:
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        (views_dir / "bad.xml").write_text(
            "<broken><xml", encoding="utf-8"
        )
        result = _extract_view_types(views_dir)
        assert result == {}

    def test_non_view_records_ignored(self, tmp_path: Path) -> None:
        xml = dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="action_partner" model="ir.actions.act_window">
                    <field name="name">Partners</field>
                    <field name="res_model">res.partner</field>
                </record>
            </odoo>
        """)
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        (views_dir / "actions.xml").write_text(xml, encoding="utf-8")

        result = _extract_view_types(views_dir)
        assert result == {}

    def test_multiple_models(self, tmp_path: Path) -> None:
        xml = dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="view_a_form" model="ir.ui.view">
                    <field name="model">model.a</field>
                    <field name="arch" type="xml">
                        <form><field name="name"/></form>
                    </field>
                </record>
                <record id="view_b_kanban" model="ir.ui.view">
                    <field name="model">model.b</field>
                    <field name="arch" type="xml">
                        <kanban><field name="name"/></kanban>
                    </field>
                </record>
            </odoo>
        """)
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        (views_dir / "views.xml").write_text(xml, encoding="utf-8")

        result = _extract_view_types(views_dir)
        assert "model.a" in result
        assert "model.b" in result
        assert "form" in result["model.a"]
        assert "kanban" in result["model.b"]

    def test_no_duplicate_view_types(self, tmp_path: Path) -> None:
        """Same view type for same model in two files is not duplicated."""
        xml_template = dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="view_{id}" model="ir.ui.view">
                    <field name="model">res.partner</field>
                    <field name="arch" type="xml">
                        <form><field name="name"/></form>
                    </field>
                </record>
            </odoo>
        """)
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        (views_dir / "a.xml").write_text(
            xml_template.format(id="a"), encoding="utf-8"
        )
        (views_dir / "b.xml").write_text(
            xml_template.format(id="b"), encoding="utf-8"
        )

        result = _extract_view_types(views_dir)
        assert result["res.partner"].count("form") == 1


# ---------------------------------------------------------------------------
# _extract_security_groups
# ---------------------------------------------------------------------------


class TestExtractSecurityGroups:
    """Test security group XML ID extraction."""

    def test_extracts_group_ids(self, tmp_path: Path) -> None:
        xml = dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="group_manager" model="res.groups">
                    <field name="name">Manager</field>
                </record>
                <record id="group_user" model="res.groups">
                    <field name="name">User</field>
                </record>
            </odoo>
        """)
        sec_dir = tmp_path / "security"
        sec_dir.mkdir()
        (sec_dir / "groups.xml").write_text(xml, encoding="utf-8")

        result = _extract_security_groups(sec_dir)
        assert "group_manager" in result
        assert "group_user" in result

    def test_category_with_group_in_id(self, tmp_path: Path) -> None:
        """ir.module.category records with 'group' in ID are captured."""
        xml = dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="module_category_group_test" model="ir.module.category">
                    <field name="name">Test Group Category</field>
                </record>
            </odoo>
        """)
        sec_dir = tmp_path / "security"
        sec_dir.mkdir()
        (sec_dir / "categories.xml").write_text(xml, encoding="utf-8")

        result = _extract_security_groups(sec_dir)
        assert "module_category_group_test" in result

    def test_category_without_group_ignored(self, tmp_path: Path) -> None:
        xml = dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="module_category_sales" model="ir.module.category">
                    <field name="name">Sales</field>
                </record>
            </odoo>
        """)
        sec_dir = tmp_path / "security"
        sec_dir.mkdir()
        (sec_dir / "cats.xml").write_text(xml, encoding="utf-8")

        result = _extract_security_groups(sec_dir)
        assert result == []

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        result = _extract_security_groups(tmp_path / "nonexistent")
        assert result == []

    def test_invalid_xml_skipped(self, tmp_path: Path) -> None:
        sec_dir = tmp_path / "security"
        sec_dir.mkdir()
        (sec_dir / "bad.xml").write_text("<broken", encoding="utf-8")
        result = _extract_security_groups(sec_dir)
        assert result == []


# ---------------------------------------------------------------------------
# analyze_module (integration of all extractors)
# ---------------------------------------------------------------------------


class TestAnalyzeModule:
    """Test the top-level analyze_module function."""

    def test_minimal_module(self, tmp_path: Path) -> None:
        mod = _make_module(tmp_path)
        analysis = analyze_module(mod)

        assert analysis.module_name == "test_module"
        assert analysis.manifest["name"] == "Test Module"
        assert analysis.manifest["version"] == "17.0.1.0.0"
        assert analysis.model_names == ()
        assert analysis.model_fields == {}
        assert analysis.view_types == {}
        assert analysis.security_groups == ()
        assert analysis.has_wizards is False
        assert analysis.has_tests is False

    def test_module_with_models(self, tmp_path: Path) -> None:
        model_code = dedent("""\
            from odoo import models, fields

            class SaleOrder(models.Model):
                _name = 'sale.order'
                name = fields.Char()
                amount = fields.Float()
        """)
        mod = _make_module(
            tmp_path,
            model_files={"sale_order.py": model_code},
        )
        analysis = analyze_module(mod)

        assert "sale.order" in analysis.model_names
        assert "name" in analysis.model_fields["sale.order"]
        assert "amount" in analysis.model_fields["sale.order"]
        assert analysis.field_types["sale.order"]["name"] == "Char"
        assert analysis.field_types["sale.order"]["amount"] == "Float"

    def test_module_with_views(self, tmp_path: Path) -> None:
        mod = _make_module(tmp_path, view_xml=_VIEW_XML)
        analysis = analyze_module(mod)

        assert "res.partner" in analysis.view_types
        assert "form" in analysis.view_types["res.partner"]

    def test_module_with_security(self, tmp_path: Path) -> None:
        security_xml = dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="group_admin" model="res.groups">
                    <field name="name">Admin</field>
                </record>
            </odoo>
        """)
        mod = _make_module(tmp_path, security_xml=security_xml)
        analysis = analyze_module(mod)

        assert "group_admin" in analysis.security_groups

    def test_module_with_wizards_and_tests(self, tmp_path: Path) -> None:
        mod = _make_module(
            tmp_path, has_wizards=True, has_tests=True
        )
        analysis = analyze_module(mod)

        assert analysis.has_wizards is True
        assert analysis.has_tests is True

    def test_data_files_from_manifest(self, tmp_path: Path) -> None:
        mod = _make_module(tmp_path)
        analysis = analyze_module(mod)

        assert "security/ir.model.access.csv" in analysis.data_files
        assert "views/test_views.xml" in analysis.data_files

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        mod = tmp_path / "no_manifest"
        mod.mkdir()
        with pytest.raises(FileNotFoundError, match="__manifest__.py"):
            analyze_module(mod)

    def test_inherited_models_detected(self, tmp_path: Path) -> None:
        ext_code = dedent("""\
            from odoo import models, fields

            class ResPartnerExt(models.Model):
                _inherit = 'res.partner'
                custom_tag = fields.Char()
        """)
        mod = _make_module(
            tmp_path,
            model_files={"partner_ext.py": ext_code},
        )
        analysis = analyze_module(mod)

        assert "res.partner" in analysis.inherited_models

    def test_data_files_non_list_handled(self, tmp_path: Path) -> None:
        """If manifest 'data' is not a list, data_files is empty tuple."""
        manifest = dedent("""\
            {
                'name': 'Bad Data',
                'data': 'not_a_list',
            }
        """)
        mod = _make_module(tmp_path, manifest=manifest)
        analysis = analyze_module(mod)
        assert analysis.data_files == ()

    def test_init_py_in_models_skipped(self, tmp_path: Path) -> None:
        """__init__.py in models/ is not processed for model extraction."""
        init_code = "from . import sale_order\n"
        model_code = dedent("""\
            from odoo import models, fields

            class SaleOrder(models.Model):
                _name = 'sale.order'
                name = fields.Char()
        """)
        mod = _make_module(
            tmp_path,
            model_files={"sale_order.py": model_code},
        )
        # The __init__.py is already created by _make_module; overwrite it
        (mod / "models" / "__init__.py").write_text(
            init_code, encoding="utf-8"
        )
        analysis = analyze_module(mod)

        # Should still find sale.order but not treat __init__.py as a model
        assert analysis.model_names == ("sale.order",)


# ---------------------------------------------------------------------------
# format_analysis_text
# ---------------------------------------------------------------------------


class TestFormatAnalysisText:
    """Test human-readable text formatting of ModuleAnalysis."""

    def _minimal_analysis(self, **overrides) -> ModuleAnalysis:
        defaults = {
            "module_name": "test_mod",
            "manifest": {"name": "Test", "version": "17.0.1.0.0", "category": "HR"},
            "model_names": (),
            "model_fields": {},
            "field_types": {},
            "view_types": {},
            "security_groups": (),
            "data_files": (),
            "has_wizards": False,
            "has_tests": False,
        }
        return ModuleAnalysis(**{**defaults, **overrides})

    def test_module_name_in_output(self) -> None:
        text = format_analysis_text(self._minimal_analysis())
        assert "Module: test_mod" in text

    def test_display_name_shown(self) -> None:
        text = format_analysis_text(self._minimal_analysis())
        assert "Display Name: Test" in text

    def test_version_shown(self) -> None:
        text = format_analysis_text(self._minimal_analysis())
        assert "Version: 17.0.1.0.0" in text

    def test_category_shown(self) -> None:
        text = format_analysis_text(self._minimal_analysis())
        assert "Category: HR" in text

    def test_models_listed(self) -> None:
        analysis = self._minimal_analysis(
            model_names=("hr.employee",),
            model_fields={"hr.employee": ("name", "age")},
            field_types={"hr.employee": {"name": "Char", "age": "Integer"}},
        )
        text = format_analysis_text(analysis)
        assert "hr.employee:" in text
        assert "name (Char)" in text
        assert "age (Integer)" in text

    def test_inherited_models_listed(self) -> None:
        analysis = self._minimal_analysis(
            inherited_models=("res.partner", "mail.thread"),
        )
        text = format_analysis_text(analysis)
        assert "Inherited Models (extensions):" in text
        assert "res.partner" in text
        assert "mail.thread" in text

    def test_views_listed(self) -> None:
        analysis = self._minimal_analysis(
            view_types={"hr.employee": ("form", "tree")},
        )
        text = format_analysis_text(analysis)
        assert "Views:" in text
        assert "hr.employee: form, tree" in text

    def test_security_groups_listed(self) -> None:
        analysis = self._minimal_analysis(
            security_groups=("group_hr_manager",),
        )
        text = format_analysis_text(analysis)
        assert "Security Groups:" in text
        assert "group_hr_manager" in text

    def test_data_files_listed(self) -> None:
        analysis = self._minimal_analysis(
            data_files=("security/ir.model.access.csv",),
        )
        text = format_analysis_text(analysis)
        assert "Data Files:" in text
        assert "security/ir.model.access.csv" in text

    def test_flags_shown(self) -> None:
        analysis = self._minimal_analysis(
            has_wizards=True, has_tests=True
        )
        text = format_analysis_text(analysis)
        assert "Has: wizards, tests" in text

    def test_no_flags_when_false(self) -> None:
        text = format_analysis_text(self._minimal_analysis())
        assert "Has:" not in text

    def test_empty_manifest_fields_omitted(self) -> None:
        analysis = self._minimal_analysis(manifest={})
        text = format_analysis_text(analysis)
        assert "Display Name:" not in text
        assert "Version:" not in text
        assert "Category:" not in text

    def test_unknown_field_type_shows_question_mark(self) -> None:
        """Fields with no type mapping show '?' in output."""
        analysis = self._minimal_analysis(
            model_names=("test.model",),
            model_fields={"test.model": ("name",)},
            field_types={"test.model": {}},  # no type info for name
        )
        text = format_analysis_text(analysis)
        assert "name (?)" in text
