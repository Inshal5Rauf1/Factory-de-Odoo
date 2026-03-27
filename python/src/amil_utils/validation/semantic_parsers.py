"""Parsing helpers for semantic validation.

Extracts model definitions from Python (via ``ast``) and record/field
references from XML (via ``xml.etree.ElementTree``).  All parsers are
single-pass and return structured dataclass instances consumed by the
check functions in ``semantic_checks.py``.
"""

from __future__ import annotations

import ast
import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

# Mapping of relative file path -> parsed AST tree, built once in Phase 2
# and reused by Phase 3 checks to avoid redundant file I/O and parsing.
AstCache = dict[str, ast.Module]


# ---------------------------------------------------------------------------
# Internal index types (mutable, used only during validation)
# ---------------------------------------------------------------------------


@dataclass
class _ParsedModel:
    model_name: str
    fields: dict[str, dict[str, Any]]  # field_name -> {type, comodel_name, ...}
    comodels: list[str]
    inherits: list[str]
    imports: list[str]  # odoo.addons.X module names
    depends_decorators: list[tuple[str, list[str]]]  # (method, [field_names])
    file_path: str
    line_numbers: dict[str, int] = field(default_factory=dict)


@dataclass
class _ParsedXml:
    record_ids: dict[str, int]  # xml_id -> line
    field_refs: list[tuple[str, str, int]]  # (model, field_name, line)
    group_refs: list[tuple[str, int]]  # (group_ref, line)
    external_refs: list[str]  # module.xml_id
    rule_domains: list[tuple[str, str, int]]  # (model_xml_id, domain_str, line)
    file_path: str


# ---------------------------------------------------------------------------
# Known Odoo data
# ---------------------------------------------------------------------------

_KNOWN_MODELS_CACHE: dict[str, Any] | None = None
_KNOWN_GROUPS: frozenset[str] = frozenset({
    "base.group_user", "base.group_public", "base.group_portal",
    "base.group_system", "base.group_no_one", "base.group_erp_manager",
    "base.group_multi_company", "base.group_multi_currency",
    "account.group_account_manager", "account.group_account_invoice",
    "account.group_account_user", "account.group_account_readonly",
    "sale.group_sale_manager", "sale.group_sale_salesman",
    "purchase.group_purchase_manager", "purchase.group_purchase_user",
    "stock.group_stock_manager", "stock.group_stock_user",
    "hr.group_hr_manager", "hr.group_hr_user",
})

# View metadata field names -- NOT model fields, should not trigger E3
_VIEW_META_FIELDS: frozenset[str] = frozenset({
    "name", "model", "arch", "priority", "inherit_id", "type",
    "groups_id", "active", "sequence",
})


def _load_known_models() -> dict[str, Any]:
    """Load and cache known_odoo_models.json."""
    global _KNOWN_MODELS_CACHE  # noqa: PLW0603
    if _KNOWN_MODELS_CACHE is not None:
        return _KNOWN_MODELS_CACHE
    data_path = Path(__file__).resolve().parent.parent / "data" / "known_odoo_models.json"
    if data_path.exists():
        data = json.loads(data_path.read_text(encoding="utf-8"))
        _KNOWN_MODELS_CACHE = data.get("models", {})
    else:
        _KNOWN_MODELS_CACHE = {}
    return _KNOWN_MODELS_CACHE


def _get_inherited_fields(
    inherits: list[str],
    known_models: dict[str, Any],
    module_models: dict[str, _ParsedModel],
) -> dict[str, dict[str, Any]]:
    """Collect fields from _inherit parents via known models and module models."""
    inherited: dict[str, dict[str, Any]] = {}
    for parent in inherits:
        known = known_models.get(parent)
        if known and "fields" in known:
            for fname, fdef in known["fields"].items():
                inherited[fname] = fdef
        parsed = module_models.get(parent)
        if parsed:
            for fname, fdef in parsed.fields.items():
                inherited[fname] = fdef
    return inherited


# ---------------------------------------------------------------------------
# Parsers (single-pass for each file type)
# ---------------------------------------------------------------------------


