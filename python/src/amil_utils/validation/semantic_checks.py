"""Individual semantic check functions for Odoo module validation.

Each ``_check_eN`` function detects an error condition, and each
``_check_wN`` function detects a warning condition.  Functions are
invoked by the orchestration entry points in ``semantic.py``.
"""

from __future__ import annotations

import ast
import csv
import difflib
import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any

from amil_utils.validation.semantic_parsers import (
    AstCache,
    _KNOWN_GROUPS,
    _ParsedModel,
    _ParsedXml,
    _VIEW_META_FIELDS,
    _extract_model_info,
    _get_inherited_fields,
    _iter_py_trees,
    _load_known_models,
    _parse_xml_file,
)
from amil_utils.validation.semantic import ValidationIssue

if TYPE_CHECKING:
    from amil_utils.registry import ModelRegistry

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_e1(module_dir: Path) -> tuple[list[ValidationIssue], set[str]]:
    """E1: Python syntax validation via ast.parse()."""
    issues: list[ValidationIssue] = []
    failed_py: set[str] = set()

    for py_file in module_dir.rglob("*.py"):
        rel = str(py_file.relative_to(module_dir))
        try:
            source = py_file.read_text(encoding="utf-8")
            ast.parse(source, filename=rel)
        except SyntaxError as exc:
            issues.append(ValidationIssue(
                code="E1",
                severity="error",
                file=rel,
                line=exc.lineno,
                message=f"Python syntax error: {exc.msg}",
            ))
            failed_py.add(rel)

    return issues, failed_py


def _check_e2(module_dir: Path) -> tuple[list[ValidationIssue], set[str]]:
    """E2: XML well-formedness via xml.etree."""
    issues: list[ValidationIssue] = []
    failed_xml: set[str] = set()

    for xml_file in module_dir.rglob("*.xml"):
        rel = str(xml_file.relative_to(module_dir))
        try:
            ET.parse(xml_file)  # noqa: S314
        except ET.ParseError as exc:
            issues.append(ValidationIssue(
                code="E2",
                severity="error",
                file=rel,
                line=None,
                message=f"XML parse error: {exc}",
            ))
            failed_xml.add(rel)

    return issues, failed_xml


def _check_e3(
    parsed_xmls: list[_ParsedXml],
    module_models: dict[str, _ParsedModel],
    known_models: dict[str, Any],
) -> list[ValidationIssue]:
    """E3: View field references exist on model."""
    issues: list[ValidationIssue] = []

    for px in parsed_xmls:
        for model_name, field_name, line in px.field_refs:
            # Skip view metadata fields
            if field_name in _VIEW_META_FIELDS:
                continue

            model = module_models.get(model_name)
            if not model:
                continue  # Model not in this module, can't validate

            # Collect all known fields: own + inherited
            all_fields: set[str] = set(model.fields.keys())
            inherited = _get_inherited_fields(model.inherits, known_models, module_models)
            all_fields.update(inherited.keys())
            # Add common implicit fields
            all_fields.update({"id", "create_date", "create_uid", "write_date", "write_uid", "display_name"})

            if field_name not in all_fields:
                suggestion = None
                matches = difflib.get_close_matches(field_name, list(all_fields), n=1, cutoff=0.6)
                if matches:
                    suggestion = f"Did you mean '{matches[0]}'?"

                issues.append(ValidationIssue(
                    code="E3",
                    severity="error",
                    file=px.file_path,
                    line=line,
                    message=f"Field '{field_name}' not found on model '{model_name}'",
                    fixable=suggestion is not None,
                    suggestion=suggestion,
                ))

    return issues


def _check_e4(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
) -> list[ValidationIssue]:
    """E4: ACL CSV entries reference valid model XML IDs."""
    issues: list[ValidationIssue] = []

    # Build set of valid model XML IDs from parsed models
    valid_model_ids: set[str] = set()
    for model in module_models.values():
        # model_id:id format: model_{technical_name_with_underscores}
        xml_id = "model_" + model.model_name.replace(".", "_")
        valid_model_ids.add(xml_id)

    for csv_file in module_dir.rglob("ir.model.access.csv"):
        rel = str(csv_file.relative_to(module_dir))
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                continue
            for line_num, row in enumerate(reader, start=2):
                if len(row) < 4:
                    continue
                model_id = row[2].strip() if len(row) > 2 else ""
                if model_id and model_id not in valid_model_ids:
                    issues.append(ValidationIssue(
                        code="E4",
                        severity="error",
                        file=rel,
                        line=line_num,
                        message=f"ACL references unknown model XML ID '{model_id}'",
                    ))

    return issues


def _check_e5(parsed_xmls: list[_ParsedXml]) -> list[ValidationIssue]:
    """E5: XML ID uniqueness across data files."""
    issues: list[ValidationIssue] = []
    seen: dict[str, str] = {}  # xml_id -> first file

    for px in parsed_xmls:
        for xml_id in px.record_ids:
            if xml_id in seen:
                issues.append(ValidationIssue(
                    code="E5",
                    severity="error",
                    file=px.file_path,
                    line=None,
                    message=(
                        f"Duplicate XML ID '{xml_id}' "
                        f"(also in '{seen[xml_id]}')"
                    ),
                ))
            else:
                seen[xml_id] = px.file_path

    return issues


def _check_e6(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    parsed_xmls: list[_ParsedXml],
) -> list[ValidationIssue]:
    """E6: Manifest depends completeness."""
    issues: list[ValidationIssue] = []

    # Parse manifest
    manifest_path = module_dir / "__manifest__.py"
    if not manifest_path.exists():
        return issues

    try:
        manifest_src = manifest_path.read_text(encoding="utf-8")
        manifest = ast.literal_eval(manifest_src)
    except (SyntaxError, ValueError):
        return issues

    declared_depends: set[str] = set(manifest.get("depends", []))
    # 'base' is always implicitly available
    declared_depends.add("base")

    # Collect required modules from Python imports
    required_modules: set[str] = set()
    for model in module_models.values():
        for imp in model.imports:
            if imp not in declared_depends:
                required_modules.add(imp)

    # Collect required modules from XML ref="" attributes
    for px in parsed_xmls:
        for ext_ref in px.external_refs:
            parts = ext_ref.split(".", 1)
            if len(parts) == 2:
                module_name = parts[0]
                if module_name not in declared_depends:
                    required_modules.add(module_name)

    for mod in sorted(required_modules):
        issues.append(ValidationIssue(
            code="E6",
            severity="error",
            file="__manifest__.py",
            line=None,
            message=f"Module '{mod}' is referenced but not in manifest depends",
        ))

    return issues


