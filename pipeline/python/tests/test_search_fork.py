"""Tests for fork clone, module analyzer, and companion directory setup.

Covers:
- clone_oca_module(): git sparse checkout with correct args, branch support, error propagation
- analyze_module(): AST-based model/field extraction, XML view parsing, security groups, manifest
- setup_companion_dir(): _ext directory structure creation
- ModuleAnalysis: frozen dataclass with all required fields
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from odoo_gen_utils.search.analyzer import ModuleAnalysis, analyze_module, format_analysis_text
from odoo_gen_utils.search.fork import clone_oca_module, setup_companion_dir


# ---------------------------------------------------------------------------
# clone_oca_module tests
# ---------------------------------------------------------------------------


class TestCloneOcaModule:
    """Tests for clone_oca_module() git sparse checkout."""

    @patch("odoo_gen_utils.search.fork.subprocess.run")
    def test_clone_calls_git_with_sparse_checkout_args(
        self, mock_run: object, tmp_path: Path
    ) -> None:
        """clone_oca_module() calls git with correct sparse-checkout args."""
        result = clone_oca_module("sale-workflow", "sale_order_type", tmp_path)

        calls = mock_run.call_args_list  # type: ignore[union-attr]
        assert len(calls) == 3

        # First call: git clone --no-checkout --filter=blob:none --sparse -b 19.0
        clone_args = calls[0][0][0]
        assert "clone" in clone_args
        assert "--no-checkout" in clone_args
        assert "--filter=blob:none" in clone_args
        assert "--sparse" in clone_args
        assert "-b" in clone_args
        assert "19.0" in clone_args
        assert "https://github.com/OCA/sale-workflow.git" in clone_args

        # Second call: git sparse-checkout set {module_name}
        sparse_args = calls[1][0][0]
        assert "sparse-checkout" in sparse_args
        assert "set" in sparse_args
        assert "sale_order_type" in sparse_args

        # Third call: git checkout {branch}
        checkout_args = calls[2][0][0]
        assert "checkout" in checkout_args
        assert "19.0" in checkout_args

    @patch("odoo_gen_utils.search.fork.subprocess.run")
    def test_clone_returns_module_path(
        self, mock_run: object, tmp_path: Path
    ) -> None:
        """clone_oca_module() returns Path to the cloned module directory."""
        result = clone_oca_module("sale-workflow", "sale_order_type", tmp_path)

        expected = tmp_path / "oca_sale-workflow" / "sale_order_type"
        assert result == expected

    @patch("odoo_gen_utils.search.fork.subprocess.run")
    def test_clone_with_custom_branch(
        self, mock_run: object, tmp_path: Path
    ) -> None:
        """clone_oca_module() with branch='16.0' passes -b 16.0 to git clone."""
        clone_oca_module("sale-workflow", "sale_order_type", tmp_path, branch="16.0")

        calls = mock_run.call_args_list  # type: ignore[union-attr]
        clone_args = calls[0][0][0]
        assert "-b" in clone_args
        idx = clone_args.index("-b")
        assert clone_args[idx + 1] == "16.0"

        # Checkout should also use 16.0
        checkout_args = calls[2][0][0]
        assert "16.0" in checkout_args

    @patch("odoo_gen_utils.search.fork.subprocess.run")
    def test_clone_raises_called_process_error_on_git_failure(
        self, mock_run: object, tmp_path: Path
    ) -> None:
        """clone_oca_module() raises subprocess.CalledProcessError when git fails."""
        mock_run.side_effect = subprocess.CalledProcessError(  # type: ignore[union-attr]
            returncode=128, cmd=["git", "clone"]
        )

        with pytest.raises(subprocess.CalledProcessError):
            clone_oca_module("sale-workflow", "sale_order_type", tmp_path)

    @patch("odoo_gen_utils.search.fork.subprocess.run")
    def test_clone_uses_check_true(
        self, mock_run: object, tmp_path: Path
    ) -> None:
        """clone_oca_module() passes check=True to subprocess.run."""
        clone_oca_module("sale-workflow", "sale_order_type", tmp_path)

        calls = mock_run.call_args_list  # type: ignore[union-attr]
        for call in calls:
            assert call[1].get("check") is True or (
                len(call[0]) > 1 and call[0][1] is True
            ), f"check=True not passed in call: {call}"


# ---------------------------------------------------------------------------
# analyze_module tests
# ---------------------------------------------------------------------------


class TestAnalyzeModule:
    """Tests for analyze_module() structure analysis."""

    def _create_module(self, tmp_path: Path) -> Path:
        """Create a minimal Odoo module for testing."""
        mod = tmp_path / "test_module"
        mod.mkdir()

        # __manifest__.py
        (mod / "__manifest__.py").write_text(textwrap.dedent("""\
            {
                'name': 'Test Module',
                'version': '17.0.1.0.0',
                'category': 'Sales',
                'depends': ['base', 'sale'],
                'data': [
                    'security/security.xml',
                    'security/ir.model.access.csv',
                    'views/test_model_views.xml',
                ],
                'installable': True,
                'license': 'LGPL-3',
            }
        """))

        # models/
        models_dir = mod / "models"
        models_dir.mkdir()
        (models_dir / "__init__.py").write_text("from . import test_model\n")
        (models_dir / "test_model.py").write_text(textwrap.dedent("""\
            from odoo import api, fields, models


            class TestModel(models.Model):
                _name = 'test.model'
                _description = 'Test Model'

                name = fields.Char(string='Name', required=True)
                code = fields.Char(string='Code')
                quantity = fields.Integer(string='Quantity')
                partner_id = fields.Many2one('res.partner', string='Partner')
                active = fields.Boolean(default=True)
        """))

        # views/
        views_dir = mod / "views"
        views_dir.mkdir()
        (views_dir / "test_model_views.xml").write_text(textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="test_model_view_form" model="ir.ui.view">
                    <field name="name">test.model.form</field>
                    <field name="model">test.model</field>
                    <field name="arch" type="xml">
                        <form>
                            <field name="name"/>
                            <field name="code"/>
                        </form>
                    </field>
                </record>
                <record id="test_model_view_tree" model="ir.ui.view">
                    <field name="name">test.model.tree</field>
                    <field name="model">test.model</field>
                    <field name="arch" type="xml">
                        <tree>
                            <field name="name"/>
                        </tree>
                    </field>
                </record>
                <record id="test_model_view_search" model="ir.ui.view">
                    <field name="name">test.model.search</field>
                    <field name="model">test.model</field>
                    <field name="arch" type="xml">
                        <search>
                            <field name="name"/>
                        </search>
                    </field>
                </record>
            </odoo>
        """))

        # security/
        security_dir = mod / "security"
        security_dir.mkdir()
        (security_dir / "security.xml").write_text(textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="group_test_user" model="ir.module.category">
                    <field name="name">Test</field>
                </record>
                <record id="group_test_manager" model="res.groups">
                    <field name="name">Manager</field>
                </record>
            </odoo>
        """))
        (security_dir / "ir.model.access.csv").write_text(
            "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"
            "access_test_model_user,test.model.user,model_test_model,group_test_user,1,1,1,0\n"
        )

        return mod

    def test_analyze_extracts_model_names(self, tmp_path: Path) -> None:
        """analyze_module() extracts model _name values from models/*.py."""
        mod = self._create_module(tmp_path)
        analysis = analyze_module(mod)

        assert "test.model" in analysis.model_names

    def test_analyze_extracts_field_names(self, tmp_path: Path) -> None:
        """analyze_module() extracts field names from model classes."""
        mod = self._create_module(tmp_path)
        analysis = analyze_module(mod)

        assert "test.model" in analysis.model_fields
        field_names = analysis.model_fields["test.model"]
        assert "name" in field_names
        assert "code" in field_names
        assert "quantity" in field_names
        assert "partner_id" in field_names
        assert "active" in field_names

    def test_analyze_extracts_field_types(self, tmp_path: Path) -> None:
        """analyze_module() extracts field types from model classes."""
        mod = self._create_module(tmp_path)
        analysis = analyze_module(mod)

        assert "test.model" in analysis.field_types
        types = analysis.field_types["test.model"]
        assert types["name"] == "Char"
        assert types["quantity"] == "Integer"
        assert types["partner_id"] == "Many2one"
        assert types["active"] == "Boolean"

    def test_analyze_detects_view_types(self, tmp_path: Path) -> None:
        """analyze_module() detects view types from views/*.xml."""
        mod = self._create_module(tmp_path)
        analysis = analyze_module(mod)

        assert "test.model" in analysis.view_types
        view_types = analysis.view_types["test.model"]
        assert "form" in view_types
        assert "tree" in view_types
        assert "search" in view_types

    def test_analyze_reads_security_groups(self, tmp_path: Path) -> None:
        """analyze_module() reads security groups from security/security.xml."""
        mod = self._create_module(tmp_path)
        analysis = analyze_module(mod)

        assert len(analysis.security_groups) >= 1
        # Should contain the group XML IDs
        assert any("group_test" in g for g in analysis.security_groups)

    def test_analyze_reads_data_files(self, tmp_path: Path) -> None:
        """analyze_module() reads data files list from __manifest__.py."""
        mod = self._create_module(tmp_path)
        analysis = analyze_module(mod)

        assert "security/security.xml" in analysis.data_files
        assert "views/test_model_views.xml" in analysis.data_files

    def test_analyze_detects_wizards(self, tmp_path: Path) -> None:
        """analyze_module() returns has_wizards=True when wizards/ exists."""
        mod = self._create_module(tmp_path)
        (mod / "wizards").mkdir()
        (mod / "wizards" / "__init__.py").write_text("")

        analysis = analyze_module(mod)
        assert analysis.has_wizards is True

    def test_analyze_no_wizards(self, tmp_path: Path) -> None:
        """analyze_module() returns has_wizards=False when wizards/ absent."""
        mod = self._create_module(tmp_path)
        analysis = analyze_module(mod)
        assert analysis.has_wizards is False

    def test_analyze_detects_tests(self, tmp_path: Path) -> None:
        """analyze_module() returns has_tests=True when tests/ exists."""
        mod = self._create_module(tmp_path)
        (mod / "tests").mkdir()
        (mod / "tests" / "__init__.py").write_text("")

        analysis = analyze_module(mod)
        assert analysis.has_tests is True

    def test_analyze_no_tests(self, tmp_path: Path) -> None:
        """analyze_module() returns has_tests=False when tests/ absent."""
        mod = self._create_module(tmp_path)
        analysis = analyze_module(mod)
        assert analysis.has_tests is False

    def test_analyze_detects_inherit_only_models(self, tmp_path: Path) -> None:
        """analyze_module() detects _inherit-only model extensions."""
        mod = self._create_module(tmp_path)
        models_dir = mod / "models"
        (models_dir / "res_partner.py").write_text(textwrap.dedent("""\
            from odoo import fields, models


            class ResPartnerExt(models.Model):
                _inherit = 'res.partner'

                custom_field = fields.Char(string='Custom')
        """))

        analysis = analyze_module(mod)
        assert "res.partner" in analysis.inherited_models

    def test_analyze_detects_inherit_list(self, tmp_path: Path) -> None:
        """analyze_module() detects _inherit as a list of model names."""
        mod = self._create_module(tmp_path)
        models_dir = mod / "models"
        (models_dir / "mail_mixin.py").write_text(textwrap.dedent("""\
            from odoo import models


            class MailMixin(models.Model):
                _inherit = ['mail.thread', 'mail.activity.mixin']
        """))

        analysis = analyze_module(mod)
        assert "mail.thread" in analysis.inherited_models
        assert "mail.activity.mixin" in analysis.inherited_models

    def test_analyze_ignores_named_inherit(self, tmp_path: Path) -> None:
        """analyze_module() does NOT put models with _name and _inherit in inherited_models."""
        mod = self._create_module(tmp_path)
        models_dir = mod / "models"
        (models_dir / "custom_model.py").write_text(textwrap.dedent("""\
            from odoo import fields, models


            class CustomModel(models.Model):
                _name = 'custom.model'
                _inherit = 'sale.order'

                extra_field = fields.Char()
        """))

        analysis = analyze_module(mod)
        # sale.order should NOT be in inherited_models (it's a new model with _name)
        assert "sale.order" not in analysis.inherited_models
        # custom.model should be in model_names
        assert "custom.model" in analysis.model_names


# ---------------------------------------------------------------------------
# setup_companion_dir tests
# ---------------------------------------------------------------------------


class TestSetupCompanionDir:
    """Tests for setup_companion_dir() companion module creation."""

    def test_creates_ext_directory(self, tmp_path: Path) -> None:
        """setup_companion_dir() creates {module}_ext directory."""
        original = tmp_path / "sale_order_type"
        original.mkdir()

        result = setup_companion_dir(original)

        expected = tmp_path / "sale_order_type_ext"
        assert result == expected
        assert result.is_dir()

    def test_creates_subdirectories(self, tmp_path: Path) -> None:
        """setup_companion_dir() creates models/, views/, security/, tests/ subdirs."""
        original = tmp_path / "sale_order_type"
        original.mkdir()

        result = setup_companion_dir(original)

        assert (result / "models").is_dir()
        assert (result / "views").is_dir()
        assert (result / "security").is_dir()
        assert (result / "tests").is_dir()

    def test_custom_ext_name(self, tmp_path: Path) -> None:
        """setup_companion_dir() uses custom ext_module_name if provided."""
        original = tmp_path / "sale_order_type"
        original.mkdir()

        result = setup_companion_dir(original, ext_module_name="my_custom_ext")

        expected = tmp_path / "my_custom_ext"
        assert result == expected
        assert result.is_dir()


# ---------------------------------------------------------------------------
# ModuleAnalysis dataclass tests
# ---------------------------------------------------------------------------


class TestModuleAnalysis:
    """Tests for ModuleAnalysis frozen dataclass."""

    def test_frozen_dataclass(self) -> None:
        """ModuleAnalysis is a frozen dataclass (immutable)."""
        analysis = ModuleAnalysis(
            module_name="test_module",
            manifest={"name": "Test"},
            model_names=("test.model",),
            model_fields={"test.model": ("name", "code")},
            field_types={"test.model": {"name": "Char", "code": "Char"}},
            view_types={"test.model": ("form", "tree")},
            security_groups=("group_test_user",),
            data_files=("views/test_views.xml",),
            has_wizards=False,
            has_tests=True,
        )

        with pytest.raises(AttributeError):
            analysis.module_name = "changed"  # type: ignore[misc]

    def test_has_all_fields(self) -> None:
        """ModuleAnalysis has all required fields."""
        analysis = ModuleAnalysis(
            module_name="test_module",
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

        assert hasattr(analysis, "module_name")
        assert hasattr(analysis, "manifest")
        assert hasattr(analysis, "model_names")
        assert hasattr(analysis, "model_fields")
        assert hasattr(analysis, "field_types")
        assert hasattr(analysis, "view_types")
        assert hasattr(analysis, "security_groups")
        assert hasattr(analysis, "data_files")
        assert hasattr(analysis, "has_wizards")
        assert hasattr(analysis, "has_tests")

    def test_inherited_models_default_empty(self) -> None:
        """ModuleAnalysis.inherited_models defaults to empty tuple."""
        analysis = ModuleAnalysis(
            module_name="test_module",
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
# format_analysis_text tests
# ---------------------------------------------------------------------------


class TestFormatAnalysisText:
    """Tests for format_analysis_text() human-readable output."""

    def test_includes_module_name(self) -> None:
        """format_analysis_text() includes module name in output."""
        analysis = ModuleAnalysis(
            module_name="sale_order_type",
            manifest={"name": "Sale Order Type"},
            model_names=("sale.order.type",),
            model_fields={"sale.order.type": ("name",)},
            field_types={"sale.order.type": {"name": "Char"}},
            view_types={"sale.order.type": ("form",)},
            security_groups=(),
            data_files=(),
            has_wizards=False,
            has_tests=True,
        )

        text = format_analysis_text(analysis)
        assert "sale_order_type" in text
        assert "sale.order.type" in text

    def test_includes_inherited_models(self) -> None:
        """format_analysis_text() includes inherited models when present."""
        analysis = ModuleAnalysis(
            module_name="sale_ext",
            manifest={"name": "Sale Extension"},
            model_names=(),
            model_fields={},
            field_types={},
            view_types={},
            security_groups=(),
            data_files=(),
            has_wizards=False,
            has_tests=False,
            inherited_models=("res.partner", "sale.order"),
        )

        text = format_analysis_text(analysis)
        assert "Inherited Models" in text
        assert "res.partner" in text
        assert "sale.order" in text