def _iter_py_trees(
    module_dir: Path,
    ast_cache: AstCache | None = None,
) -> list[tuple[str, ast.Module]]:
    """Yield (relative_path, ast_tree) for all Python files in module_dir.

    Uses *ast_cache* when available to avoid redundant parsing.
    Returns a list (not generator) so callers can iterate multiple times.
    """
    results: list[tuple[str, ast.Module]] = []
    for py_file in module_dir.rglob("*.py"):
        rel = str(py_file.relative_to(module_dir))
        if ast_cache is not None and rel in ast_cache:
            results.append((rel, ast_cache[rel]))
        else:
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=rel)
            except (SyntaxError, OSError):
                continue
            results.append((rel, tree))
    return results


def _parse_python_file(
    py_path: Path, module_dir: Path, ast_cache: AstCache | None = None,
) -> tuple[list[_ParsedModel], list[str] | None]:
    """Parse a Python file for model definitions.

    Returns (models, error_or_none).
    If syntax error, returns ([], error_message).
    Populates *ast_cache* with successfully parsed trees.
    """
    source = py_path.read_text(encoding="utf-8")
    rel = str(py_path.relative_to(module_dir))
    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as exc:
        return [], [f"Python syntax error in {rel}: {exc.msg} (line {exc.lineno})"]

    if ast_cache is not None:
        ast_cache[rel] = tree

    models: list[_ParsedModel] = []
    imports: list[str] = []

    for node in ast.walk(tree):
        # Collect imports from odoo.addons.*
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod_name = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                mod_name = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("odoo.addons."):
                        parts = alias.name.split(".")
                        if len(parts) >= 3:
                            imports.append(parts[2])
            if mod_name.startswith("odoo.addons."):
                parts = mod_name.split(".")
                if len(parts) >= 3:
                    imports.append(parts[2])

        # Collect model classes
        if isinstance(node, ast.ClassDef):
            model_info = _extract_model_info(node, rel)
            if model_info:
                model_info.imports = imports
                models.append(model_info)

    return models, None


def _extract_model_info(node: ast.ClassDef, file_path: str) -> _ParsedModel | None:
    """Extract model name, fields, inherits from an AST ClassDef."""
    model_name: str | None = None
    inherits: list[str] = []
    fields_dict: dict[str, dict[str, Any]] = {}
    comodels: list[str] = []
    depends_decs: list[tuple[str, list[str]]] = []
    line_numbers: dict[str, int] = {}

    for stmt in node.body:
        # _name = '...'
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    if target.id == "_name" and isinstance(stmt.value, ast.Constant):
                        model_name = str(stmt.value.value)
                    elif target.id == "_inherit":
                        inherits = _extract_inherit(stmt.value)

        # Field assignments: name = fields.Char(...)
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target = stmt.targets[0]
            if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Call):
                finfo = _extract_field_call(stmt.value)
                if finfo:
                    fields_dict[target.id] = finfo
                    line_numbers[target.id] = stmt.lineno
                    if "comodel_name" in finfo:
                        comodels.append(finfo["comodel_name"])

        # @api.depends(...) decorators on methods
        if isinstance(stmt, ast.FunctionDef):
            for dec in stmt.decorator_list:
                dep_fields = _extract_depends_decorator(dec)
                if dep_fields:
                    depends_decs.append((stmt.name, dep_fields))

    if model_name is None:
        return None

    return _ParsedModel(
        model_name=model_name,
        fields=fields_dict,
        comodels=comodels,
        inherits=inherits,
        imports=[],
        depends_decorators=depends_decs,
        file_path=file_path,
        line_numbers=line_numbers,
    )