def _check_w1(
    module_models: dict[str, _ParsedModel],
    known_models: dict[str, Any],
    registry: ModelRegistry | None,
) -> list[ValidationIssue]:
    """W1: Comodel references checked against registry and known models."""
    issues: list[ValidationIssue] = []
    all_module_model_names = set(module_models.keys())

    for model in module_models.values():
        for comodel in model.comodels:
            # Check known models
            if comodel in known_models:
                continue
            # Check within this module
            if comodel in all_module_model_names:
                continue
            # Check registry
            if registry and registry.show_model(comodel) is not None:
                continue

            issues.append(ValidationIssue(
                code="W1",
                severity="warning",
                file=model.file_path,
                line=None,
                message=f"Comodel '{comodel}' not found in known models or registry",
            ))

    return issues


def _check_w2(module_models: dict[str, _ParsedModel]) -> list[ValidationIssue]:
    """W2: @api.depends references validated."""
    issues: list[ValidationIssue] = []

    for model in module_models.values():
        all_fields: set[str] = set(model.fields.keys())
        # Add common implicit fields
        all_fields.update({"id", "create_date", "create_uid", "write_date", "write_uid", "display_name"})

        for method_name, dep_fields in model.depends_decorators:
            for dep_field in dep_fields:
                # Dot-notation: only validate first segment
                first_segment = dep_field.split(".")[0]
                if first_segment not in all_fields:
                    issues.append(ValidationIssue(
                        code="W2",
                        severity="warning",
                        file=model.file_path,
                        line=None,
                        message=(
                            f"@api.depends('{dep_field}') on '{method_name}': "
                            f"field '{first_segment}' not found on '{model.model_name}'"
                        ),
                    ))

    return issues


def _check_w3(
    parsed_xmls: list[_ParsedXml],
    module_xml_ids: set[str],
) -> list[ValidationIssue]:
    """W3: Security group references in views validated."""
    issues: list[ValidationIssue] = []

    for px in parsed_xmls:
        for group_ref, line in px.group_refs:
            # Known Odoo groups
            if group_ref in _KNOWN_GROUPS:
                continue
            # Groups defined in this module (without module prefix)
            if group_ref in module_xml_ids:
                continue
            # Check if group is module.id format and module part matches known
            if "." in group_ref:
                # External group -- we can't fully validate, but check known
                pass  # Falls through to warning

            issues.append(ValidationIssue(
                code="W3",
                severity="warning",
                file=px.file_path,
                line=line,
                message=f"Security group '{group_ref}' not found in known groups",
            ))

    return issues


def _check_w4(
    parsed_xmls: list[_ParsedXml],
    module_models: dict[str, _ParsedModel],
) -> list[ValidationIssue]:
    """W4: Record rule domain field references validated."""
    issues: list[ValidationIssue] = []

    for px in parsed_xmls:
        for model_ref, domain_str, line in px.rule_domains:
            # Convert model_ref (e.g., model_res_partner_ext) to model name
            model_name = model_ref.replace("model_", "", 1).replace("_", ".")
            model = module_models.get(model_name)
            if not model:
                continue

            all_fields: set[str] = set(model.fields.keys())
            all_fields.update({"id", "create_date", "create_uid", "write_date", "write_uid", "display_name"})

            # Extract field names from domain tuples: ('field_name', '=', value)
            field_pattern = re.compile(r"\(\s*['\"](\w+)['\"]")
            for match in field_pattern.finditer(domain_str):
                domain_field = match.group(1)
                if domain_field not in all_fields:
                    issues.append(ValidationIssue(
                        code="W4",
                        severity="warning",
                        file=px.file_path,
                        line=line,
                        message=(
                            f"Record rule domain references field '{domain_field}' "
                            f"not found on model '{model_name}'"
                        ),
                    ))

    return issues


# ---------------------------------------------------------------------------
# E7-E12 helper functions
# ---------------------------------------------------------------------------


def _has_api_decorator(func: ast.FunctionDef, decorator_name: str) -> bool:
    """Return True if *func* has ``@api.{decorator_name}`` decorator."""
    for dec in func.decorator_list:
        # @api.depends('x') -- Call form
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if (
                dec.func.attr == decorator_name
                and isinstance(dec.func.value, ast.Name)
                and dec.func.value.id == "api"
            ):
                return True
        # @api.model -- bare Attribute form (no call parens)
        if isinstance(dec, ast.Attribute):
            if (
                dec.attr == decorator_name
                and isinstance(dec.value, ast.Name)
                and dec.value.id == "api"
            ):
                return True
    return False


def _extract_constrains_decorator(dec: ast.expr) -> list[str] | None:
    """Extract field names from ``@api.constrains('f1', 'f2')``."""
    if not isinstance(dec, ast.Call):
        return None
    if not isinstance(dec.func, ast.Attribute):
        return None
    if dec.func.attr != "constrains":
        return None
    if not isinstance(dec.func.value, ast.Name) or dec.func.value.id != "api":
        return None
    result = []
    for arg in dec.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            result.append(arg.value)
    return result if result else None


# Attributes on self that are safe to access without iteration
# (they're ORM methods/properties, not field accesses)
_SELF_SAFE_ATTRS: frozenset[str] = frozenset({
    "env", "ids", "id", "ensure_one", "browse", "search",
    "with_context", "sudo", "mapped", "filtered", "sorted",
    "create", "write", "unlink", "read", "with_company",
    "_context", "_cr", "_uid", "pool",
})


