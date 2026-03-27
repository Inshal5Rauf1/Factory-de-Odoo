"""Registry helpers extracted from cli.py.

Contains ``_find_registry_path`` and ``_parse_module_dir_to_spec``
used by multiple registry-related commands.
"""

from __future__ import annotations

from pathlib import Path


def find_registry_path() -> Path:
    """Return the path to the model registry JSON file (relative to cwd)."""
    return Path(".planning/model_registry.json")


def parse_module_dir_to_spec(
    module_name: str, manifest_data: dict, mod_dir: Path
) -> dict:
    """Parse a module directory into a spec dict for registry registration.

    Uses AST to extract _name and field definitions from Python model files.
    """
    import ast as ast_mod

    depends = manifest_data.get("depends", ["base"])
    models_list: list[dict] = []

    models_dir = mod_dir / "models"
    if models_dir.is_dir():
        for py_file in models_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast_mod.parse(source)
            except (SyntaxError, OSError):
                continue

            for node in ast_mod.walk(tree):
                if not isinstance(node, ast_mod.ClassDef):
                    continue
                model_name = None
                model_desc = ""
                fields: dict = {}

                for item in node.body:
                    if (
                        isinstance(item, ast_mod.Assign)
                        and len(item.targets) == 1
                        and isinstance(item.targets[0], ast_mod.Name)
                    ):
                        attr_name = item.targets[0].id
                        if attr_name == "_name" and isinstance(
                            item.value, ast_mod.Constant
                        ):
                            model_name = item.value.value
                        elif attr_name == "_description" and isinstance(
                            item.value, ast_mod.Constant
                        ):
                            model_desc = item.value.value

                    if (
                        isinstance(item, ast_mod.Assign)
                        and len(item.targets) == 1
                        and isinstance(item.targets[0], ast_mod.Name)
                        and isinstance(item.value, ast_mod.Call)
                        and isinstance(item.value.func, ast_mod.Attribute)
                    ):
                        field_name = item.targets[0].id
                        if field_name.startswith("_"):
                            continue
                        field_type = item.value.func.attr
                        field_def: dict = {"type": field_type}

                        if item.value.args and isinstance(
                            item.value.args[0], ast_mod.Constant
                        ):
                            if field_type in ("Many2one", "One2many", "Many2many"):
                                field_def["comodel_name"] = item.value.args[0].value
                        for kw in item.value.keywords:
                            if kw.arg == "comodel_name" and isinstance(
                                kw.value, ast_mod.Constant
                            ):
                                field_def["comodel_name"] = kw.value.value

                        fields[field_name] = field_def

                if model_name:
                    models_list.append(
                        {
                            "_name": model_name,
                            "fields": fields,
                            "description": model_desc,
                        }
                    )

    return {
        "module_name": module_name,
        "models": models_list,
        "depends": depends,
    }