def _extract_inherit(node: ast.expr) -> list[str]:
    """Extract _inherit value as a list of strings."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.List):
        result = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                result.append(elt.value)
        return result
    return []


def _extract_field_call(node: ast.Call) -> dict[str, Any] | None:
    """Extract field info from a fields.X(...) call."""
    if not isinstance(node.func, ast.Attribute):
        return None
    if not isinstance(node.func.value, ast.Name):
        return None
    if node.func.value.id != "fields":
        return None

    ftype = node.func.attr
    info: dict[str, Any] = {"type": ftype}

    # First positional arg is often comodel_name for relational fields
    if ftype in ("Many2one", "One2many", "Many2many") and node.args:
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            info["comodel_name"] = first_arg.value

    # Check keyword args
    for kw in node.keywords:
        if kw.arg == "comodel_name" and isinstance(kw.value, ast.Constant):
            info["comodel_name"] = str(kw.value.value)
        elif kw.arg == "compute" and isinstance(kw.value, ast.Constant):
            info["compute"] = str(kw.value.value)

    return info


def _extract_depends_decorator(dec: ast.expr) -> list[str] | None:
    """Extract field names from @api.depends('f1', 'f2')."""
    if not isinstance(dec, ast.Call):
        return None
    if not isinstance(dec.func, ast.Attribute):
        return None
    if dec.func.attr != "depends":
        return None
    if not isinstance(dec.func.value, ast.Name) or dec.func.value.id != "api":
        return None

    result = []
    for arg in dec.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            result.append(arg.value)
    return result if result else None


def _parse_xml_file(
    xml_path: Path, module_dir: Path
) -> tuple[_ParsedXml | None, str | None]:
    """Parse an XML file for records, field refs, groups, external refs.

    Returns (parsed_xml, error_message_or_none).
    """
    rel = str(xml_path.relative_to(module_dir))
    try:
        tree = ET.parse(xml_path)  # noqa: S314
    except ET.ParseError as exc:
        return None, f"XML parse error in {rel}: {exc}"

    root = tree.getroot()
    record_ids: dict[str, int] = {}
    field_refs: list[tuple[str, str, int]] = []
    group_refs: list[tuple[str, int]] = []
    external_refs: list[str] = []
    rule_domains: list[tuple[str, str, int]] = []

    for record in root.iter("record"):
        xml_id = record.get("id", "")
        record_model = record.get("model", "")

        if xml_id:
            record_ids[xml_id] = 1  # line not easily available from ET

        # Check for ir.rule domain_force
        if record_model == "ir.rule":
            model_ref = ""
            domain_str = ""
            for fld in record:
                if fld.tag == "field":
                    fname = fld.get("name", "")
                    if fname == "model_id":
                        model_ref = fld.get("ref", "")
                    elif fname == "domain_force":
                        domain_str = (fld.text or "").strip()
            if model_ref and domain_str:
                rule_domains.append((model_ref, domain_str, 1))

        # Detect ir.ui.view records to extract arch field refs
        if record_model == "ir.ui.view":
            view_model = ""
            for fld in record:
                if fld.tag == "field" and fld.get("name") == "model":
                    view_model = (fld.text or "").strip()
                # Check for ref="" attributes on fields (external refs)
                if fld.tag == "field" and fld.get("ref"):
                    ref_val = fld.get("ref", "")
                    if "." in ref_val:
                        external_refs.append(ref_val)

            # Find arch content and extract field refs inside form/tree/search
            for fld in record:
                if fld.tag == "field" and fld.get("name") == "arch":
                    _extract_arch_field_refs(fld, view_model, field_refs, group_refs)

        # Non-view records: check for ref="" attributes
        if record_model != "ir.ui.view":
            for fld in record:
                if fld.tag == "field" and fld.get("ref"):
                    ref_val = fld.get("ref", "")
                    if "." in ref_val:
                        external_refs.append(ref_val)

    parsed = _ParsedXml(
        record_ids=record_ids,
        field_refs=field_refs,
        group_refs=group_refs,
        external_refs=external_refs,
        rule_domains=rule_domains,
        file_path=rel,
    )
    return parsed, None


def _extract_arch_field_refs(
    arch_node: ET.Element,
    view_model: str,
    field_refs: list[tuple[str, str, int]],
    group_refs: list[tuple[str, int]],
) -> None:
    """Extract field name references from inside arch (form/tree/search)."""
    # Walk all elements inside arch
    for elem in arch_node.iter():
        # Field references inside form/tree/search
        if elem.tag == "field":
            fname = elem.get("name", "")
            if fname and view_model:
                field_refs.append((view_model, fname, 1))

        # Group references (groups="module.group_name")
        groups_attr = elem.get("groups", "")
        if groups_attr:
            for grp in groups_attr.split(","):
                grp = grp.strip()
                if grp:
                    group_refs.append((grp, 1))
