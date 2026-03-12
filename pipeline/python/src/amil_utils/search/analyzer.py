"""Module structure analysis: models, fields, views, security.

Analyzes a cloned Odoo module directory to extract its structure using
AST parsing for Python files and xml.etree.ElementTree for XML files.
Produces a frozen ModuleAnalysis dataclass for agent consumption.
"""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from odoo_gen_utils.search.index import _parse_manifest_safe


@dataclass(frozen=True)
class ModuleAnalysis:
    """Frozen analysis result for an Odoo module's structure.

    Attributes:
        module_name: Technical module name.
        manifest: Parsed __manifest__.py dictionary.
        model_names: Tuple of model _name values found in models/*.py.
        model_fields: Mapping of model_name -> tuple of field names.
        field_types: Mapping of model_name -> {field_name: field_type}.
        view_types: Mapping of model_name -> tuple of view types (form, tree, search).
        security_groups: Tuple of security group XML IDs.
        data_files: Tuple of data file paths from manifest.
        has_wizards: Whether a wizards/ directory exists.
        has_tests: Whether a tests/ directory exists.
    """

    module_name: str
    manifest: dict
    model_names: tuple[str, ...]
    model_fields: dict[str, tuple[str, ...]]
    field_types: dict[str, dict[str, str]]
    view_types: dict[str, tuple[str, ...]]
    security_groups: tuple[str, ...]
    data_files: tuple[str, ...]
    has_wizards: bool
    has_tests: bool
    inherited_models: tuple[str, ...] = ()


# Odoo field type names that appear as fields.X(...) calls
_ODOO_FIELD_TYPES = frozenset({
    "Char", "Text", "Html", "Integer", "Float", "Monetary",
    "Boolean", "Date", "Datetime", "Binary", "Image",
    "Selection", "Reference",
    "Many2one", "One2many", "Many2many",
})