def _accesses_self_field_without_loop(func: ast.FunctionDef) -> bool:
    """Return True if method body accesses ``self.X`` (read or write)
    without a ``for rec in self:`` loop.

    Both ``self.field = value`` (assignment) and ``self.field`` (read
    in expression) on a multi-record recordset are bugs.
    """
    has_self_field_access = False
    has_self_loop = False

    for stmt in ast.walk(func):
        # Check for: for rec in self: ...
        if isinstance(stmt, ast.For):
            if isinstance(stmt.iter, ast.Name) and stmt.iter.id == "self":
                has_self_loop = True

        # Check for: self.field = ... (assignment)
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    has_self_field_access = True

        # Check for: self.field (read in expression) -- Attribute access
        if isinstance(stmt, ast.Attribute):
            if (
                isinstance(stmt.value, ast.Name)
                and stmt.value.id == "self"
                and stmt.attr not in _SELF_SAFE_ATTRS
            ):
                has_self_field_access = True

    return has_self_field_access and not has_self_loop


def _has_raise_validation_error(func: ast.FunctionDef) -> bool:
    """Return True if method body contains ``raise ValidationError(...)``."""
    for node in ast.walk(func):
        if isinstance(node, ast.Raise) and node.exc is not None:
            exc = node.exc
            # raise ValidationError(...)
            if isinstance(exc, ast.Call):
                if isinstance(exc.func, ast.Name) and exc.func.id == "ValidationError":
                    return True
                # raise exceptions.ValidationError(...)
                if isinstance(exc.func, ast.Attribute) and exc.func.attr == "ValidationError":
                    return True
    return False


def _check_mapped_filtered_syntax(
    func: ast.FunctionDef,
) -> list[tuple[int, str]]:
    """Return ``(line, message)`` tuples for bad ``mapped()``/``filtered()`` calls."""
    errors: list[tuple[int, str]] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue

        method_name = node.func.attr
        if method_name == "mapped" and node.args:
            arg = node.args[0]
            # Bad: bare Name (missing quotes)
            if isinstance(arg, ast.Name):
                errors.append((
                    node.lineno,
                    f"mapped({arg.id}) -- missing quotes, should be mapped('{arg.id}')",
                ))
        elif method_name == "filtered" and node.args:
            arg = node.args[0]
            # Bad: string with comparison operator
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if any(op in arg.value for op in ("==", "!=", ">", "<", ">=", "<=")):
                    errors.append((
                        node.lineno,
                        f"filtered('{arg.value}') -- use lambda instead of string comparison",
                    ))
    return errors


def _has_self_mutating_call(
    func: ast.FunctionDef,
) -> list[tuple[int, str]]:
    """Detect ``self.write()``/``self.create()``/``self.unlink()`` calls.

    Only flags calls where the receiver is literally ``self``, not
    variable aliases or ``self.env[...]``.
    """
    bad_methods = frozenset({"write", "create", "unlink"})
    errors: list[tuple[int, str]] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in bad_methods:
            continue
        # Check receiver is literally `self` (not self.env['...'].method())
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
            errors.append((
                node.lineno,
                f"self.{node.func.attr}() inside compute method causes infinite recursion",
            ))
    return errors


def _get_assigned_fields_in_method(func: ast.FunctionDef) -> set[str]:
    """Return set of field names assigned as ``record.field = ...`` anywhere
    in the method body (via any variable name, not just ``self``).
    """
    fields_set: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    fields_set.add(target.attr)
    return fields_set


def _get_for_loop_var_over_self(func: ast.FunctionDef) -> str | None:
    """Return the loop variable name from ``for <var> in self:``
    if present, else None.
    """
    for node in ast.walk(func):
        if isinstance(node, ast.For):
            if isinstance(node.iter, ast.Name) and node.iter.id == "self":
                if isinstance(node.target, ast.Name):
                    return node.target.id
    return None


def _bare_field_names_in_for_body(
    func: ast.FunctionDef,
    model_fields: set[str],
) -> list[tuple[int, str]]:
    """Find bare Name nodes in Load context inside for-loop body that
    match model field names.

    Returns ``(line, field_name)`` tuples.
    """
    errors: list[tuple[int, str]] = []

    for node in ast.walk(func):
        if not isinstance(node, ast.For):
            continue
        if not (isinstance(node.iter, ast.Name) and node.iter.id == "self"):
            continue

        # Get the loop variable name(s) (e.g., 'rec', or 'idx, rec' for tuple unpacking)
        loop_vars: set[str] = set()
        if isinstance(node.target, ast.Name):
            loop_vars.add(node.target.id)
        elif isinstance(node.target, ast.Tuple):
            for elt in node.target.elts:
                if isinstance(elt, ast.Name):
                    loop_vars.add(elt.id)

        # Collect all names that are assigned to (Store context) inside the loop
        assigned_names: set[str] = set()
        for inner in ast.walk(node):
            if isinstance(inner, ast.Assign):
                for t in inner.targets:
                    if isinstance(t, ast.Name):
                        assigned_names.add(t.id)

        # Walk the for-loop body for bare Name nodes in Load context
        for inner in ast.walk(node):
            if isinstance(inner, ast.Name) and isinstance(inner.ctx, ast.Load):
                name = inner.id
                # Skip: not a model field, or is loop var, or is 'self', or common builtins
                if name not in model_fields:
                    continue
                if name in loop_vars or name == "self":
                    continue
                # Skip common builtins/imports that might match field names
                if name in {"True", "False", "None", "super", "len", "sum", "min", "max", "abs", "int", "float", "str", "list", "dict", "set", "range", "print", "type", "isinstance", "hasattr", "getattr"}:
                    continue
                errors.append((inner.lineno, name))
    return errors


def _read_sidecar_targets(module_dir: Path) -> dict[str, list[str]]:
    """Read ``.amil-stubs.json`` sidecar and return
    ``{method_name: [target_fields]}`` mapping.
    """
    sidecar_path = module_dir / ".amil-stubs.json"
    if not sidecar_path.exists():
        return {}
    try:
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    result: dict[str, list[str]] = {}
    for stub in data.get("stubs", []):
        method = stub.get("method", "")
        targets = stub.get("target_fields", [])
        if method and targets:
            result[method] = targets
    return result


# ---------------------------------------------------------------------------
# E7-E12 check functions
# ---------------------------------------------------------------------------


