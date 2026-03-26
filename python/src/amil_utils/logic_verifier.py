"""AST-based verification of AI-written method bodies.

Checks that:
- _compute_* methods assign their target field (not just pass/placeholder)
- action_* methods check state before modifying it
"""
from __future__ import annotations

import ast
from pathlib import Path


def verify_compute_methods(module_path: Path) -> list[dict]:
    """Check that each _compute_* method assigns its target field.

    Returns list of issue dicts with keys: file, method, issue.
    """
    issues: list[dict] = []
    models_dir = module_path / "models"
    if not models_dir.exists():
        return issues

    for py_file in sorted(models_dir.glob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith("_compute_"):
                continue

            target_field = node.name[len("_compute_"):]
            if _has_field_assignment(node, target_field):
                continue

            issues.append({
                "file": py_file.name,
                "method": node.name,
                "issue": f"compute method does not assign 'rec.{target_field}'",
            })

    return issues


def verify_action_methods(module_path: Path) -> list[dict]:
    """Check that action_* methods check state before modifying it.

    Returns list of issue dicts with keys: file, method, issue.
    """
    issues: list[dict] = []
    models_dir = module_path / "models"
    if not models_dir.exists():
        return issues

    for py_file in sorted(models_dir.glob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith("action_"):
                continue

            if _writes_state(node) and not _checks_state(node):
                issues.append({
                    "file": py_file.name,
                    "method": node.name,
                    "issue": "action modifies 'state' without checking current state",
                })

    return issues


def _has_field_assignment(func_node: ast.FunctionDef, field_name: str) -> bool:
    """Check if any statement assigns rec.{field_name}."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr == field_name
                ):
                    return True
    return False


def _writes_state(func_node: ast.FunctionDef) -> bool:
    """Check if function assigns to .state."""
    return _has_field_assignment(func_node, "state")


def _checks_state(func_node: ast.FunctionDef) -> bool:
    """Check if function reads .state in a condition (if/assert)."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.If):
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Attribute) and sub.attr == "state":
                    return True
        if isinstance(node, ast.Assert):
            test_node = getattr(node, "test", None)
            if test_node is not None:
                for sub in ast.walk(test_node):
                    if isinstance(sub, ast.Attribute) and sub.attr == "state":
                        return True
    return False
