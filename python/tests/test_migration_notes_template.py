"""Tests for MIGRATION_NOTES.md.j2 template rendering.

Verifies that the migration notes template:
- Loads and renders without errors via Jinja2
- Includes version-specific patterns for Odoo < 18.0 (name_get, tree tag, attrs)
- Includes version-specific patterns for Odoo < 19.0 (_sql_constraints, category_id)
- Produces minimal output (no version-specific sections) for Odoo 19.0
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import FileSystemLoader, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment as Environment


SHARED_TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "amil_utils"
    / "templates"
    / "shared"
)

TEMPLATE_NAME = "MIGRATION_NOTES.md.j2"


@pytest.fixture()
def jinja_env() -> Environment:
    """Create a Jinja2 environment pointing at the shared templates directory."""
    return Environment(
        loader=FileSystemLoader(str(SHARED_TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _render(env: Environment, module_name: str, odoo_version: str) -> str:
    """Render the migration notes template with the given context."""
    template = env.get_template(TEMPLATE_NAME)
    return template.render(module_name=module_name, odoo_version=odoo_version)


# ---------------------------------------------------------------------------
# Template existence
# ---------------------------------------------------------------------------


class TestMigrationNotesTemplateExists:
    def test_template_file_exists(self):
        path = SHARED_TEMPLATES_DIR / TEMPLATE_NAME
        assert path.exists(), f"Template not found: {path}"

    def test_template_loadable(self, jinja_env: Environment):
        template = jinja_env.get_template(TEMPLATE_NAME)
        assert template is not None


# ---------------------------------------------------------------------------
# Odoo 17.0 — should include both <18.0 and <19.0 sections
# ---------------------------------------------------------------------------


class TestMigrationNotesOdoo17:
    def test_renders_without_error(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert len(output) > 0

    def test_contains_module_name(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "test_module" in output

    def test_contains_odoo_version(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "17.0" in output

    def test_contains_name_get_deprecation(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "name_get" in output

    def test_contains_tree_tag_deprecation(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "<tree>" in output
        assert "<list>" in output

    def test_contains_attrs_deprecation(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "attrs" in output

    def test_contains_sql_constraints_deprecation(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "_sql_constraints" in output

    def test_contains_category_id_deprecation(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "category_id" in output
        assert "privilege_id" in output

    def test_contains_expression_or_deprecation(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "expression.OR()" in output
        assert "Domain" in output

    def test_contains_how_to_migrate_section(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "## How to Migrate" in output

    def test_contains_18_to_section_header(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "17.0" in output
        assert "18.0" in output

    def test_contains_19_to_section_header(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "17.0")
        assert "19.0" in output


# ---------------------------------------------------------------------------
# Odoo 18.0 — should include only <19.0 section (not <18.0)
# ---------------------------------------------------------------------------


class TestMigrationNotesOdoo18:
    def test_renders_without_error(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "18.0")
        assert len(output) > 0

    def test_excludes_name_get_section(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "18.0")
        assert "name_get" not in output

    def test_excludes_tree_tag_section(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "18.0")
        assert "<tree>" not in output

    def test_excludes_attrs_section(self, jinja_env: Environment):
        """The attrs deprecation block is in the <18.0 section only."""
        output = _render(jinja_env, "test_module", "18.0")
        assert "attrs" not in output

    def test_contains_sql_constraints_deprecation(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "18.0")
        assert "_sql_constraints" in output

    def test_contains_category_id_deprecation(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "18.0")
        assert "category_id" in output

    def test_contains_how_to_migrate(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "18.0")
        assert "## How to Migrate" in output


# ---------------------------------------------------------------------------
# Odoo 19.0 — minimal output, no version-specific patterns
# ---------------------------------------------------------------------------


class TestMigrationNotesOdoo19:
    def test_renders_without_error(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "19.0")
        assert len(output) > 0

    def test_contains_module_name(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "19.0")
        assert "test_module" in output

    def test_excludes_name_get(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "19.0")
        assert "name_get" not in output

    def test_excludes_sql_constraints(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "19.0")
        assert "_sql_constraints" not in output

    def test_excludes_category_id(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "19.0")
        assert "category_id" not in output

    def test_excludes_attrs(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "19.0")
        assert "attrs" not in output

    def test_contains_how_to_migrate(self, jinja_env: Environment):
        output = _render(jinja_env, "test_module", "19.0")
        assert "## How to Migrate" in output

    def test_minimal_output_no_version_sections(self, jinja_env: Environment):
        """For 19.0, there should be no version-specific upgrade sections."""
        output = _render(jinja_env, "test_module", "19.0")
        assert "expression.OR()" not in output
        assert "privilege_id" not in output
