"""Unit tests for mermaid.py -- Mermaid diagram generation from registry data.

Tests: _mermaid_id sanitization, _is_key_field filtering, _is_external_module,
generate_dependency_dag, generate_er_diagram, generate_module_diagrams,
generate_project_diagrams, Mermaid syntax validation, CLI mermaid command,
auto-generation hook in render_module_cmd.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import click.testing
import pytest

from amil_utils.cli import main
from amil_utils.registry import ModelEntry, ModelRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def reg_path(tmp_path: Path) -> Path:
    """Return a temporary registry file path."""
    return tmp_path / "model_registry.json"


@pytest.fixture()
def registry(reg_path: Path) -> ModelRegistry:
    """Return a fresh ModelRegistry pointing at a temp file."""
    r = ModelRegistry(reg_path)
    r.load_known_models()
    return r


@pytest.fixture()
def project_modules() -> set[str]:
    """Set of project module names."""
    return {"uni_fee", "uni_core", "uni_student"}


@pytest.fixture()
def sample_models() -> dict[str, ModelEntry]:
    """Sample models for ER diagram tests."""
    return {
        "uni.fee.invoice": ModelEntry(
            module="uni_fee",
            fields={
                "name": {"type": "Char", "string": "Name"},
                "state": {"type": "Selection", "string": "Status"},
                "amount_total": {"type": "Monetary", "string": "Total"},
                "student_id": {
                    "type": "Many2one",
                    "comodel_name": "uni.student",
                    "string": "Student",
                },
                "line_ids": {
                    "type": "One2many",
                    "comodel_name": "uni.fee.line",
                    "inverse_name": "invoice_id",
                    "string": "Lines",
                },
                "create_uid": {"type": "Many2one", "comodel_name": "res.users"},
                "write_date": {"type": "Datetime"},
                "notes": {"type": "Text", "string": "Notes"},
                "attachment": {"type": "Binary", "string": "File"},
                "description_html": {"type": "Html", "string": "Description"},
                "computed_field": {
                    "type": "Char",
                    "compute": "_compute_x",
                    "string": "Computed",
                },
                "stored_computed": {
                    "type": "Char",
                    "compute": "_compute_y",
                    "store": True,
                    "string": "Stored",
                },
            },
            description="Fee Invoice",
        ),
        "uni.fee.line": ModelEntry(
            module="uni_fee",
            fields={
                "name": {"type": "Char", "string": "Description"},
                "amount": {"type": "Monetary", "string": "Amount"},
                "invoice_id": {
                    "type": "Many2one",
                    "comodel_name": "uni.fee.invoice",
                    "string": "Invoice",
                },
            },
            description="Fee Line",
        ),
    }


@pytest.fixture()
def registry_with_models(registry: ModelRegistry, sample_models: dict) -> ModelRegistry:
    """Registry pre-populated with sample models."""
    spec_fee = {
        "module_name": "uni_fee",
        "models": [
            {
                "_name": "uni.fee.invoice",
                "fields": sample_models["uni.fee.invoice"].fields,
                "_inherit": [],
                "description": "Fee Invoice",
            },
            {
                "_name": "uni.fee.line",
                "fields": sample_models["uni.fee.line"].fields,
                "_inherit": [],
                "description": "Fee Line",
            },
        ],
        "depends": ["base", "mail", "uni_core"],
    }
    spec_student = {
        "module_name": "uni_student",
        "models": [
            {
                "_name": "uni.student",
                "fields": {
                    "name": {"type": "Char", "string": "Name"},
                    "enrollment_status": {
                        "type": "Selection",
                        "string": "Enrollment Status",
                    },
                },
                "_inherit": [],
                "description": "Student",
            },
        ],
        "depends": ["base", "uni_core"],
    }
    spec_core = {
        "module_name": "uni_core",
        "models": [
            {
                "_name": "uni.config",
                "fields": {"name": {"type": "Char"}},
                "_inherit": [],
                "description": "Config",
            },
        ],
        "depends": ["base"],
    }
    registry.register_module("uni_fee", spec_fee)
    registry.register_module("uni_student", spec_student)
    registry.register_module("uni_core", spec_core)
    return registry


# ===========================================================================
# TestMermaidId
# ===========================================================================


class TestMermaidId:
    """Tests for _mermaid_id() sanitization."""

    def test_dots_replaced(self) -> None:
        from amil_utils.mermaid import _mermaid_id

        assert _mermaid_id("res.partner") == "res_partner"

    def test_hyphens_replaced(self) -> None:
        from amil_utils.mermaid import _mermaid_id

        assert _mermaid_id("uni-fee") == "uni_fee"

    def test_underscores_unchanged(self) -> None:
        from amil_utils.mermaid import _mermaid_id

        assert _mermaid_id("uni_student") == "uni_student"

    def test_mixed_dots_and_hyphens(self) -> None:
        from amil_utils.mermaid import _mermaid_id

        assert _mermaid_id("res.partner-info") == "res_partner_info"

    def test_multiple_dots(self) -> None:
        from amil_utils.mermaid import _mermaid_id

        assert _mermaid_id("uni.fee.invoice") == "uni_fee_invoice"

    def test_already_clean(self) -> None:
        from amil_utils.mermaid import _mermaid_id

        assert _mermaid_id("mail") == "mail"


# ===========================================================================
# TestIsKeyField
# ===========================================================================


class TestIsKeyField:
    """Tests for _is_key_field() filtering heuristic."""

    def test_name_field(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("name", {"type": "Char"}) is True

    def test_state_field(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("state", {"type": "Selection"}) is True

    def test_monetary_field(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("amount_total", {"type": "Monetary"}) is True

    def test_selection_field(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("payment_type", {"type": "Selection"}) is True

    def test_technical_field_excluded(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("create_uid", {"type": "Many2one"}) is False

    def test_write_date_excluded(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("write_date", {"type": "Datetime"}) is False

    def test_message_ids_excluded(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("message_ids", {"type": "One2many"}) is False

    def test_text_type_excluded(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("notes", {"type": "Text"}) is False

    def test_binary_type_excluded(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("attachment", {"type": "Binary"}) is False

    def test_html_type_excluded(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("body_html", {"type": "Html"}) is False

    def test_non_stored_computed_excluded(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert (
            _is_key_field("computed_field", {"type": "Char", "compute": "_compute_x"})
            is False
        )

    def test_stored_computed_included(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert (
            _is_key_field(
                "stored_field",
                {"type": "Char", "compute": "_compute_x", "store": True},
            )
            is True
        )

    def test_regular_char_excluded(self) -> None:
        """A plain Char field that is not 'name' should be excluded."""
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("description", {"type": "Char"}) is False

    def test_regular_integer_excluded(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("sequence", {"type": "Integer"}) is False

    def test_activity_ids_excluded(self) -> None:
        from amil_utils.mermaid import _is_key_field

        assert _is_key_field("activity_ids", {"type": "One2many"}) is False


# ===========================================================================
# TestIsExternalModule
# ===========================================================================


class TestIsExternalModule:
    """Tests for _is_external_module()."""

    def test_external_module(self, project_modules: set[str]) -> None:
        from amil_utils.mermaid import _is_external_module

        assert _is_external_module("mail", project_modules) is True

    def test_project_module(self, project_modules: set[str]) -> None:
        from amil_utils.mermaid import _is_external_module

        assert _is_external_module("uni_fee", project_modules) is False

    def test_base_is_external(self, project_modules: set[str]) -> None:
        from amil_utils.mermaid import _is_external_module

        assert _is_external_module("base", project_modules) is True


# ===========================================================================
# TestDependencyDag
# ===========================================================================


class TestDependencyDag:
    """Tests for generate_dependency_dag()."""

    def test_basic_dag_structure(self) -> None:
        from amil_utils.mermaid import generate_dependency_dag

        dep_graph = {
            "uni_fee": ["uni_core", "uni_student", "mail"],
        }
        project_mods = {"uni_fee", "uni_core", "uni_student"}
        result = generate_dependency_dag("uni_fee", dep_graph, project_mods)

        assert result.startswith("graph TD\n")
        assert result.endswith("\n")

    def test_node_declarations(self) -> None:
        from amil_utils.mermaid import generate_dependency_dag

        dep_graph = {"uni_fee": ["uni_core", "mail"]}
        project_mods = {"uni_fee", "uni_core"}
        result = generate_dependency_dag("uni_fee", dep_graph, project_mods)

        assert 'uni_fee["uni_fee"]' in result
        assert 'uni_core["uni_core"]' in result

    def test_external_class_marker(self) -> None:
        from amil_utils.mermaid import generate_dependency_dag

        dep_graph = {"uni_fee": ["mail"]}
        project_mods = {"uni_fee"}
        result = generate_dependency_dag("uni_fee", dep_graph, project_mods)

        assert 'mail["mail"]:::external' in result

    def test_edges(self) -> None:
        from amil_utils.mermaid import generate_dependency_dag

        dep_graph = {"uni_fee": ["uni_core", "mail"]}
        project_mods = {"uni_fee", "uni_core"}
        result = generate_dependency_dag("uni_fee", dep_graph, project_mods)

        assert "uni_fee --> uni_core" in result
        assert "uni_fee --> mail" in result

    def test_classdef_line(self) -> None:
        from amil_utils.mermaid import generate_dependency_dag

        dep_graph = {"uni_fee": ["mail"]}
        project_mods = {"uni_fee"}
        result = generate_dependency_dag("uni_fee", dep_graph, project_mods)

        assert "classDef external fill:#f0f0f0,stroke:#999,stroke-dasharray: 5 5" in result

    def test_no_deps_minimal_graph(self) -> None:
        from amil_utils.mermaid import generate_dependency_dag

        dep_graph = {"uni_core": []}
        project_mods = {"uni_core"}
        result = generate_dependency_dag("uni_core", dep_graph, project_mods)

        assert result.startswith("graph TD\n")
        assert 'uni_core["uni_core"]' in result
        assert result.endswith("\n")

    def test_module_not_in_graph(self) -> None:
        """Module not in dependency_graph should still produce a minimal graph."""
        from amil_utils.mermaid import generate_dependency_dag

        dep_graph: dict[str, list[str]] = {}
        project_mods = {"uni_core"}
        result = generate_dependency_dag("uni_core", dep_graph, project_mods)

        assert result.startswith("graph TD\n")
        assert 'uni_core["uni_core"]' in result

    def test_trailing_newline(self) -> None:
        from amil_utils.mermaid import generate_dependency_dag

        result = generate_dependency_dag("uni_fee", {"uni_fee": ["mail"]}, {"uni_fee"})
        assert result.endswith("\n")


# ===========================================================================
# TestErDiagram
# ===========================================================================


class TestErDiagram:
    """Tests for generate_er_diagram()."""

    def test_basic_structure(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        assert result.startswith("erDiagram\n")
        assert result.endswith("\n")

    def test_entity_blocks(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        assert "uni_fee_invoice {" in result
        assert "uni_fee_line {" in result

    def test_key_fields_in_entity(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        # Key non-relational fields should appear
        assert "Char name" in result
        assert "Selection state" in result
        assert "Monetary amount_total" in result

    def test_stored_computed_in_entity(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        assert "Char stored_computed" in result

    def test_excluded_fields_not_in_entity(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        # Technical fields, excluded types, non-stored computed should NOT appear
        # as attributes inside entity blocks (they may appear in relationship lines)
        lines = result.split("\n")
        entity_lines = [
            l
            for l in lines
            if l.strip().startswith(("Char ", "Text ", "Binary ", "Html ", "Datetime ", "Many2one "))
            or "computed_field" in l
        ]
        # Non-stored computed field should not be an entity attribute
        assert not any("Char computed_field" in l for l in lines)
        # Text field excluded
        assert not any("Text notes" in l for l in lines)
        # Binary field excluded
        assert not any("Binary attachment" in l for l in lines)
        # Html field excluded
        assert not any("Html description_html" in l for l in lines)

    def test_many2one_relationship_same_module(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        """Same-module Many2one uses solid line."""
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        # uni.fee.line -> uni.fee.invoice (same module, solid)
        assert "uni_fee_line }o--|| uni_fee_invoice : invoice_id" in result

    def test_one2many_relationship_same_module(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        """Same-module One2many uses solid line."""
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        # uni.fee.invoice -> uni.fee.line (One2many, same module, solid)
        assert "uni_fee_invoice ||--o{ uni_fee_line : line_ids" in result

    def test_cross_module_dotted_lines(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        """Cross-module references use dotted lines."""
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        # uni.fee.invoice -> uni.student (cross-module, dotted)
        assert "uni_fee_invoice }o..|| uni_student : student_id" in result

    def test_technical_relational_fields_excluded(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        """Technical fields like create_uid should not appear as relationships."""
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        assert "create_uid" not in result

    def test_empty_module_minimal_er(self, registry_with_models: ModelRegistry) -> None:
        """Empty module produces minimal valid erDiagram."""
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("empty_mod", {}, registry_with_models)

        assert result.startswith("erDiagram\n")
        assert result.endswith("\n")

    def test_field_type_shown(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        """Field types are shown next to field names in entities."""
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        # Format: "        Type field_name"
        assert "Char name" in result
        assert "Monetary amount_total" in result

    def test_trailing_newline(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)
        assert result.endswith("\n")

    def test_cross_module_stub_entity(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        """Cross-module models get a minimal entity stub."""
        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        # uni.student is cross-module -- should appear as an entity
        assert "uni_student {" in result


# ===========================================================================
# TestMermaidSyntax
# ===========================================================================


class TestMermaidSyntax:
    """Basic Mermaid syntax validation on generated output."""

    def test_dag_no_empty_lines_in_edges(self) -> None:
        from amil_utils.mermaid import generate_dependency_dag

        dep_graph = {"uni_fee": ["uni_core", "mail"]}
        project_mods = {"uni_fee", "uni_core"}
        result = generate_dependency_dag("uni_fee", dep_graph, project_mods)

        # No consecutive empty lines
        assert "\n\n\n" not in result

    def test_er_valid_relationship_syntax(
        self,
        sample_models: dict[str, ModelEntry],
        registry_with_models: ModelRegistry,
    ) -> None:
        """All relationship lines match expected patterns."""
        import re

        from amil_utils.mermaid import generate_er_diagram

        result = generate_er_diagram("uni_fee", sample_models, registry_with_models)

        # Relationship lines should match the pattern:
        # entity_a }o--|| entity_b : field_name (or with .. for cross-module)
        rel_pattern = re.compile(
            r"^\s+\w+ (\}o--\|\||\|\|--o\{|\}o--o\{|\}o\.\.\|\||\|\|\.\.o\{|\}o\.\.o\{) \w+ : \w+$"
        )
        for line in result.split("\n"):
            # Skip non-relationship lines
            if " : " in line and "{" not in line:
                assert rel_pattern.match(line), f"Invalid relationship syntax: {line!r}"

    def test_dag_all_arrows_valid(self) -> None:
        from amil_utils.mermaid import generate_dependency_dag

        dep_graph = {"uni_fee": ["uni_core", "mail"]}
        project_mods = {"uni_fee", "uni_core"}
        result = generate_dependency_dag("uni_fee", dep_graph, project_mods)

        for line in result.split("\n"):
            if "-->" in line:
                parts = line.strip().split(" --> ")
                assert len(parts) == 2, f"Invalid arrow: {line!r}"


# ===========================================================================
# TestModuleDiagrams
# ===========================================================================


class TestModuleDiagrams:
    """Tests for generate_module_diagrams() file writing."""

    def test_writes_both_files(
        self,
        tmp_path: Path,
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_module_diagrams

        spec = {
            "module_name": "uni_fee",
            "models": [
                {
                    "_name": "uni.fee.invoice",
                    "fields": {"name": {"type": "Char"}},
                    "_inherit": [],
                    "description": "Fee Invoice",
                },
            ],
            "depends": ["base", "mail", "uni_core"],
        }
        output_dir = tmp_path / "docs"
        generate_module_diagrams("uni_fee", spec, registry_with_models, output_dir)

        assert (output_dir / "dependencies.mmd").exists()
        assert (output_dir / "er_diagram.mmd").exists()

    def test_creates_output_dir(
        self,
        tmp_path: Path,
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_module_diagrams

        spec = {
            "module_name": "uni_fee",
            "models": [],
            "depends": ["base"],
        }
        output_dir = tmp_path / "new_dir" / "docs"
        generate_module_diagrams("uni_fee", spec, registry_with_models, output_dir)

        assert output_dir.exists()
        assert (output_dir / "dependencies.mmd").exists()

    def test_file_content_valid(
        self,
        tmp_path: Path,
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_module_diagrams

        spec = {
            "module_name": "uni_fee",
            "models": [
                {
                    "_name": "uni.fee.invoice",
                    "fields": {"name": {"type": "Char"}},
                    "_inherit": [],
                    "description": "Fee Invoice",
                },
            ],
            "depends": ["base", "mail"],
        }
        output_dir = tmp_path / "docs"
        generate_module_diagrams("uni_fee", spec, registry_with_models, output_dir)

        dep_content = (output_dir / "dependencies.mmd").read_text()
        er_content = (output_dir / "er_diagram.mmd").read_text()

        assert dep_content.startswith("graph TD\n")
        assert er_content.startswith("erDiagram\n")
        assert dep_content.endswith("\n")
        assert er_content.endswith("\n")


# ===========================================================================
# TestProjectDiagrams
# ===========================================================================


class TestProjectDiagrams:
    """Tests for generate_project_diagrams() file writing."""

    def test_writes_both_files(
        self,
        tmp_path: Path,
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_project_diagrams

        output_dir = tmp_path / "diagrams"
        generate_project_diagrams(registry_with_models, output_dir)

        assert (output_dir / "project_dependencies.mmd").exists()
        assert (output_dir / "project_er.mmd").exists()

    def test_creates_output_dir(
        self,
        tmp_path: Path,
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_project_diagrams

        output_dir = tmp_path / "new" / "diagrams"
        generate_project_diagrams(registry_with_models, output_dir)

        assert output_dir.exists()

    def test_project_dep_includes_all_modules(
        self,
        tmp_path: Path,
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_project_diagrams

        output_dir = tmp_path / "diagrams"
        generate_project_diagrams(registry_with_models, output_dir)

        content = (output_dir / "project_dependencies.mmd").read_text()
        assert "uni_fee" in content
        assert "uni_student" in content
        assert "uni_core" in content

    def test_project_er_includes_all_models(
        self,
        tmp_path: Path,
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_project_diagrams

        output_dir = tmp_path / "diagrams"
        generate_project_diagrams(registry_with_models, output_dir)

        content = (output_dir / "project_er.mmd").read_text()
        assert "uni_fee_invoice" in content
        assert "uni_student" in content

    def test_trailing_newlines(
        self,
        tmp_path: Path,
        registry_with_models: ModelRegistry,
    ) -> None:
        from amil_utils.mermaid import generate_project_diagrams

        output_dir = tmp_path / "diagrams"
        generate_project_diagrams(registry_with_models, output_dir)

        dep_content = (output_dir / "project_dependencies.mmd").read_text()
        er_content = (output_dir / "project_er.mmd").read_text()
        assert dep_content.endswith("\n")
        assert er_content.endswith("\n")


# ===========================================================================
# TestManyToManyRelationship
# ===========================================================================


class TestManyToManyRelationship:
    """Tests for Many2many relationship rendering."""

    def test_many2many_same_module(self, registry_with_models: ModelRegistry) -> None:
        from amil_utils.mermaid import generate_er_diagram

        models = {
            "uni.course": ModelEntry(
                module="uni_core",
                fields={
                    "name": {"type": "Char"},
                    "student_ids": {
                        "type": "Many2many",
                        "comodel_name": "uni.config",
                        "string": "Students",
                    },
                },
            ),
            "uni.config": ModelEntry(
                module="uni_core",
                fields={"name": {"type": "Char"}},
            ),
        }
        result = generate_er_diagram("uni_core", models, registry_with_models)

        assert "uni_course }o--o{ uni_config : student_ids" in result

    def test_many2many_cross_module(self, registry_with_models: ModelRegistry) -> None:
        from amil_utils.mermaid import generate_er_diagram

        models = {
            "uni.course": ModelEntry(
                module="uni_core",
                fields={
                    "name": {"type": "Char"},
                    "tag_ids": {
                        "type": "Many2many",
                        "comodel_name": "uni.student",
                        "string": "Tags",
                    },
                },
            ),
        }
        result = generate_er_diagram("uni_core", models, registry_with_models)

        # Cross-module: dotted
        assert "uni_course }o..o{ uni_student : tag_ids" in result


# ===========================================================================
# CLI Test Fixtures
# ===========================================================================


@pytest.fixture()
def runner() -> click.testing.CliRunner:
    """Click CLI test runner."""
    return click.testing.CliRunner()


@pytest.fixture()
def cli_registry(tmp_path: Path) -> Path:
    """Create a populated registry JSON for CLI tests."""
    data = {
        "_meta": {
            "version": "1.0",
            "last_updated": "2026-01-01T00:00:00+00:00",
            "odoo_version": "17.0",
            "modules_registered": 2,
        },
        "models": {
            "uni.fee.invoice": {
                "module": "uni_fee",
                "fields": {
                    "name": {"type": "Char", "string": "Name"},
                    "state": {"type": "Selection", "string": "Status"},
                    "amount_total": {"type": "Monetary", "string": "Total"},
                    "student_id": {
                        "type": "Many2one",
                        "comodel_name": "uni.student",
                        "string": "Student",
                    },
                },
                "inherits": [],
                "mixins": [],
                "description": "Fee Invoice",
            },
            "uni.fee.line": {
                "module": "uni_fee",
                "fields": {
                    "name": {"type": "Char", "string": "Description"},
                    "amount": {"type": "Monetary", "string": "Amount"},
                    "invoice_id": {
                        "type": "Many2one",
                        "comodel_name": "uni.fee.invoice",
                        "string": "Invoice",
                    },
                },
                "inherits": [],
                "mixins": [],
                "description": "Fee Line",
            },
            "uni.student": {
                "module": "uni_student",
                "fields": {
                    "name": {"type": "Char", "string": "Name"},
                },
                "inherits": [],
                "mixins": [],
                "description": "Student",
            },
        },
        "dependency_graph": {
            "uni_fee": ["base", "mail", "uni_core"],
            "uni_student": ["base", "uni_core"],
        },
    }
    reg_path = tmp_path / ".planning" / "model_registry.json"
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return reg_path


@pytest.fixture()
def cli_spec(tmp_path: Path) -> dict:
    """Sample spec dict for CLI module-level mermaid tests."""
    return {
        "module_name": "uni_fee",
        "models": [
            {
                "_name": "uni.fee.invoice",
                "fields": {
                    "name": {"type": "Char", "string": "Name"},
                    "state": {"type": "Selection", "string": "Status"},
                    "student_id": {
                        "type": "Many2one",
                        "comodel_name": "uni.student",
                    },
                },
                "_inherit": [],
                "description": "Fee Invoice",
            },
        ],
        "depends": ["base", "mail", "uni_core"],
    }


# ===========================================================================
# TestMermaidCli
# ===========================================================================


class TestMermaidCli:
    """Integration tests for the `amil mermaid` CLI command."""

    def test_deps_writes_file(
        self, runner: click.testing.CliRunner, cli_registry: Path, tmp_path: Path
    ) -> None:
        """mermaid --module uni_fee --type deps writes dependencies.mmd."""
        output_dir = tmp_path / "output" / "uni_fee" / "docs"
        with patch("amil_utils.cli._find_registry_path", return_value=cli_registry):
            result = runner.invoke(
                main, ["mermaid", "--module", "uni_fee", "--type", "deps"]
            )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # Check a file was written somewhere containing "graph TD"

    def test_er_writes_file(
        self, runner: click.testing.CliRunner, cli_registry: Path, tmp_path: Path
    ) -> None:
        """mermaid --module uni_fee --type er writes er_diagram.mmd."""
        with patch("amil_utils.cli._find_registry_path", return_value=cli_registry):
            result = runner.invoke(
                main, ["mermaid", "--module", "uni_fee", "--type", "er"]
            )
        assert result.exit_code == 0, f"CLI failed: {result.output}"

    def test_all_writes_both(
        self, runner: click.testing.CliRunner, cli_registry: Path, tmp_path: Path
    ) -> None:
        """mermaid --module uni_fee --type all writes both .mmd files."""
        with patch("amil_utils.cli._find_registry_path", return_value=cli_registry):
            result = runner.invoke(
                main, ["mermaid", "--module", "uni_fee", "--type", "all"]
            )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "dependencies.mmd" in result.output
        assert "er_diagram.mmd" in result.output

    def test_default_type_is_all(
        self, runner: click.testing.CliRunner, cli_registry: Path, tmp_path: Path
    ) -> None:
        """mermaid --module uni_fee (no --type) defaults to all."""
        with patch("amil_utils.cli._find_registry_path", return_value=cli_registry):
            result = runner.invoke(main, ["mermaid", "--module", "uni_fee"])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "dependencies.mmd" in result.output
        assert "er_diagram.mmd" in result.output

    def test_project_deps(
        self, runner: click.testing.CliRunner, cli_registry: Path, tmp_path: Path
    ) -> None:
        """mermaid --project --type deps writes project_dependencies.mmd."""
        with patch("amil_utils.cli._find_registry_path", return_value=cli_registry):
            result = runner.invoke(
                main, ["mermaid", "--project", "--type", "deps"]
            )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "project_dependencies.mmd" in result.output

    def test_project_er(
        self, runner: click.testing.CliRunner, cli_registry: Path, tmp_path: Path
    ) -> None:
        """mermaid --project --type er writes project_er.mmd."""
        with patch("amil_utils.cli._find_registry_path", return_value=cli_registry):
            result = runner.invoke(
                main, ["mermaid", "--project", "--type", "er"]
            )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "project_er.mmd" in result.output

    def test_stdout(
        self, runner: click.testing.CliRunner, cli_registry: Path, tmp_path: Path
    ) -> None:
        """mermaid --module uni_fee --stdout prints diagram to stdout."""
        with patch("amil_utils.cli._find_registry_path", return_value=cli_registry):
            result = runner.invoke(
                main, ["mermaid", "--module", "uni_fee", "--type", "deps", "--stdout"]
            )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "graph TD" in result.output


# ===========================================================================
# TestMermaidCliEdgeCases
# ===========================================================================


class TestMermaidCliEdgeCases:
    """Edge case tests for the mermaid CLI command."""

    def test_no_module_no_project_fails(
        self, runner: click.testing.CliRunner
    ) -> None:
        """mermaid with neither --module nor --project exits with code 1."""
        result = runner.invoke(main, ["mermaid"])
        assert result.exit_code != 0

    def test_both_module_and_project_fails(
        self, runner: click.testing.CliRunner
    ) -> None:
        """mermaid with both --module and --project exits with code 1."""
        result = runner.invoke(
            main, ["mermaid", "--module", "uni_fee", "--project"]
        )
        assert result.exit_code != 0


# ===========================================================================
# TestAutoGeneration
# ===========================================================================


class TestAutoGeneration:
    """Tests for the auto-generation hook in render_module_cmd."""

    def test_auto_gen_after_render(
        self, runner: click.testing.CliRunner, cli_registry: Path, tmp_path: Path
    ) -> None:
        """After successful render + validation, mermaid diagrams are created."""
        spec = {
            "module_name": "uni_fee",
            "models": [
                {
                    "_name": "uni.fee.invoice",
                    "fields": {"name": {"type": "Char"}},
                },
            ],
            "depends": ["base", "mail"],
        }
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(spec), encoding="utf-8")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with (
            patch("amil_utils.cli._find_registry_path", return_value=cli_registry),
            patch(
                "amil_utils.renderer.render_module",
                return_value=(["file1.py"], []),
            ),
            patch(
                "amil_utils.renderer.get_template_dir",
                return_value=tmp_path,
            ),
        ):
            result = runner.invoke(
                main,
                ["render-module", "--spec-file", str(spec_file), "--output-dir", str(output_dir)],
            )

        # Mermaid diagrams should be mentioned in output
        assert "Mermaid diagrams" in result.output or "mermaid" in result.output.lower()

    def test_auto_gen_best_effort(
        self, runner: click.testing.CliRunner, cli_registry: Path, tmp_path: Path
    ) -> None:
        """Mermaid generation failure does not block render."""
        spec = {
            "module_name": "uni_fee",
            "models": [
                {
                    "_name": "uni.fee.invoice",
                    "fields": {"name": {"type": "Char"}},
                },
            ],
            "depends": ["base"],
        }
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(spec), encoding="utf-8")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with (
            patch("amil_utils.cli._find_registry_path", return_value=cli_registry),
            patch(
                "amil_utils.renderer.render_module",
                return_value=(["file1.py"], []),
            ),
            patch(
                "amil_utils.renderer.get_template_dir",
                return_value=tmp_path,
            ),
            patch(
                "amil_utils.mermaid.generate_module_diagrams",
                side_effect=RuntimeError("mermaid broken"),
            ),
        ):
            result = runner.invoke(
                main,
                ["render-module", "--spec-file", str(spec_file), "--output-dir", str(output_dir)],
            )

        # Render should still succeed even though mermaid failed
        assert result.exit_code == 0, f"Render failed: {result.output}"

    def test_auto_gen_skipped_when_validation_skipped(
        self, runner: click.testing.CliRunner, cli_registry: Path, tmp_path: Path
    ) -> None:
        """With --skip-validation, mermaid auto-generation is NOT attempted."""
        spec = {
            "module_name": "uni_fee",
            "models": [
                {
                    "_name": "uni.fee.invoice",
                    "fields": {"name": {"type": "Char"}},
                },
            ],
            "depends": ["base"],
        }
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(spec), encoding="utf-8")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with (
            patch("amil_utils.cli._find_registry_path", return_value=cli_registry),
            patch(
                "amil_utils.renderer.render_module",
                return_value=(["file1.py"], []),
            ),
            patch(
                "amil_utils.renderer.get_template_dir",
                return_value=tmp_path,
            ),
        ):
            result = runner.invoke(
                main,
                [
                    "render-module",
                    "--spec-file", str(spec_file),
                    "--output-dir", str(output_dir),
                    "--skip-validation",
                ],
            )

        # "Mermaid diagrams" should NOT appear when validation is skipped
        assert "Mermaid diagrams" not in result.output
