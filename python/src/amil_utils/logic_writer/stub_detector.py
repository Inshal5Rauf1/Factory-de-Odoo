"""AST-based stub detection for generated Odoo Python files.

Scans ``.py`` files recursively, identifies methods whose bodies match
known TODO-stub patterns (bare ``pass``, ``for rec in self: pass``,
``for rec in self: rec.field = <constant>``), and returns a list of
:class:`StubInfo` frozen dataclasses describing each stub.

This module is intentionally a **leaf** -- it imports only from the
standard library to avoid circular dependencies with renderer or
validation modules.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Marker constants
# ---------------------------------------------------------------------------

_MARKER_START = "# --- BUSINESS LOGIC START ---"
_MARKER_END = "# --- BUSINESS LOGIC END ---"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StubInfo:
    """A detected TODO method stub in a generated Python file."""

    file: str
    """Relative path within the module directory."""

    line: int
    """1-based line number of the ``def`` statement."""

    class_name: str
    """Python class name containing the method."""

    model_name: str
    """Odoo ``_name`` value from the class body."""

    method_name: str
    """Name of the stubbed method."""

    decorator: str
    """Full decorator text (e.g. ``@api.depends("x", "y")``) or ``""``."""

    target_fields: list[str] = field(default_factory=list)
    """Field names set inside a compute-stub ``for`` loop."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_stubs(module_dir: Path) -> list[StubInfo]:
    """Scan all ``.py`` files in *module_dir* for TODO method stubs.

    Returns a list of :class:`StubInfo` entries sorted by file path then
    line number.
    """
    stubs: list[StubInfo] = []
    for py_file in sorted(module_dir.rglob("*.py")):
        rel = str(py_file.relative_to(module_dir))
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Cannot read %s, skipping", rel)
            continue
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            logger.warning("SyntaxError in %s, skipping", rel)
            continue

        source_lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_name = _extract_model_name(node)
            if model_name is None:
                continue
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef) and _is_stub_body(stmt):
                    stubs.append(
                        StubInfo(
                            file=rel,
                            line=stmt.lineno,
                            class_name=node.name,
                            model_name=model_name,
                            method_name=stmt.name,
                            decorator=_extract_decorator_string(
                                stmt, source_lines
                            ),
                            target_fields=_extract_target_fields(stmt),
                        )
                    )

    return stubs


def _find_stub_zones(source_lines: list[str]) -> list[dict[str, Any]]:
    """Find ``BUSINESS LOGIC START/END`` marker-delimited zones in *source_lines*.

    Returns a list of zone dicts, each with:
    - ``start_line`` (1-based, line of the START marker)
    - ``end_line`` (1-based, line of the END marker)
    - ``marker``: always ``"BUSINESS LOGIC"``

    Unclosed markers (START without a matching END) are silently ignored.
    """
    zones: list[dict[str, Any]] = []
    pending_start: int | None = None

    for idx, line in enumerate(source_lines, start=1):
        stripped = line.strip()
        if stripped == _MARKER_START:
            pending_start = idx
        elif stripped == _MARKER_END and pending_start is not None:
            zones.append({
                "start_line": pending_start,
                "end_line": idx,
                "marker": "BUSINESS LOGIC",
            })
            pending_start = None

    return zones


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_stub_body(func: ast.FunctionDef) -> bool:
    """Return ``True`` if *func* body matches a known stub pattern.

    Stub patterns (after filtering docstrings):
    1. Empty body (docstring only)
    2. Single ``pass`` statement
    3. Single ``for rec in self: pass`` (constraint stub)
    4. Single ``for rec in self: rec.field = <constant>`` (compute stub)
    5. Single ``for`` with multiple ``rec.field = <constant>`` assigns
       (multi-field compute stub)
    """
    executable = _executable_stmts(func.body)

    if not executable:
        return True  # docstring only -> stub

    if len(executable) == 1:
        stmt = executable[0]
        # Pattern: bare pass
        if isinstance(stmt, ast.Pass):
            return True
        # Pattern: for rec in self: ...
        if isinstance(stmt, ast.For):
            return _is_stub_for(stmt)

    return False


def _executable_stmts(body: list[ast.stmt]) -> list[ast.stmt]:
    """Filter out docstring expressions from a function body."""
    return [
        s
        for s in body
        if not (
            isinstance(s, ast.Expr)
            and isinstance(s.value, ast.Constant)
            and isinstance(s.value.value, str)
        )
    ]


def _is_stub_for(for_node: ast.For) -> bool:
    """Return ``True`` if the ``for`` loop body is a stub pattern."""
    body = for_node.body
    if len(body) == 1:
        inner = body[0]
        if isinstance(inner, ast.Pass):
            return True
        if isinstance(inner, ast.Assign) and _is_constant_attr_assign(inner):
            return True
        return False

    # Multi-statement for body: all must be constant attribute assigns
    if all(
        isinstance(s, ast.Assign) and _is_constant_attr_assign(s)
        for s in body
    ):
        return True

    return False


def _is_constant_attr_assign(node: ast.Assign) -> bool:
    """Return ``True`` if *node* is ``rec.field = <constant>``."""
    if not isinstance(node.value, ast.Constant):
        return False
    if len(node.targets) != 1:
        return False
    target = node.targets[0]
    return isinstance(target, ast.Attribute)


def _extract_model_name(cls: ast.ClassDef) -> str | None:
    """Extract ``_name = "..."`` from *cls* body, or ``None``."""
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "_name"
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    return stmt.value.value
    return None


def _extract_decorator_string(
    func: ast.FunctionDef, source_lines: list[str]
) -> str:
    """Extract the full decorator text from *source_lines* for *func*.

    Returns the first decorator as a single-line string, or ``""`` if
    there are no decorators.
    """
    if not func.decorator_list:
        return ""
    dec = func.decorator_list[0]
    start = dec.lineno - 1  # 0-based
    end = (dec.end_lineno or dec.lineno) - 1
    lines = source_lines[start : end + 1]
    return " ".join(line.strip() for line in lines)


def _extract_target_fields(func: ast.FunctionDef) -> list[str]:
    """Extract field names from compute-stub ``for`` loops.

    For stubs like ``for rec in self: rec.total = 0``, returns
    ``["total"]``.  Returns ``[]`` for non-compute stubs.
    """
    executable = _executable_stmts(func.body)
    if len(executable) != 1:
        return []
    stmt = executable[0]
    if not isinstance(stmt, ast.For):
        return []

    fields: list[str] = []
    for inner in stmt.body:
        if isinstance(inner, ast.Assign) and _is_constant_attr_assign(inner):
            target = inner.targets[0]
            if isinstance(target, ast.Attribute):
                fields.append(target.attr)
    return fields