def _extract_models_from_file(filepath: Path) -> list[tuple[str, dict[str, str]]]:
    """Extract model _name and field definitions from a Python file via AST.

    Scans class bodies for ``_name = 'model.name'`` assignments and
    ``field_name = fields.Type(...)`` attribute assignments.

    Args:
        filepath: Path to a Python file in models/ directory.

    Returns:
        List of (model_name, {field_name: field_type}) tuples.
    """
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    results: list[tuple[str, dict[str, str]]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        model_name: str | None = None
        fields_map: dict[str, str] = {}

        for item in node.body:
            # Look for _name = 'model.name'
            if (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
                and item.targets[0].id == "_name"
                and isinstance(item.value, ast.Constant)
                and isinstance(item.value.value, str)
            ):
                model_name = item.value.value

            # Look for field_name = fields.Type(...)
            if (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
                and isinstance(item.value, ast.Call)
                and isinstance(item.value.func, ast.Attribute)
                and isinstance(item.value.func.value, ast.Name)
                and item.value.func.value.id == "fields"
                and item.value.func.attr in _ODOO_FIELD_TYPES
            ):
                field_name = item.targets[0].id
                field_type = item.value.func.attr
                fields_map[field_name] = field_type

        if model_name is not None:
            results.append((model_name, fields_map))

    return results


def _extract_inherit_only(filepath: Path) -> list[str]:
    """Extract _inherit-only model extensions from a Python file via AST.

    Scans class bodies for ``_inherit = 'model.name'`` or ``_inherit = [...]``
    assignments where NO ``_name`` assignment is present. These represent model
    extensions (adding fields/methods to existing models) rather than new models.

    Args:
        filepath: Path to a Python file in models/ directory.

    Returns:
        List of inherited model name strings.
    """
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    results: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        has_name = False
        inherit_values: list[str] = []

        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            if len(item.targets) != 1 or not isinstance(item.targets[0], ast.Name):
                continue

            target_id = item.targets[0].id

            if target_id == "_name" and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                has_name = True

            if target_id == "_inherit":
                # _inherit can be a string constant or a list of strings
                if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                    inherit_values.append(item.value.value)
                elif isinstance(item.value, ast.List):
                    for elt in item.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            inherit_values.append(elt.value)

        if inherit_values and not has_name:
            results.extend(inherit_values)

    return results


def _extract_view_types(views_dir: Path) -> dict[str, list[str]]:
    """Extract view types from views/*.xml files.

    Parses XML to find ``<record model="ir.ui.view">`` elements and
    inspects the ``<field name="arch">`` content for top-level view
    tags (form, tree, search, kanban, graph, pivot, calendar).

    Args:
        views_dir: Path to the views/ directory.

    Returns:
        Mapping of model_name -> list of view type strings.
    """
    view_types: dict[str, list[str]] = {}

    if not views_dir.is_dir():
        return view_types

    known_view_tags = frozenset({
        "form", "tree", "search", "kanban", "graph", "pivot",
        "calendar", "activity", "cohort",
    })

    for xml_file in views_dir.glob("*.xml"):
        try:
            tree = ET.parse(str(xml_file))
            root = tree.getroot()
        except ET.ParseError:
            continue

        for record in root.iter("record"):
            if record.get("model") != "ir.ui.view":
                continue

            # Get the model name from <field name="model">
            model_elem = None
            arch_elem = None
            for field in record.findall("field"):
                if field.get("name") == "model":
                    model_elem = field
                elif field.get("name") == "arch":
                    arch_elem = field

            if model_elem is None or model_elem.text is None:
                continue

            model_name = model_elem.text.strip()

            if arch_elem is None:
                continue

            # Look for top-level view type tags in arch content
            for child in arch_elem:
                tag = child.tag
                if tag in known_view_tags:
                    if model_name not in view_types:
                        view_types[model_name] = []
                    if tag not in view_types[model_name]:
                        view_types[model_name].append(tag)

    return view_types


def _extract_security_groups(security_dir: Path) -> list[str]:
    """Extract security group XML IDs from security/*.xml files.

    Looks for ``<record id="..." model="res.groups">`` elements.

    Args:
        security_dir: Path to the security/ directory.

    Returns:
        List of group XML ID strings.
    """
    groups: list[str] = []

    if not security_dir.is_dir():
        return groups

    for xml_file in security_dir.glob("*.xml"):
        try:
            tree = ET.parse(str(xml_file))
            root = tree.getroot()
        except ET.ParseError:
            continue

        for record in root.iter("record"):
            record_id = record.get("id", "")
            record_model = record.get("model", "")

            # Groups: model="res.groups"
            if record_model == "res.groups" and record_id:
                groups.append(record_id)

            # Also capture category records that contain "group" in ID
            if record_model == "ir.module.category" and record_id and "group" in record_id:
                groups.append(record_id)

    return groups


def analyze_module(module_path: Path) -> ModuleAnalysis:
    """Analyze an Odoo module's structure.

    Reads __manifest__.py, scans models/*.py with AST for model _name
    and field definitions, scans views/*.xml for view types, reads
    security groups from security/*.xml, and checks for wizards/
    and tests/ directories.

    Args:
        module_path: Path to the module directory (must contain __manifest__.py).

    Returns:
        Frozen ModuleAnalysis with complete structural information.

    Raises:
        FileNotFoundError: If __manifest__.py is not found.
    """
    manifest_path = module_path / "__manifest__.py"
    if not manifest_path.exists():
        msg = f"No __manifest__.py found in {module_path}"
        raise FileNotFoundError(msg)

    manifest_content = manifest_path.read_text(encoding="utf-8")
    manifest = _parse_manifest_safe(manifest_content) or {}

    # Extract models and fields from models/*.py
    all_model_names: list[str] = []
    all_model_fields: dict[str, tuple[str, ...]] = {}
    all_field_types: dict[str, dict[str, str]] = {}

    all_inherited: list[str] = []

    models_dir = module_path / "models"
    if models_dir.is_dir():
        for py_file in models_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            for model_name, fields_map in _extract_models_from_file(py_file):
                all_model_names.append(model_name)
                all_model_fields[model_name] = tuple(fields_map.keys())
                all_field_types[model_name] = dict(fields_map)
            all_inherited.extend(_extract_inherit_only(py_file))

    # Extract view types from views/*.xml
    raw_view_types = _extract_view_types(module_path / "views")
    frozen_view_types = {
        model: tuple(types) for model, types in raw_view_types.items()
    }

    # Extract security groups
    security_groups = _extract_security_groups(module_path / "security")

    # Data files from manifest
    data_files = manifest.get("data", [])
    if not isinstance(data_files, list):
        data_files = []

    return ModuleAnalysis(
        module_name=module_path.name,
        manifest=manifest,
        model_names=tuple(all_model_names),
        model_fields=all_model_fields,
        field_types=all_field_types,
        view_types=frozen_view_types,
        security_groups=tuple(security_groups),
        data_files=tuple(data_files),
        has_wizards=(module_path / "wizards").is_dir(),
        has_tests=(module_path / "tests").is_dir(),
        inherited_models=tuple(all_inherited),
    )


def format_analysis_text(analysis: ModuleAnalysis) -> str:
    """Format a ModuleAnalysis as human-readable text for agent consumption.

    Produces a structured summary of the module's models, fields, views,
    security groups, and structural flags.

    Args:
        analysis: Frozen ModuleAnalysis to format.

    Returns:
        Multi-line string with module structure summary.
    """
    lines: list[str] = []

    lines.append(f"Module: {analysis.module_name}")
    if analysis.manifest.get("name"):
        lines.append(f"Display Name: {analysis.manifest['name']}")
    if analysis.manifest.get("version"):
        lines.append(f"Version: {analysis.manifest['version']}")
    if analysis.manifest.get("category"):
        lines.append(f"Category: {analysis.manifest['category']}")
    lines.append("")

    # Models
    if analysis.model_names:
        lines.append("Models:")
        for model in analysis.model_names:
            fields_list = analysis.model_fields.get(model, ())
            types_map = analysis.field_types.get(model, {})
            lines.append(f"  {model}:")
            for field_name in fields_list:
                ftype = types_map.get(field_name, "?")
                lines.append(f"    - {field_name} ({ftype})")
        lines.append("")

    # Inherited Models (extensions)
    if analysis.inherited_models:
        lines.append("Inherited Models (extensions):")
        for model in analysis.inherited_models:
            lines.append(f"  - {model}")
        lines.append("")

    # Views
    if analysis.view_types:
        lines.append("Views:")
        for model, types in analysis.view_types.items():
            lines.append(f"  {model}: {', '.join(types)}")
        lines.append("")

    # Security
    if analysis.security_groups:
        lines.append("Security Groups:")
        for group in analysis.security_groups:
            lines.append(f"  - {group}")
        lines.append("")

    # Data files
    if analysis.data_files:
        lines.append("Data Files:")
        for df in analysis.data_files:
            lines.append(f"  - {df}")
        lines.append("")

    # Flags
    flags = []
    if analysis.has_wizards:
        flags.append("wizards")
    if analysis.has_tests:
        flags.append("tests")
    if flags:
        lines.append(f"Has: {', '.join(flags)}")

    return "\n".join(lines)