def _check_e7(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    ast_cache: AstCache | None = None,
) -> list[ValidationIssue]:
    """E7: Missing self iteration in multi-record method.

    Methods with ``@api.depends`` or ``@api.constrains`` that assign
    to ``self.field`` without a ``for rec in self:`` loop are flagged.
    ``@api.model`` methods are exempt.
    """
    issues: list[ValidationIssue] = []

    for rel, tree in _iter_py_trees(module_dir, ast_cache):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_info = _extract_model_info(node, rel)
            if model_info is None:
                continue

            for stmt in node.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                # Only check methods with @api.depends or @api.constrains
                if not (_has_api_decorator(stmt, "depends") or _has_api_decorator(stmt, "constrains")):
                    continue
                # @api.model is exempt
                if _has_api_decorator(stmt, "model"):
                    continue

                if _accesses_self_field_without_loop(stmt):
                    issues.append(ValidationIssue(
                        code="E7",
                        severity="error",
                        file=rel,
                        line=stmt.lineno,
                        message=(
                            f"Method '{stmt.name}' assigns to self.field "
                            f"without iterating over self (for rec in self)"
                        ),
                    ))

    return issues


def _check_e8(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    ast_cache: AstCache | None = None,
) -> list[ValidationIssue]:
    """E8: Compute method doesn't set target field.

    Reads ``.amil-stubs.json`` sidecar for ``target_fields``.
    Falls back to ``_compute_X`` -> field ``X`` naming convention.
    """
    issues: list[ValidationIssue] = []
    sidecar_targets = _read_sidecar_targets(module_dir)

    for rel, tree in _iter_py_trees(module_dir, ast_cache):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_info = _extract_model_info(node, rel)
            if model_info is None:
                continue

            for stmt in node.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                if not _has_api_decorator(stmt, "depends"):
                    continue

                # Determine target fields
                method_name = stmt.name
                target_fields: list[str] = []

                # NEW-04: Odoo built-in fields that can be overridden via compute
                _BUILTIN_COMPUTE_FIELDS = {"display_name"}

                if method_name in sidecar_targets:
                    target_fields = sidecar_targets[method_name]
                elif method_name.startswith("_compute_"):
                    inferred = method_name[len("_compute_"):]
                    if inferred and (inferred in model_info.fields or inferred in _BUILTIN_COMPUTE_FIELDS):
                        target_fields = [inferred]

                if not target_fields:
                    issues.append(ValidationIssue(
                        code="W8",
                        severity="warning",
                        file=rel,
                        line=stmt.lineno,
                        message=(
                            f"Cannot determine target field(s) for compute "
                            f"method '{method_name}' — E8 check skipped"
                        ),
                    ))
                    continue

                # Check which targets are assigned in the method body
                assigned = _get_assigned_fields_in_method(stmt)
                missing = [f for f in target_fields if f not in assigned]

                if missing:
                    issues.append(ValidationIssue(
                        code="E8",
                        severity="error",
                        file=rel,
                        line=stmt.lineno,
                        message=(
                            f"Compute method '{method_name}' never assigns "
                            f"to target field(s): {', '.join(missing)}"
                        ),
                    ))

    return issues


def _check_e9(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    ast_cache: AstCache | None = None,
) -> list[ValidationIssue]:
    """E9: Constraint method doesn't raise ValidationError.

    Methods with ``@api.constrains`` must contain at least one
    ``raise ValidationError(...)`` statement.
    """
    issues: list[ValidationIssue] = []

    for rel, tree in _iter_py_trees(module_dir, ast_cache):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_info = _extract_model_info(node, rel)
            if model_info is None:
                continue

            for stmt in node.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                if not _has_api_decorator(stmt, "constrains"):
                    continue

                if not _has_raise_validation_error(stmt):
                    issues.append(ValidationIssue(
                        code="E9",
                        severity="error",
                        file=rel,
                        line=stmt.lineno,
                        message=(
                            f"Constraint method '{stmt.name}' never raises "
                            f"ValidationError"
                        ),
                    ))

    return issues


def _check_e10(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    ast_cache: AstCache | None = None,
) -> list[ValidationIssue]:
    """E10: Bare field access without record variable.

    Inside ``for rec in self:`` loops of ``@api.depends``/``@api.constrains``
    methods, bare Name nodes in Load context matching model field names
    are flagged.
    """
    issues: list[ValidationIssue] = []

    for rel, tree in _iter_py_trees(module_dir, ast_cache):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_info = _extract_model_info(node, rel)
            if model_info is None:
                continue

            model_field_names = set(model_info.fields.keys())

            for stmt in node.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                if not (_has_api_decorator(stmt, "depends") or _has_api_decorator(stmt, "constrains")):
                    continue

                bare_refs = _bare_field_names_in_for_body(stmt, model_field_names)
                for lineno, field_name in bare_refs:
                    issues.append(ValidationIssue(
                        code="E10",
                        severity="error",
                        file=rel,
                        line=lineno,
                        message=(
                            f"Bare field reference '{field_name}' -- "
                            f"use record.{field_name} instead"
                        ),
                    ))

    return issues


def _check_e11(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    ast_cache: AstCache | None = None,
) -> list[ValidationIssue]:
    """E11: Wrong mapped/filtered syntax.

    ``mapped()`` with bare Name argument (missing quotes) and
    ``filtered()`` with string comparison expression.
    """
    issues: list[ValidationIssue] = []

    for rel, tree in _iter_py_trees(module_dir, ast_cache):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_info = _extract_model_info(node, rel)
            if model_info is None:
                continue

            for stmt in node.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                if not (_has_api_decorator(stmt, "depends") or _has_api_decorator(stmt, "constrains")):
                    continue

                bad_calls = _check_mapped_filtered_syntax(stmt)
                for lineno, msg in bad_calls:
                    issues.append(ValidationIssue(
                        code="E11",
                        severity="error",
                        file=rel,
                        line=lineno,
                        message=msg,
                    ))

    return issues


def _check_e12(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    ast_cache: AstCache | None = None,
) -> list[ValidationIssue]:
    """E12: write()/create()/unlink() inside @api.depends method.

    Only checks direct ``self.write()``/``self.create()``/``self.unlink()``
    calls, not variable aliases or ``self.env[...].create()``.
    """
    issues: list[ValidationIssue] = []

    for rel, tree in _iter_py_trees(module_dir, ast_cache):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_info = _extract_model_info(node, rel)
            if model_info is None:
                continue

            for stmt in node.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                # E12 only applies to @api.depends methods (compute)
                if not _has_api_decorator(stmt, "depends"):
                    continue

                bad_calls = _has_self_mutating_call(stmt)
                for lineno, msg in bad_calls:
                    issues.append(ValidationIssue(
                        code="E12",
                        severity="error",
                        file=rel,
                        line=lineno,
                        message=msg,
                    ))

    return issues


