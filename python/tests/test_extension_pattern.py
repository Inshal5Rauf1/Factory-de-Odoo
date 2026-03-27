"""Tests for Module Extension Pattern (Phase 59).

Tests cover:
- Pydantic schema validation for extension specs
- Extension preprocessor (depends injection, normalization)
- Extension context builders (model + view)
- Template rendering (extension_model.py.j2, extension_views.xml.j2)
- Renderer integration (render_extensions stage)
- init_models.py.j2 with extension model imports
- Full render_module() pipeline with mixed spec
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def extension_spec() -> dict[str, Any]:
    """Load the full extension spec fixture (hr.employee extension + greenfield model)."""
    with open(FIXTURES_DIR / "extension_spec.json") as f:
        return json.load(f)


@pytest.fixture()
def extension_only_spec() -> dict[str, Any]:
    """Spec with only extensions, no greenfield models."""
    return {
        "module_name": "hr_academic",
        "depends": ["base"],
        "extends": [
            {
                "base_model": "hr.employee",
                "base_module": "hr",
                "add_fields": [
                    {"name": "faculty_id", "type": "Char", "string": "Faculty ID"},
                ],
                "add_computed": [],
                "add_constraints": [],
                "add_methods": [],
                "view_extensions": [],
            }
        ],
    }


# ===========================================================================
# Schema validation tests
# ===========================================================================


class TestExtensionSpecSchema:
    """Test Pydantic schema validates extension specs correctly."""

    def test_extension_spec_schema(self, extension_spec: dict[str, Any]) -> None:
        """ModuleSpec validates a spec dict containing 'extends' array."""
        from amil_utils.spec_schema import validate_spec

        result = validate_spec(extension_spec)
        assert len(result.extends) == 1
        ext = result.extends[0]
        assert ext.base_model == "hr.employee"
        assert ext.base_module == "hr"
        assert len(ext.add_fields) == 5
        assert len(ext.add_computed) == 1
        assert len(ext.add_constraints) == 1
        assert len(ext.add_methods) == 1
        assert len(ext.view_extensions) == 2
        # Coexistence with models
        assert len(result.models) == 1
        assert result.models[0].name == "uni.faculty.publication"

    def test_extension_spec_schema_mixed(self, extension_spec: dict[str, Any]) -> None:
        """Mixed spec (extends + models) validates without error."""
        from amil_utils.spec_schema import validate_spec

        result = validate_spec(extension_spec)
        assert result.extends  # has extensions
        assert result.models  # has greenfield models

    def test_extension_spec_schema_rejects_missing_base_model(self) -> None:
        """Missing base_model in extension raises ValidationError."""
        from amil_utils.spec_schema import ModuleSpec

        spec = {
            "module_name": "test_bad",
            "extends": [
                {
                    "base_module": "hr",
                    "add_fields": [],
                }
            ],
        }
        with pytest.raises(ValidationError):
            ModuleSpec(**spec)

    def test_extension_spec_schema_rejects_missing_base_module(self) -> None:
        """Missing base_module in extension raises ValidationError."""
        from amil_utils.spec_schema import ModuleSpec

        spec = {
            "module_name": "test_bad",
            "extends": [
                {
                    "base_model": "hr.employee",
                    "add_fields": [],
                }
            ],
        }
        with pytest.raises(ValidationError):
            ModuleSpec(**spec)

    def test_extension_spec_duplicate_base_model_rejected(self) -> None:
        """Duplicate base_model in extends list raises ValidationError."""
        from amil_utils.spec_schema import ModuleSpec

        spec = {
            "module_name": "test_dup",
            "extends": [
                {
                    "base_model": "hr.employee",
                    "base_module": "hr",
                    "add_fields": [{"name": "x", "type": "Char"}],
                },
                {
                    "base_model": "hr.employee",
                    "base_module": "hr",
                    "add_fields": [{"name": "y", "type": "Char"}],
                },
            ],
        }
        with pytest.raises(ValidationError, match="duplicate"):
            ModuleSpec(**spec)

    def test_extension_field_spec_types(self) -> None:
        """ExtensionFieldSpec accepts various field types."""
        from amil_utils.spec_schema import ExtensionFieldSpec

        char = ExtensionFieldSpec(name="test", type="Char")
        assert char.name == "test"

        sel = ExtensionFieldSpec(
            name="status", type="Selection",
            selection=[["a", "A"], ["b", "B"]],
        )
        assert len(sel.selection) == 2

        m2o = ExtensionFieldSpec(
            name="partner_id", type="Many2one", comodel="res.partner",
        )
        assert m2o.comodel == "res.partner"


# ===========================================================================
# Preprocessor tests
# ===========================================================================


class TestExtensionPreprocessor:
    """Test the extensions preprocessor."""

    def test_extension_preprocessor(self, extension_spec: dict[str, Any]) -> None:
        """Preprocessor sets has_extensions=True and normalizes entries."""
        from amil_utils.preprocessors.extensions import _process_extensions

        result = _process_extensions(extension_spec)
        assert result.get("has_extensions") is True
        assert "extension_model_files" in result

    def test_depends_injection(self, extension_spec: dict[str, Any]) -> None:
        """base_module auto-injected into depends list."""
        from amil_utils.preprocessors.extensions import _process_extensions

        # "hr" is not in the original depends (only "uni_core")
        assert "hr" not in extension_spec["depends"]
        result = _process_extensions(extension_spec)
        assert "hr" in result["depends"]

    def test_depends_no_duplicate(self) -> None:
        """If base_module already in depends, not duplicated."""
        from amil_utils.preprocessors.extensions import _process_extensions

        spec = {
            "module_name": "test_mod",
            "depends": ["hr", "base"],
            "extends": [
                {
                    "base_model": "hr.employee",
                    "base_module": "hr",
                    "add_fields": [{"name": "x", "type": "Char"}],
                    "add_computed": [],
                    "add_constraints": [],
                    "add_methods": [],
                    "view_extensions": [],
                }
            ],
        }
        result = _process_extensions(spec)
        assert result["depends"].count("hr") == 1

    def test_selection_values_normalized(self) -> None:
        """Preprocessor normalizes 'values' key to 'selection' for Selection fields."""
        from amil_utils.preprocessors.extensions import _process_extensions

        spec = {
            "module_name": "test_norm",
            "depends": ["base"],
            "extends": [
                {
                    "base_model": "hr.employee",
                    "base_module": "hr",
                    "add_fields": [
                        {
                            "name": "role",
                            "type": "Selection",
                            "values": [["a", "A"], ["b", "B"]],
                        }
                    ],
                    "add_computed": [],
                    "add_constraints": [],
                    "add_methods": [],
                    "view_extensions": [],
                }
            ],
        }
        result = _process_extensions(spec)
        ext = result["extends"][0]
        field = ext["add_fields"][0]
        assert "selection" in field
        assert field["selection"] == [["a", "A"], ["b", "B"]]

    def test_extension_model_files(self, extension_spec: dict[str, Any]) -> None:
        """Preprocessor builds extension_model_files list for init_models."""
        from amil_utils.preprocessors.extensions import _process_extensions

        result = _process_extensions(extension_spec)
        assert "hr_employee" in result["extension_model_files"]

    def test_no_extends_passthrough(self) -> None:
        """Spec without 'extends' key passes through unchanged."""
        from amil_utils.preprocessors.extensions import _process_extensions

        spec = {"module_name": "test", "depends": ["base"], "models": []}
        result = _process_extensions(spec)
        assert result.get("has_extensions") is not True
        assert "extension_model_files" not in result


# ===========================================================================
# Context builder tests
# ===========================================================================


class TestExtensionContextBuilder:
    """Test _build_extension_context and _build_extension_view_context."""

    def _get_preprocessed_spec(self, extension_spec: dict[str, Any]) -> dict[str, Any]:
        """Helper: run preprocessor on spec and return first extension."""
        from amil_utils.preprocessors.extensions import _process_extensions

        return _process_extensions(extension_spec)

    def test_extension_context_builder(self, extension_spec: dict[str, Any]) -> None:
        """_build_extension_context() returns correct dict."""
        from amil_utils.renderer_context import _build_extension_context

        spec = self._get_preprocessed_spec(extension_spec)
        ext = spec["extends"][0]
        ctx = _build_extension_context(spec, ext)

        assert ctx["base_model"] == "hr.employee"
        assert ctx["base_model_var"] == "hr_employee"
        assert ctx["class_name"] == "HrEmployee"
        assert ctx["module_name"] == "uni_student_hr"
        assert len(ctx["fields"]) == 5
        assert len(ctx["computed_fields"]) == 1
        assert len(ctx["sql_constraints"]) == 1
        assert len(ctx["methods"]) == 1
        assert ctx["needs_api"] is True

    def test_extension_view_context(self, extension_spec: dict[str, Any]) -> None:
        """_build_extension_view_context() returns correct dict for form view."""
        from amil_utils.renderer_context import _build_extension_view_context

        spec = self._get_preprocessed_spec(extension_spec)
        ext = spec["extends"][0]
        view_ext = ext["view_extensions"][0]
        ctx = _build_extension_view_context(spec, ext, view_ext)

        assert ctx["model_name"] == "hr.employee"
        assert ctx["inherit_id_ref"] == "hr.view_employee_form"
        assert "view_hr_employee_form_inherit_uni_student_hr" == ctx["view_record_id"]
        assert ctx["view_name"] == "hr.employee.form.inherit.uni_student_hr"
        assert len(ctx["insertions"]) == 1
        ins = ctx["insertions"][0]
        assert ins["xpath"] == "//page[@name='public']"
        assert ins["position"] == "after"
        assert ins["content"] == "page"

    def test_extension_view_context_tree(self, extension_spec: dict[str, Any]) -> None:
        """_build_extension_view_context() returns correct dict for tree view."""
        from amil_utils.renderer_context import _build_extension_view_context

        spec = self._get_preprocessed_spec(extension_spec)
        ext = spec["extends"][0]
        view_ext = ext["view_extensions"][1]  # tree view
        ctx = _build_extension_view_context(spec, ext, view_ext)

        assert "view_hr_employee_tree_inherit_uni_student_hr" == ctx["view_record_id"]
        assert ctx["inherit_id_ref"] == "hr.view_employee_tree"

    def test_mixed_module_context(self, extension_spec: dict[str, Any]) -> None:
        """_build_module_context() includes extension_model_files alongside models."""
        from amil_utils.renderer_context import _build_module_context

        spec = self._get_preprocessed_spec(extension_spec)
        ctx = _build_module_context(spec, spec["module_name"])

        assert "extension_model_files" in ctx
        assert "hr_employee" in ctx["extension_model_files"]
        assert ctx["has_extensions"] is True
        # Greenfield models are also present
        assert len(ctx["models"]) >= 1


# ===========================================================================
# Template rendering tests (Task 2)
# ===========================================================================


class TestExtensionModelRender:
    """Test extension_model.py.j2 template rendering."""

    def _render_extension_model(self, extension_spec: dict[str, Any]) -> str:
        """Helper: preprocess, build context, render extension model template."""
        from amil_utils.preprocessors.extensions import _process_extensions
        from amil_utils.renderer import create_versioned_renderer
        from amil_utils.renderer_context import _build_extension_context

        spec = _process_extensions(extension_spec)
        ext = spec["extends"][0]
        ctx = _build_extension_context(spec, ext)
        env = create_versioned_renderer("17.0")
        template = env.get_template("extension_model.py.j2")
        return template.render(**ctx)

    def test_extension_model_render(self, extension_spec: dict[str, Any]) -> None:
        """Rendered .py file contains _inherit, fields, computed, constraints."""
        content = self._render_extension_model(extension_spec)

        assert "_inherit = 'hr.employee'" in content
        # Extension models don't define _name (check no standalone _name = assignment)
        assert "\n    _name = " not in content
        assert "faculty_id" in content
        assert "designation" in content
        assert "Selection" in content
        assert "course_ids" in content
        assert "Many2many" in content
        assert "current_course_count" in content
        assert "UNIQUE(faculty_id)" in content or "UNIQUE" in content

    def test_extension_super_pattern(self, extension_spec: dict[str, Any]) -> None:
        """Extension methods do NOT auto-include super() call."""
        content = self._render_extension_model(extension_spec)
        # Methods in add_methods are new additions, not overrides
        assert "super()" not in content

    def test_extension_logic_markers(self, extension_spec: dict[str, Any]) -> None:
        """Each method has BUSINESS LOGIC START/END markers."""
        content = self._render_extension_model(extension_spec)
        assert "# --- BUSINESS LOGIC START ---" in content
        assert "# --- BUSINESS LOGIC END ---" in content

    def test_extension_model_imports(self, extension_spec: dict[str, Any]) -> None:
        """Extension model imports api when computed/methods present."""
        content = self._render_extension_model(extension_spec)
        assert "from odoo import api, fields, models" in content

    def test_extension_model_no_api_when_not_needed(self) -> None:
        """Extension model omits api import when no computed/methods."""
        from amil_utils.preprocessors.extensions import _process_extensions
        from amil_utils.renderer import create_versioned_renderer
        from amil_utils.renderer_context import _build_extension_context

        spec = {
            "module_name": "simple_ext",
            "depends": ["base"],
            "extends": [{
                "base_model": "res.partner",
                "base_module": "base",
                "add_fields": [{"name": "nickname", "type": "Char"}],
                "add_computed": [],
                "add_constraints": [],
                "add_methods": [],
                "view_extensions": [],
            }],
        }
        spec = _process_extensions(spec)
        ext = spec["extends"][0]
        ctx = _build_extension_context(spec, ext)
        env = create_versioned_renderer("17.0")
        template = env.get_template("extension_model.py.j2")
        content = template.render(**ctx)

        assert "from odoo import fields, models" in content
        assert "api" not in content.split("from odoo import")[1].split("\n")[0]


class TestExtensionViewRender:
    """Test extension_views.xml.j2 template rendering."""

    def _render_extension_views(
        self, extension_spec: dict[str, Any], view_index: int = 0
    ) -> str:
        """Helper: preprocess, build context, render extension view template."""
        from amil_utils.preprocessors.extensions import _process_extensions
        from amil_utils.renderer import create_versioned_renderer
        from amil_utils.renderer_context import _build_extension_view_context

        spec = _process_extensions(extension_spec)
        ext = spec["extends"][0]
        views = []
        for ve in ext["view_extensions"]:
            ctx = _build_extension_view_context(spec, ext, ve)
            views.append(ctx)

        env = create_versioned_renderer("17.0")
        template = env.get_template("extension_views.xml.j2")
        return template.render(views=views)

    def test_xpath_pattern_a(self, extension_spec: dict[str, Any]) -> None:
        """Pattern A: field after existing field in tree view."""
        content = self._render_extension_views(extension_spec)
        # Tree view has Pattern A: after department_id
        assert '//field[@name=\'department_id\']' in content
        assert 'position="after"' in content
        assert '<field name="designation"/>' in content
        assert '<field name="faculty_id"/>' in content

    def test_xpath_pattern_b(self, extension_spec: dict[str, Any]) -> None:
        """Pattern B: new page with fields (form view)."""
        content = self._render_extension_views(extension_spec)
        assert '<page string="Academic Info" name="academic">' in content
        # 6 fields -> should trigger two-column layout
        assert "<group>" in content

    def test_xpath_pattern_c(self) -> None:
        """Pattern C: inside existing group."""
        from amil_utils.preprocessors.extensions import _process_extensions
        from amil_utils.renderer import create_versioned_renderer
        from amil_utils.renderer_context import _build_extension_view_context

        spec = {
            "module_name": "test_c",
            "depends": ["base"],
            "extends": [{
                "base_model": "hr.employee",
                "base_module": "hr",
                "add_fields": [{"name": "x", "type": "Char"}],
                "add_computed": [],
                "add_constraints": [],
                "add_methods": [],
                "view_extensions": [{
                    "base_view": "hr.view_employee_form",
                    "insertions": [{
                        "xpath": "//group[@name='hr_settings']",
                        "position": "inside",
                        "fields": ["x"],
                    }],
                }],
            }],
        }
        spec = _process_extensions(spec)
        ext = spec["extends"][0]
        ve = ext["view_extensions"][0]
        ctx = _build_extension_view_context(spec, ext, ve)

        env = create_versioned_renderer("17.0")
        template = env.get_template("extension_views.xml.j2")
        content = template.render(views=[ctx])

        assert "//group[@name='hr_settings']" in content
        assert 'position="inside"' in content
        assert '<field name="x"/>' in content

    def test_inherit_id_ref(self, extension_spec: dict[str, Any]) -> None:
        """View record has correct inherit_id ref."""
        content = self._render_extension_views(extension_spec)
        assert 'ref="hr.view_employee_form"' in content

    def test_view_xml_id(self, extension_spec: dict[str, Any]) -> None:
        """Record id follows format view_{base_model}_{view_type}_inherit_{module}."""
        content = self._render_extension_views(extension_spec)
        assert 'id="view_hr_employee_form_inherit_uni_student_hr"' in content
        assert 'id="view_hr_employee_tree_inherit_uni_student_hr"' in content


class TestInitModelsImports:
    """Test updated init_models.py.j2 generates extension imports."""

    def test_init_models_imports(self, extension_spec: dict[str, Any]) -> None:
        """init_models.py.j2 generates imports for both greenfield and extension models."""
        from amil_utils.preprocessors.extensions import _process_extensions
        from amil_utils.renderer import create_versioned_renderer
        from amil_utils.renderer_context import _build_module_context

        spec = _process_extensions(extension_spec)
        ctx = _build_module_context(spec, spec["module_name"])

        env = create_versioned_renderer("17.0")
        template = env.get_template("init_models.py.j2")
        content = template.render(**ctx)

        # Greenfield model
        assert "from . import uni_faculty_publication" in content
        # Extension model
        assert "from . import hr_employee" in content


class TestRendererIntegration:
    """Test render_extensions() stage and full render_module() pipeline."""

    def test_render_extensions_function(self, extension_spec: dict[str, Any]) -> None:
        """render_extensions() creates extension model and view files."""
        from amil_utils.preprocessors.extensions import _process_extensions
        from amil_utils.renderer import create_versioned_renderer, render_extensions
        from amil_utils.renderer_context import _build_module_context

        spec = _process_extensions(extension_spec)
        env = create_versioned_renderer("17.0")
        ctx = _build_module_context(spec, spec["module_name"])

        with tempfile.TemporaryDirectory() as tmpdir:
            module_dir = Path(tmpdir) / spec["module_name"]
            module_dir.mkdir()

            result = render_extensions(env, spec, module_dir, ctx)
            assert result.success
            assert result.data  # non-empty file list

            # Check extension model file
            ext_model = module_dir / "models" / "hr_employee.py"
            assert ext_model.exists()
            content = ext_model.read_text()
            assert "_inherit = 'hr.employee'" in content

            # Check extension view file
            ext_view = module_dir / "views" / "hr_employee_views.xml"
            assert ext_view.exists()
            view_content = ext_view.read_text()
            assert "xpath" in view_content
            assert "inherit_id" in view_content

    def test_full_extension_render(self, extension_spec: dict[str, Any]) -> None:
        """Full render_module() produces extension + greenfield files."""
        from amil_utils.renderer import get_template_dir, render_module

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            template_dir = get_template_dir()

            created, warnings = render_module(
                extension_spec, template_dir, output_dir, no_context7=True,
            )
            module_dir = output_dir / extension_spec["module_name"]

            # Extension model
            ext_model = module_dir / "models" / "hr_employee.py"
            assert ext_model.exists(), f"Expected {ext_model}"
            assert "_inherit" in ext_model.read_text()

            # Extension view
            ext_view = module_dir / "views" / "hr_employee_views.xml"
            assert ext_view.exists(), f"Expected {ext_view}"

            # Greenfield model
            gf_model = module_dir / "models" / "uni_faculty_publication.py"
            assert gf_model.exists(), f"Expected {gf_model}"

            # Manifest has "hr" in depends
            manifest = module_dir / "__manifest__.py"
            assert manifest.exists()
            manifest_content = manifest.read_text()
            assert '"hr"' in manifest_content

            # init_models has both imports
            init = module_dir / "models" / "__init__.py"
            init_content = init.read_text()
            assert "hr_employee" in init_content
            assert "uni_faculty_publication" in init_content

    def test_mixed_spec(self, extension_spec: dict[str, Any]) -> None:
        """render_module() with both extends and models produces all files."""
        from amil_utils.renderer import get_template_dir, render_module

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            template_dir = get_template_dir()

            created, warnings = render_module(
                extension_spec, template_dir, output_dir, no_context7=True,
            )

            module_dir = output_dir / extension_spec["module_name"]
            assert module_dir.exists()

            # Count created files: should include extension + greenfield
            py_files = list(module_dir.rglob("*.py"))
            xml_files = list(module_dir.rglob("*.xml"))
            assert len(py_files) >= 4  # manifest, init_root, init_models, model, ext_model, tests
            assert len(xml_files) >= 3  # views, actions, menu, ext_views

    def test_extensions_stage_in_pipeline(self) -> None:
        """'extensions' is in STAGE_NAMES."""
        from amil_utils.renderer import STAGE_NAMES

        assert "extensions" in STAGE_NAMES


class TestExtensionSemanticValidation:
    """Test that generated extension modules pass semantic_validate() cleanly."""

    def test_full_extension_semantic_validate(self, extension_spec: dict[str, Any]) -> None:
        """Generated extension module passes full semantic_validate() with zero issues.

        Proves that E1-E17 and W1-W6 produce no false positives on properly
        generated extension output.
        """
        from amil_utils.renderer import get_template_dir, render_module
        from amil_utils.validation.semantic import semantic_validate

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            template_dir = get_template_dir()

            created, warnings = render_module(
                extension_spec, template_dir, output_dir, no_context7=True,
            )
            module_dir = output_dir / extension_spec["module_name"]
            assert module_dir.exists()

            result = semantic_validate(module_dir)
            assert result.errors == [], (
                f"Extension module produced errors: "
                f"{[(e.code, e.message) for e in result.errors]}"
            )
            assert result.warnings == [], (
                f"Extension module produced warnings: "
                f"{[(w.code, w.message) for w in result.warnings]}"
            )
