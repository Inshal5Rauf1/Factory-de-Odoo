"""Post-logic-writer test enrichment.

Reads completed model Python files after amil-logic-writer fills method
bodies, extracts compute method signatures via AST, and generates
test data suggestions for automated assertion generation.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ComputeTestHint:
    """Hint for generating a test assertion for a compute method."""

    model_name: str
    method_name: str
    target_field: str
    depends_fields: list[str] = field(default_factory=list)
    field_type: str = "unknown"  # Float, Integer, Char, Boolean, etc.


def extract_compute_hints(module_path: Path) -> list[ComputeTestHint]:
    """Extract compute method test hints from a module's model files.

    Reads all .py files in models/ directory, finds @api.depends decorators
    on _compute_* methods, and extracts the target field name and dependencies.
    """
    hints: list[ComputeTestHint] = []
    models_dir = module_path / "models"
    if not models_dir.exists():
        return hints

    for py_file in sorted(models_dir.glob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for class_node in ast.walk(tree):
            if not isinstance(class_node, ast.ClassDef):
                continue

            # Extract _name from class body
            model_name = _extract_model_name(class_node)
            if not model_name:
                continue

            for node in class_node.body:
                if not isinstance(node, ast.FunctionDef):
                    continue
                if not node.name.startswith("_compute_"):
                    continue

                target_field = node.name[len("_compute_"):]
                depends = _extract_depends(node)
                field_type = _guess_field_type(class_node, target_field)

                hints.append(ComputeTestHint(
                    model_name=model_name,
                    method_name=node.name,
                    target_field=target_field,
                    depends_fields=depends,
                    field_type=field_type,
                ))

    return hints


def _extract_model_name(class_node: ast.ClassDef) -> str | None:
    """Extract _name = 'model.name' from a class body."""
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_name":
                    if isinstance(node.value, ast.Constant):
                        return str(node.value.value)
    return None


def _extract_depends(func_node: ast.FunctionDef) -> list[str]:
    """Extract field names from @api.depends('field1', 'field2') decorator."""
    for decorator in func_node.decorator_list:
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute) and func.attr == "depends":
                return [
                    arg.value
                    for arg in decorator.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                ]
    return []


def _guess_field_type(class_node: ast.ClassDef, field_name: str) -> str:
    """Guess field type from class body field definition."""
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == field_name:
                    if isinstance(node.value, ast.Call):
                        func = node.value.func
                        if isinstance(func, ast.Attribute):
                            return func.attr  # e.g., "Float", "Integer", "Char"
    return "unknown"