# ---------------------------------------------------------------------------
# E13-E16, W5 check functions
# ---------------------------------------------------------------------------


def _has_super_call(func: ast.FunctionDef) -> bool:
    """Return True if *func* body contains a ``super()`` call.

    Detects both Python 3 style (``super().method()``) and old style
    (``super(ClassName, self).method()``).
    """
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        # super() -- bare call
        if isinstance(node.func, ast.Name) and node.func.id == "super":
            return True
        # super().create(...) -- Attribute on super() call
        if isinstance(node.func, ast.Attribute):
            value = node.func.value
            if isinstance(value, ast.Call):
                if isinstance(value.func, ast.Name) and value.func.id == "super":
                    return True
    return False


def _check_e13(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    ast_cache: AstCache | None = None,
) -> list[ValidationIssue]:
    """E13: Override method (create/write) doesn't call super().

    Only checks methods inside classes with ``_name`` or ``_inherit``.
    """
    issues: list[ValidationIssue] = []

    for rel, tree in _iter_py_trees(module_dir, ast_cache):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_info = _extract_model_info(node, rel)
            if model_info is None:
                continue

            for stmt in node.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                if stmt.name not in ("create", "write"):
                    continue

                if not _has_super_call(stmt):
                    issues.append(ValidationIssue(
                        code="E13",
                        severity="error",
                        file=rel,
                        line=stmt.lineno,
                        message=(
                            f"Override '{stmt.name}' does not call super()"
                        ),
                    ))

    return issues


def _check_w5(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    ast_cache: AstCache | None = None,
) -> list[ValidationIssue]:
    """W5: Action method modifies state without checking current state.

    Checks ``action_*`` methods that assign to ``self.state`` or
    ``record.state`` for a preceding ``if`` check on ``state`` or
    ``self.filtered(lambda ...)`` with state reference.
    """
    issues: list[ValidationIssue] = []

    for rel, tree in _iter_py_trees(module_dir, ast_cache):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_info = _extract_model_info(node, rel)
            if model_info is None:
                continue

            for stmt in node.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                if not stmt.name.startswith("action_"):
                    continue

                # Check if method assigns to state
                has_state_assign = False
                for inner in ast.walk(stmt):
                    if isinstance(inner, ast.Assign):
                        for target in inner.targets:
                            if (
                                isinstance(target, ast.Attribute)
                                and target.attr == "state"
                            ):
                                has_state_assign = True

                if not has_state_assign:
                    continue  # No state assignment, exempt

                # Check for state precondition: if-check on state or filtered(lambda)
                has_state_check = _has_state_precondition(stmt)

                if not has_state_check:
                    issues.append(ValidationIssue(
                        code="W5",
                        severity="warning",
                        file=rel,
                        line=stmt.lineno,
                        message=(
                            f"Action method '{stmt.name}' modifies state "
                            f"without checking current state"
                        ),
                    ))

    return issues


def _has_state_precondition(func: ast.FunctionDef) -> bool:
    """Return True if *func* contains a state precondition check.

    Detects:
    - ``if self.state ...`` or ``if rec.state ...``
    - ``self.filtered(lambda r: r.state ...)``
    """
    for node in ast.walk(func):
        # Check for: if <expr>.state ...
        if isinstance(node, ast.If):
            if _references_state_attr(node.test):
                return True

        # Check for: self.filtered(lambda r: r.state ...)
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "filtered"
                and node.args
            ):
                arg = node.args[0]
                if isinstance(arg, ast.Lambda):
                    if _references_state_attr(arg.body):
                        return True

    return False


def _references_state_attr(node: ast.expr) -> bool:
    """Return True if *node* contains an ``X.state`` attribute access."""
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr == "state":
            return True
    return False


def _check_e15(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    ast_cache: AstCache | None = None,
) -> list[ValidationIssue]:
    """E15: Cron method ``_cron_*`` missing ``@api.model`` decorator."""
    issues: list[ValidationIssue] = []

    for rel, tree in _iter_py_trees(module_dir, ast_cache):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_info = _extract_model_info(node, rel)
            if model_info is None:
                continue

            for stmt in node.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                if not stmt.name.startswith("_cron_"):
                    continue

                if not _has_api_decorator(stmt, "model"):
                    issues.append(ValidationIssue(
                        code="E15",
                        severity="error",
                        file=rel,
                        line=stmt.lineno,
                        message=(
                            f"Cron method '{stmt.name}' missing @api.model decorator"
                        ),
                    ))

    return issues


def _check_e16(
    module_dir: Path,
    module_models: dict[str, _ParsedModel],
    ast_cache: AstCache | None = None,
) -> list[ValidationIssue]:
    """E16: Exclusion zone violation -- template code outside markers modified.

    Compares filled ``.py`` files against ``.amil-skeleton/`` baseline.
    Lines outside ``BUSINESS LOGIC START/END`` marker zones must match.
    Silently returns ``[]`` when skeleton directory does not exist.

    Since stub filling may add/remove lines inside marker zones, we extract
    the lines OUTSIDE zones from both files and compare those sequences.
    """
    from amil_utils.logic_writer.stub_detector import _find_stub_zones

    issues: list[ValidationIssue] = []

    skeleton_dir = module_dir.parent / ".amil-skeleton" / module_dir.name
    if not skeleton_dir.exists():
        return issues

    for py_file in module_dir.rglob("*.py"):
        rel = str(py_file.relative_to(module_dir))
        skeleton_file = skeleton_dir / rel
        if not skeleton_file.exists():
            continue

        try:
            filled_lines = py_file.read_text(encoding="utf-8").splitlines()
            skeleton_lines = skeleton_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        # Extract lines outside stub zones from both files
        skel_outside = _lines_outside_zones(skeleton_lines)
        fill_outside = _lines_outside_zones(filled_lines)

        # Compare the sequences of outside-zone lines
        max_count = max(len(skel_outside), len(fill_outside))
        for i in range(max_count):
            skel_item = skel_outside[i] if i < len(skel_outside) else (0, "")
            fill_item = fill_outside[i] if i < len(fill_outside) else (0, "")

            if skel_item[1].strip() != fill_item[1].strip():
                # Report the line number from the filled file
                line_num = fill_item[0] if fill_item[0] else skel_item[0]
                issues.append(ValidationIssue(
                    code="E16",
                    severity="error",
                    file=rel,
                    line=line_num,
                    message=(
                        f"Template code modified outside BUSINESS LOGIC zone "
                        f"(line {line_num})"
                    ),
                ))

    return issues


