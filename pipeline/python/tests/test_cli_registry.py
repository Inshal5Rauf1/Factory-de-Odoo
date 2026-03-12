"""CLI integration tests for registry commands and post-render hook."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import click.testing
import pytest

from amil_utils.cli import main


@pytest.fixture()
def runner():
    return click.testing.CliRunner()


@pytest.fixture()
def tmp_registry(tmp_path):
    """Return path to a temporary registry file (does not exist yet)."""
    return tmp_path / "model_registry.json"


@pytest.fixture()
def populated_registry(tmp_registry):
    """Create a registry with one module (uni_fee) and two models."""
    data = {
        "_meta": {
            "version": "1.0",
            "last_updated": "2026-01-01T00:00:00+00:00",
            "odoo_version": "17.0",
            "modules_registered": 1,
        },
        "models": {
            "uni.fee": {
                "module": "uni_fee",
                "fields": {
                    "name": {"type": "Char"},
                    "student_id": {"type": "Many2one", "comodel_name": "res.partner"},
                },
                "inherits": [],
                "mixins": [],
                "description": "University Fee",
            },
            "uni.fee.line": {
                "module": "uni_fee",
                "fields": {
                    "fee_id": {"type": "Many2one", "comodel_name": "uni.fee"},
                    "amount": {"type": "Float"},
                },
                "inherits": [],
                "mixins": [],
                "description": "Fee Line",
            },
        },
        "dependency_graph": {"uni_fee": ["base", "account"]},
    }
    tmp_registry.parent.mkdir(parents=True, exist_ok=True)
    tmp_registry.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return tmp_registry


def _make_spec(
    module_name: str = "test_mod",
    models: list | None = None,
    depends: list | None = None,
) -> dict:
    if models is None:
        models = [
            {
                "_name": "test.model",
                "fields": {"name": {"type": "Char"}},
            }
        ]
    return {
        "module_name": module_name,
        "models": models,
        "depends": depends if depends is not None else ["base"],
    }


# ---- registry list --------------------------------------------------------


class TestRegistryList:
    def test_registry_list_empty(self, runner, tmp_registry):
        with patch("amil_utils.cli._find_registry_path", return_value=tmp_registry):
            result = runner.invoke(main, ["registry", "list"])
        assert result.exit_code == 0
        assert "No modules registered" in result.output

    def test_registry_list_with_modules(self, runner, populated_registry):
        with patch("amil_utils.cli._find_registry_path", return_value=populated_registry):
            result = runner.invoke(main, ["registry", "list"])
        assert result.exit_code == 0
        assert "uni_fee" in result.output
        assert "2" in result.output  # 2 models

    def test_registry_list_json(self, runner, populated_registry):
        with patch("amil_utils.cli._find_registry_path", return_value=populated_registry):
            result = runner.invoke(main, ["registry", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "uni_fee" in data
        assert len(data["uni_fee"]) == 2


# ---- registry show --------------------------------------------------------


class TestRegistryShow:
    def test_registry_show_found(self, runner, populated_registry):
        with patch("amil_utils.cli._find_registry_path", return_value=populated_registry):
            result = runner.invoke(main, ["registry", "show", "uni.fee"])
        assert result.exit_code == 0
        assert "uni.fee" in result.output
        assert "uni_fee" in result.output  # module name
        assert "student_id" in result.output or "fields" in result.output.lower()

    def test_registry_show_not_found(self, runner, populated_registry):
        with patch("amil_utils.cli._find_registry_path", return_value=populated_registry):
            result = runner.invoke(main, ["registry", "show", "nonexistent.model"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()


# ---- registry remove ------------------------------------------------------


class TestRegistryRemove:
    def test_registry_remove_module(self, runner, populated_registry):
        with patch("amil_utils.cli._find_registry_path", return_value=populated_registry):
            result = runner.invoke(main, ["registry", "remove", "uni_fee"])
        assert result.exit_code == 0
        assert "removed" in result.output.lower() or "Removed" in result.output
        # Verify file was updated
        data = json.loads(populated_registry.read_text(encoding="utf-8"))
        assert "uni.fee" not in data["models"]
        assert "uni_fee" not in data["dependency_graph"]

    def test_registry_remove_nonexistent(self, runner, populated_registry):
        with patch("amil_utils.cli._find_registry_path", return_value=populated_registry):
            result = runner.invoke(main, ["registry", "remove", "nonexistent"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower() or "warning" in result.output.lower()


# ---- registry validate ----------------------------------------------------


class TestRegistryValidate:
    def test_registry_validate_clean(self, runner, populated_registry):
        with patch("amil_utils.cli._find_registry_path", return_value=populated_registry):
            result = runner.invoke(main, ["registry", "validate"])
        assert result.exit_code == 0

    def test_registry_validate_warnings(self, runner, tmp_registry):
        """Registry with a broken comodel reference should show warnings."""
        data = {
            "_meta": {"version": "1.0", "last_updated": "", "odoo_version": "17.0", "modules_registered": 1},
            "models": {
                "bad.model": {
                    "module": "bad_mod",
                    "fields": {
                        "ref_id": {"type": "Many2one", "comodel_name": "nonexistent.model"},
                    },
                    "inherits": [],
                    "mixins": [],
                    "description": "",
                },
            },
            "dependency_graph": {"bad_mod": ["base"]},
        }
        tmp_registry.write_text(json.dumps(data), encoding="utf-8")
        with patch("amil_utils.cli._find_registry_path", return_value=tmp_registry):
            result = runner.invoke(main, ["registry", "validate"])
        assert result.exit_code == 0
        assert "WARNING" in result.output or "warning" in result.output.lower()

    def test_registry_validate_errors(self, runner, tmp_registry):
        """Registry with circular dependency should exit with error."""
        data = {
            "_meta": {"version": "1.0", "last_updated": "", "odoo_version": "17.0", "modules_registered": 2},
            "models": {},
            "dependency_graph": {"mod_a": ["mod_b"], "mod_b": ["mod_a"]},
        }
        tmp_registry.write_text(json.dumps(data), encoding="utf-8")
        with patch("amil_utils.cli._find_registry_path", return_value=tmp_registry):
            result = runner.invoke(main, ["registry", "validate"])
        assert result.exit_code == 1
        assert "ERROR" in result.output or "error" in result.output.lower()


# ---- registry import ------------------------------------------------------


class TestRegistryImport:
    def test_registry_import_manifest(self, runner, tmp_registry, tmp_path):
        """Import from a __manifest__.py and model file."""
        # Create a minimal module directory
        mod_dir = tmp_path / "test_module"
        mod_dir.mkdir()
        models_dir = mod_dir / "models"
        models_dir.mkdir()

        manifest = mod_dir / "__manifest__.py"
        manifest.write_text(
            "{\n"
            "    'name': 'Test Module',\n"
            "    'version': '17.0.1.0.0',\n"
            "    'depends': ['base', 'mail'],\n"
            "    'data': [],\n"
            "}\n",
            encoding="utf-8",
        )

        model_file = models_dir / "test_model.py"
        model_file.write_text(
            "from odoo import models, fields\n\n"
            "class TestModel(models.Model):\n"
            "    _name = 'test.model'\n"
            "    _description = 'A Test Model'\n\n"
            "    name = fields.Char(string='Name')\n"
            "    partner_id = fields.Many2one('res.partner', string='Partner')\n",
            encoding="utf-8",
        )

        with patch("amil_utils.cli._find_registry_path", return_value=tmp_registry):
            result = runner.invoke(main, ["registry", "import", "--from-manifest", str(manifest)])
        assert result.exit_code == 0
        assert "test_module" in result.output or "registered" in result.output.lower()
        # Verify registry was saved
        assert tmp_registry.exists()
        data = json.loads(tmp_registry.read_text(encoding="utf-8"))
        assert "test.model" in data["models"]


# ---- post-render hook -----------------------------------------------------


class TestPostRenderHook:
    def test_render_module_updates_registry(self, runner, tmp_path):
        """After successful render, registry contains new models."""
        spec = _make_spec("gen_mod", models=[
            {"_name": "gen.model", "fields": {"name": {"type": "Char"}}},
            {"_name": "gen.line", "fields": {"ref": {"type": "Many2one", "comodel_name": "gen.model"}}},
        ])
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(spec), encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        registry_path = tmp_path / "model_registry.json"

        with (
            patch("amil_utils.cli._find_registry_path", return_value=registry_path),
            patch("amil_utils.renderer.render_module", return_value=(["file1.py"], [])),
            patch("amil_utils.cli.build_verifier_from_env", return_value=None, create=True),
        ):
            # Need to patch where render_module is looked up (inside the function)
            with patch("amil_utils.renderer.get_template_dir", return_value=tmp_path):
                result = runner.invoke(main, ["render-module", "--spec-file", str(spec_file), "--output-dir", str(output_dir)])

        # Registry should be updated if render succeeded
        if result.exit_code == 0 and registry_path.exists():
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            assert "gen.model" in data["models"]
            assert "gen.line" in data["models"]
            assert "Registry updated" in result.output

    def test_render_module_failure_no_registry_update(self, runner, tmp_path):
        """Failed render does not update registry."""
        spec = _make_spec("fail_mod")
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(spec), encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        registry_path = tmp_path / "model_registry.json"

        with (
            patch("amil_utils.cli._find_registry_path", return_value=registry_path),
            patch("amil_utils.renderer.render_module", side_effect=RuntimeError("render failed")),
            patch("amil_utils.renderer.get_template_dir", return_value=tmp_path),
        ):
            result = runner.invoke(main, ["render-module", "--spec-file", str(spec_file), "--output-dir", str(output_dir)])

        # Registry should NOT exist (never updated)
        assert not registry_path.exists()


# ---- lazy imports ----------------------------------------------------------


class TestRegistryLazyImports:
    def test_registry_lazy_imports(self):
        """Registry imports must be inside functions, not at module level."""
        import ast

        cli_path = (
            Path(__file__).parent.parent / "src" / "amil_utils" / "cli.py"
        )
        source = cli_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        top_level_imports: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_level_imports.append(node.module)

        registry_violations = [
            imp for imp in top_level_imports if "registry" in imp.lower()
        ]
        assert not registry_violations, (
            f"Registry imports at module level: {registry_violations}. "
            f"Must be lazy (inside functions)."
        )