def _lines_outside_zones(
    source_lines: list[str],
) -> list[tuple[int, str]]:
    """Return ``(line_number, text)`` tuples for lines outside marker zones.

    Marker lines (START/END) are considered outside the zone (they are
    template-generated) but the content between them is inside.
    """
    from amil_utils.logic_writer.stub_detector import _find_stub_zones

    zones = _find_stub_zones(source_lines)

    # Build set of line numbers strictly INSIDE zones (excluding markers)
    inside_lines: set[int] = set()
    for zone in zones:
        # Lines between START and END markers (exclusive of markers themselves)
        for ln in range(zone["start_line"] + 1, zone["end_line"]):
            inside_lines.add(ln)

    result: list[tuple[int, str]] = []
    for idx, line in enumerate(source_lines, start=1):
        if idx not in inside_lines:
            result.append((idx, line))
    return result


# ---------------------------------------------------------------------------
# E17: Extension xpath references non-existent base field
# W6: Unknown base model warning
# ---------------------------------------------------------------------------

_XPATH_FIELD_RE = re.compile(r"field\[@name=['\"](\w+)['\"]\]")


def _check_e17(
    output_dir: Path,
    known_models: dict[str, Any],
    registry: "ModelRegistry | None" = None,
) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    """E17: Extension xpath references non-existent base field.

    Returns (errors, warnings) tuple.
    Errors for Tier 1/2 (known/registry models with bad field refs).
    Warnings (W6) for Tier 3 (unknown models -- cannot validate).
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # Track which unknown models we've already warned about to avoid duplicates
    warned_models: set[str] = set()

    for xml_path in output_dir.rglob("*.xml"):
        rel = str(xml_path.relative_to(output_dir))
        try:
            tree = ET.parse(xml_path)  # noqa: S314
        except ET.ParseError:
            continue  # E2 already catches parse errors

        root = tree.getroot()
        for record in root.iter("record"):
            # Only check ir.ui.view records
            if record.get("model") != "ir.ui.view":
                continue

            # Check if this is an inherited view (has inherit_id field with ref)
            inherit_field = None
            model_field = None
            arch_field = None
            for field_elem in record.findall("field"):
                field_name = field_elem.get("name")
                if field_name == "inherit_id" and field_elem.get("ref"):
                    inherit_field = field_elem
                elif field_name == "model":
                    model_field = field_elem
                elif field_name == "arch":
                    arch_field = field_elem

            # Skip non-inherited views
            if inherit_field is None or model_field is None or arch_field is None:
                continue

            model_name = (model_field.text or "").strip()
            if not model_name:
                continue

            # Collect all field references from xpath expressions inside arch
            for xpath_elem in arch_field.iter("xpath"):
                expr = xpath_elem.get("expr", "")
                matches = _XPATH_FIELD_RE.findall(expr)
                if not matches:
                    # Non-field xpath (page, group, etc.) -- skip
                    continue

                for field_ref in matches:
                    # Determine which tier the model belongs to
                    known_entry = known_models.get(model_name)
                    registry_entry = None
                    if registry is not None:
                        registry_entry = registry.show_model(model_name)

                    if known_entry is not None:
                        # Tier 1: Known Odoo model
                        known_fields = known_entry.get("fields", {})
                        if field_ref not in known_fields:
                            errors.append(ValidationIssue(
                                code="E17",
                                severity="error",
                                file=rel,
                                line=None,
                                message=(
                                    f"xpath references field '{field_ref}' not "
                                    f"found on model '{model_name}'"
                                ),
                            ))
                    elif registry_entry is not None:
                        # Tier 2: Registry model
                        reg_fields = registry_entry.fields
                        if field_ref not in reg_fields:
                            errors.append(ValidationIssue(
                                code="E17",
                                severity="error",
                                file=rel,
                                line=None,
                                message=(
                                    f"xpath references field '{field_ref}' not "
                                    f"found on model '{model_name}'"
                                ),
                            ))
                    else:
                        # Tier 3: Unknown model -- warn once per model
                        if model_name not in warned_models:
                            warned_models.add(model_name)
                            warnings.append(ValidationIssue(
                                code="W6",
                                severity="warning",
                                file=rel,
                                line=None,
                                message=(
                                    f"Base model '{model_name}' not in known "
                                    f"models or registry. Cannot validate "
                                    f"field references."
                                ),
                            ))

    return errors, warnings


# ---------------------------------------------------------------------------
# E23: Portal ownership path validation
# ---------------------------------------------------------------------------


def _resolve_model_fields(
    model_name: str,
    spec: dict[str, Any] | None,
    registry: "ModelRegistry | None",
) -> dict[str, dict[str, Any]] | None:
    """Resolve a model's fields from spec models or registry.

    Returns dict of field_name -> field_info, or None if model not found.
    """
    if spec is not None:
        for model in spec.get("models", []):
            if model.get("name") == model_name:
                return {f["name"]: f for f in model.get("fields", [])}
    if registry is not None:
        entry = registry.show_model(model_name)
        if entry is not None:
            return entry.fields
    return None


def _check_e23(
    module_dir: Path,
    spec: dict[str, Any] | None = None,
    registry: "ModelRegistry | None" = None,
) -> list[ValidationIssue]:
    """E23: Portal ownership path validation.

    For each portal page, validates that the ownership field path
    traverses through models and terminates at res.users.

    Returns a list of ValidationIssue (errors for bad paths, warnings
    for unresolvable models).
    """
    issues: list[ValidationIssue] = []

    if spec is None:
        return issues

    portal = spec.get("portal")
    if not portal:
        return issues

    # Handle both Pydantic model and dict
    if hasattr(portal, "model_dump"):
        portal_dict = portal.model_dump()
    elif isinstance(portal, dict):
        portal_dict = portal
    else:
        return issues

    pages = portal_dict.get("pages", [])

    for page in pages:
        page_id = page.get("id", "unknown")
        page_model = page.get("model", "")
        ownership = page.get("ownership", "")
        if not ownership or not page_model:
            continue

        hops = ownership.split(".")
        current_model = page_model

        # Try to resolve the starting model
        fields = _resolve_model_fields(current_model, spec, registry)
        if fields is None:
            issues.append(ValidationIssue(
                code="W7",
                severity="warning",
                file="portal",
                line=None,
                message=(
                    f"Cannot validate ownership path '{ownership}' on page "
                    f"'{page_id}' -- model '{current_model}' not in spec or registry"
                ),
            ))
            continue

        path_valid = True
        terminal_model = current_model

        for i, hop in enumerate(hops):
            if fields is None:
                # Intermediate model not resolvable
                issues.append(ValidationIssue(
                    code="W7",
                    severity="warning",
                    file="portal",
                    line=None,
                    message=(
                        f"Cannot validate ownership path '{ownership}' on page "
                        f"'{page_id}' -- model '{current_model}' not in spec or registry"
                    ),
                ))
                path_valid = False
                break

            field_info = fields.get(hop)
            if field_info is None:
                issues.append(ValidationIssue(
                    code="E23",
                    severity="error",
                    file="portal",
                    line=None,
                    message=(
                        f"Ownership path '{ownership}' on page '{page_id}': "
                        f"field '{hop}' not found on model '{current_model}'"
                    ),
                ))
                path_valid = False
                break

            # Check if field is relational
            field_type = field_info.get("type", "")
            comodel = field_info.get("comodel_name", "")

            if field_type in ("Many2one", "One2many", "Many2many") and comodel:
                terminal_model = comodel
                if i < len(hops) - 1:
                    # More hops remain -- resolve the next model
                    current_model = comodel
                    fields = _resolve_model_fields(current_model, spec, registry)
            else:
                # Non-relational field at intermediate position
                if i < len(hops) - 1:
                    issues.append(ValidationIssue(
                        code="E23",
                        severity="error",
                        file="portal",
                        line=None,
                        message=(
                            f"Ownership path '{ownership}' on page '{page_id}': "
                            f"field '{hop}' on model '{current_model}' is not "
                            f"relational (type: {field_type})"
                        ),
                    ))
                    path_valid = False
                    break
                else:
                    # Terminal non-relational field -- path doesn't point to res.users
                    terminal_model = current_model

        if not path_valid:
            continue

        # Check that path terminates at res.users
        if terminal_model != "res.users":
            issues.append(ValidationIssue(
                code="E23",
                severity="error",
                file="portal",
                line=None,
                message=(
                    f"Ownership path '{ownership}' on page '{page_id}' does not "
                    f"terminate at res.users (terminates at '{terminal_model}')"
                ),
            ))

    return issues


# ---------------------------------------------------------------------------
# E24: Bulk operation source_model validation
# ---------------------------------------------------------------------------


def _model_exists_in_spec(model_name: str, spec: dict[str, Any] | None) -> bool:
    """Check if a model name exists in spec['models']."""
    if spec is None:
        return False
    return any(m.get("name") == model_name for m in spec.get("models", []))


def _model_exists_in_registry(
    model_name: str, registry: "ModelRegistry | None"
) -> bool:
    """Check if a model name exists in registry."""
    if registry is None:
        return False
    return registry.show_model(model_name) is not None


def _check_e24(
    output_dir: Path,
    spec: dict[str, Any] | None = None,
    registry: "ModelRegistry | None" = None,
) -> list[ValidationIssue]:
    """E24: Bulk operation source_model validation.

    For each bulk operation, validates that source_model exists in
    spec models or in the registry.
    """
    if spec is None:
        return []
    issues: list[ValidationIssue] = []
    for op in spec.get("bulk_operations", []):
        source_model = op.get("source_model", "")
        op_id = op.get("id", "unknown")
        if not _model_exists_in_spec(source_model, spec) and not _model_exists_in_registry(
            source_model, registry
        ):
            issues.append(
                ValidationIssue(
                    code="E24",
                    severity="error",
                    file="bulk_operations",
                    line=None,
                    message=(
                        f"Bulk operation '{op_id}': source_model '{source_model}' "
                        f"not found in spec models or registry"
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# E25: Bulk operation create_model validation
# ---------------------------------------------------------------------------


def _check_e25(
    output_dir: Path,
    spec: dict[str, Any] | None = None,
    registry: "ModelRegistry | None" = None,
) -> list[ValidationIssue]:
    """E25: Bulk operation create_model validation.

    For each create_related bulk operation, validates that create_model
    exists in spec models or in the registry.
    """
    if spec is None:
        return []
    issues: list[ValidationIssue] = []
    for op in spec.get("bulk_operations", []):
        if op.get("operation") != "create_related":
            continue
        create_model = op.get("create_model", "")
        op_id = op.get("id", "unknown")
        if not create_model:
            continue
        if not _model_exists_in_spec(create_model, spec) and not _model_exists_in_registry(
            create_model, registry
        ):
            issues.append(
                ValidationIssue(
                    code="E25",
                    severity="error",
                    file="bulk_operations",
                    line=None,
                    message=(
                        f"Bulk operation '{op_id}': create_model '{create_model}' "
                        f"not found in spec models or registry"
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# W8: Bulk operation create_fields reference validation
# ---------------------------------------------------------------------------


def _check_w8(
    output_dir: Path,
    spec: dict[str, Any] | None = None,
    registry: "ModelRegistry | None" = None,
) -> list[ValidationIssue]:
    """W8: Bulk operation create_fields source reference validation.

    For each create_related bulk operation with create_fields,
    validates that source.X references point to existing fields
    in the source model.
    """
    if spec is None:
        return []
    issues: list[ValidationIssue] = []
    for op in spec.get("bulk_operations", []):
        if op.get("operation") != "create_related":
            continue
        create_fields = op.get("create_fields", {})
        if not create_fields:
            continue
        source_model = op.get("source_model", "")
        op_id = op.get("id", "unknown")

        # Resolve source model fields
        source_fields = _resolve_model_fields(source_model, spec, registry)

        for _target_field, source_ref in create_fields.items():
            if not source_ref.startswith("source."):
                continue
            field_name = source_ref[len("source."):]
            # "id" is always valid (every Odoo record has id)
            if field_name == "id":
                continue
            if source_fields is not None and field_name not in source_fields:
                issues.append(
                    ValidationIssue(
                        code="W8",
                        severity="warning",
                        file="bulk_operations",
                        line=None,
                        message=(
                            f"Bulk operation '{op_id}': create_fields references "
                            f"source field '{field_name}' not found in "
                            f"source model '{source_model}'"
                        ),
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# W9: Comodel depends cross-validation
# ---------------------------------------------------------------------------

# Standard Odoo models that don't require an explicit depends entry
_COMODEL_NO_DEPENDS: frozenset[str] = frozenset({
    "res.users", "res.partner", "res.company", "res.groups",
    "res.currency", "ir.attachment", "ir.cron",
    "mail.thread", "mail.activity.mixin", "portal.mixin",
    "utm.mixin", "image.mixin",
})


def _parse_manifest_depends(output_dir: Path) -> set[str] | None:
    """Parse __manifest__.py and return the depends set, or None on failure."""
    manifest_path = output_dir / "__manifest__.py"
    if not manifest_path.exists():
        return None
    try:
        manifest_src = manifest_path.read_text(encoding="utf-8")
        manifest = ast.literal_eval(manifest_src)
    except (SyntaxError, ValueError):
        return None
    depends = set(manifest.get("depends", []))
    depends.add("base")
    return depends


def _extract_comodel_module_prefix(comodel: str) -> str | None:
    """Extract the module prefix from a comodel name.

    Examples: 'sale.order' -> 'sale', 'account.move' -> 'account'.
    Returns None if the comodel has no dot separator.
    """
    parts = comodel.split(".")
    if len(parts) < 2:
        return None
    return parts[0]


def _prefix_covered_by_depends(prefix: str, declared_depends: set[str]) -> bool:
    """Check if a comodel prefix is covered by any declared dependency.

    Matches exact module name or modules that start with the prefix
    followed by ``_`` (e.g., prefix ``uni`` matches ``uni_core``).
    """
    if prefix in declared_depends:
        return True
    prefix_underscore = prefix + "_"
    return any(dep.startswith(prefix_underscore) for dep in declared_depends)


def check_comodel_depends(output_dir: Path) -> list[ValidationIssue]:
    """W9: Verify all comodel references have corresponding depends entries.

    Parses __manifest__.py for depends and all .py model files for
    comodel_name= references. Flags comodels whose module prefix
    is not in the depends list.
    """
    declared_depends = _parse_manifest_depends(output_dir)
    if declared_depends is None:
        return []

    module_name = output_dir.name
    issues: list[ValidationIssue] = []
    missing_prefixes: set[str] = set()

    for py_file in output_dir.rglob("*.py"):
        rel = str(py_file.relative_to(output_dir))
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=rel)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.keyword):
                continue
            if node.arg != "comodel_name":
                continue
            if not isinstance(node.value, ast.Constant):
                continue
            comodel = str(node.value.value)
            if comodel in _COMODEL_NO_DEPENDS:
                continue
            prefix = _extract_comodel_module_prefix(comodel)
            if prefix is None:
                continue
            if prefix == module_name:
                continue
            if _prefix_covered_by_depends(prefix, declared_depends):
                continue
            if prefix not in missing_prefixes:
                missing_prefixes.add(prefix)
                issues.append(ValidationIssue(
                    code="W9",
                    severity="warning",
                    file=rel,
                    line=node.value.lineno if hasattr(node.value, "lineno") else None,
                    message=(
                        f"Comodel '{comodel}' implies dependency on "
                        f"module '{prefix}', but '{prefix}' is not in "
                        f"manifest depends"
                    ),
                ))

    return issues


def _check_w10(module_dir: Path, spec: dict, **kwargs) -> list[dict]:
    """Computed field used in search view without store=True."""
    issues = []
    for model in spec.get("models", []):
        computed = {f["name"] for f in model.get("fields", []) if f.get("compute")}
        stored_computed = {f["name"] for f in model.get("fields", []) if f.get("compute") and f.get("store")}
        unstored = computed - stored_computed
        if not unstored:
            continue
        # Check search views for references to unstored computes
        model_var = model["name"].replace(".", "_")
        search_view = module_dir / "views" / f"{model_var}_views.xml"
        if not search_view.exists():
            continue
        content = search_view.read_text(encoding="utf-8")
        for field_name in unstored:
            if f'name="{field_name}"' in content and "<search" in content:
                issues.append({
                    "code": "W10",
                    "message": f"Computed field '{field_name}' on {model['name']} is used in search view but lacks store=True",
                    "model": model["name"],
                    "field": field_name,
                    "severity": "warning",
                })
    return issues


def _check_w11(module_dir: Path, spec: dict, **kwargs) -> list[dict]:
    """_order references non-existent field."""
    issues = []
    implicit_fields = {"id", "create_date", "write_date", "create_uid", "write_uid", "display_name"}
    for model in spec.get("models", []):
        order = model.get("order") or model.get("_order", "")
        if not order:
            continue
        field_names = {f["name"] for f in model.get("fields", [])} | implicit_fields
        for part in order.split(","):
            order_field = part.strip().split()[0].strip()
            if order_field and order_field not in field_names:
                issues.append({
                    "code": "W11",
                    "message": f"_order references '{order_field}' which is not a field on {model['name']}",
                    "model": model["name"],
                    "field": order_field,
                    "severity": "warning",
                })
    return issues


def _check_w12(module_dir: Path, spec: dict, **kwargs) -> list[dict]:
    """Required Many2one with incompatible ondelete."""
    issues = []
    for model in spec.get("models", []):
        for field in model.get("fields", []):
            if field.get("type") != "Many2one":
                continue
            if field.get("required") and field.get("ondelete") in ("set null", "set default"):
                issues.append({
                    "code": "W12",
                    "message": f"Field '{field['name']}' on {model['name']} is required=True but ondelete='{field['ondelete']}' — incompatible",
                    "model": model["name"],
                    "field": field["name"],
                    "severity": "warning",
                })
    return issues
