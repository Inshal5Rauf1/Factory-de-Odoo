"""Mermaid diagram generation from model registry data.

Pure functions for generating Mermaid dependency DAG (`graph TD` flowchart)
and ER diagrams (`erDiagram`) from :class:`ModelRegistry` data.  All output
is plain-text ``.mmd`` content -- no parsing or AST needed.

Public API
----------
- :func:`generate_dependency_dag` -- module dependency flowchart
- :func:`generate_er_diagram` -- model entity-relationship diagram
- :func:`generate_module_diagrams` -- write module-level ``.mmd`` files
- :func:`generate_project_diagrams` -- write project-level ``.mmd`` files
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from odoo_gen_utils.registry import ModelEntry, ModelRegistry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TECHNICAL_FIELDS = frozenset({
    "create_uid",
    "write_uid",
    "create_date",
    "write_date",
    "message_ids",
    "message_follower_ids",
    "activity_ids",
    "activity_state",
    "message_main_attachment_id",
    "__last_update",
    "display_name",
})

_EXCLUDED_TYPES = frozenset({"Binary", "Text", "Html"})

_RELATIONAL_TYPES = frozenset({"Many2one", "One2many", "Many2many"})

_EXTERNAL_CLASSDEF = "classDef external fill:#f0f0f0,stroke:#999,stroke-dasharray: 5 5"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mermaid_id(name: str) -> str:
    """Sanitize a name to a valid Mermaid identifier.

    Replaces ``'.'`` and ``'-'`` with ``'_'``.

    Examples::

        >>> _mermaid_id("res.partner")
        'res_partner'
        >>> _mermaid_id("uni-fee")
        'uni_fee'
        >>> _mermaid_id("uni_student")
        'uni_student'
    """
    return re.sub(r'[.\-]', '_', name)


def _is_key_field(field_name: str, field_def: dict[str, Any]) -> bool:
    """Determine if a non-relational field is important enough for the ER diagram.

    Inclusion rules (in order):

    1. Exclude technical fields (create_uid, write_date, etc.)
    2. Exclude Binary, Text, Html types
    3. Exclude non-stored computed fields
    4. Include ``name`` and ``state`` fields
    5. Include Selection and Monetary types
    6. Include stored computed fields
    7. Exclude everything else
    """
    if field_name in _TECHNICAL_FIELDS:
        return False
    ftype = field_def.get("type", "")
    if ftype in _EXCLUDED_TYPES:
        return False
    # Non-stored computed fields are excluded
    if field_def.get("compute") and not field_def.get("store", False):
        return False
    # Include: name, state
    if field_name in ("name", "state"):
        return True
    # Include: Selection, Monetary
    if ftype in ("Selection", "Monetary"):
        return True
    # Include: stored computed fields
    if field_def.get("compute") and field_def.get("store", False):
        return True
    return False


def _is_external_module(module_name: str, project_modules: set[str]) -> bool:
    """Return ``True`` if *module_name* is not a project module."""
    return module_name not in project_modules


def _get_model_module(
    model_name: str,
    registry: ModelRegistry,
) -> str | None:
    """Return the module that owns *model_name*, or ``None``."""
    entry = registry._models.get(model_name)
    if entry:
        return entry.module
    return None


def _relationship_marker(
    rel_type: str,
    is_cross_module: bool,
) -> str:
    """Return the Mermaid cardinality marker for a relationship.

    Uses dotted lines (``..``) for cross-module, solid (``--``) for same.
    """
    sep = ".." if is_cross_module else "--"
    if rel_type == "Many2one":
        return f"}}o{sep}||"
    if rel_type == "One2many":
        return f"||{sep}o{{"
    # Many2many
    return f"}}o{sep}o{{"


# ---------------------------------------------------------------------------
# Public: Dependency DAG
# ---------------------------------------------------------------------------


def generate_dependency_dag(
    module_name: str,
    dependency_graph: dict[str, list[str]],
    project_modules: set[str],
) -> str:
    """Generate a Mermaid ``graph TD`` flowchart of module dependencies.

    Args:
        module_name: Target module name.
        dependency_graph: ``{module: [dep_modules]}`` from registry.
        project_modules: Set of modules in the project (non-external).

    Returns:
        Mermaid flowchart string ending with a newline.
    """
    lines: list[str] = ["graph TD"]

    deps = dependency_graph.get(module_name, [])

    # Node declarations
    mid = _mermaid_id(module_name)
    lines.append(f'    {mid}["{module_name}"]')

    for dep in deps:
        dep_id = _mermaid_id(dep)
        if _is_external_module(dep, project_modules):
            lines.append(f'    {dep_id}["{dep}"]:::external')
        else:
            lines.append(f'    {dep_id}["{dep}"]')

    # Edge lines
    for dep in deps:
        dep_id = _mermaid_id(dep)
        lines.append(f"    {mid} --> {dep_id}")

    # classDef line
    lines.append(f"    {_EXTERNAL_CLASSDEF}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public: ER Diagram
# ---------------------------------------------------------------------------


def generate_er_diagram(
    module_name: str,
    models: dict[str, ModelEntry],
    registry: ModelRegistry,
) -> str:
    """Generate a Mermaid ``erDiagram`` for a module's models.

    Args:
        module_name: Target module name.
        models: ``{model_name: ModelEntry}`` for this module.
        registry: Full registry for cross-module reference lookup.

    Returns:
        Mermaid erDiagram string ending with a newline.
    """
    lines: list[str] = ["erDiagram"]
    project_modules = set(registry.list_modules().keys())

    # Track which cross-module entities we need stubs for
    cross_module_entities: dict[str, ModelEntry | None] = {}

    # Entity blocks + relationship lines
    relationships: list[str] = []

    for model_name, entry in models.items():
        entity_id = _mermaid_id(model_name)

        # Collect key non-relational fields
        key_fields: list[tuple[str, str]] = []  # (type, field_name)
        for fname, fdef in entry.fields.items():
            ftype = fdef.get("type", "")

            # Skip technical fields for relationships too
            if fname in _TECHNICAL_FIELDS:
                continue

            if ftype in _RELATIONAL_TYPES:
                comodel = fdef.get("comodel_name", "")
                if not comodel:
                    continue
                comodel_id = _mermaid_id(comodel)

                # Determine if cross-module
                comodel_module = _get_model_module(comodel, registry)
                is_cross = comodel_module is not None and comodel_module != module_name

                # If comodel is not in our models dict and is cross-module, track stub
                if comodel not in models and comodel_module != module_name:
                    is_cross = True
                    if comodel not in cross_module_entities:
                        cross_module_entities[comodel] = registry._models.get(comodel)

                marker = _relationship_marker(ftype, is_cross)
                relationships.append(
                    f"    {entity_id} {marker} {comodel_id} : {fname}"
                )
            else:
                if _is_key_field(fname, fdef):
                    key_fields.append((ftype, fname))

        # Write entity block
        lines.append(f"    {entity_id} {{")
        for ftype, fname in key_fields:
            lines.append(f"        {ftype} {fname}")
        lines.append("    }")

    # Add stub entities for cross-module references
    for cm_name, cm_entry in cross_module_entities.items():
        cm_id = _mermaid_id(cm_name)
        lines.append(f"    {cm_id} {{")
        if cm_entry is not None:
            # Add just the 'name' field if it exists
            if "name" in cm_entry.fields:
                name_ftype = cm_entry.fields["name"].get("type", "Char")
                lines.append(f"        {name_ftype} name")
        lines.append("    }")

    # Add relationship lines
    lines.extend(relationships)

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public: File writers
# ---------------------------------------------------------------------------


def generate_module_diagrams(
    module_name: str,
    spec: dict[str, Any],
    registry: ModelRegistry,
    output_dir: Path,
) -> None:
    """Write ``dependencies.mmd`` and ``er_diagram.mmd`` to *output_dir*.

    Builds the required data structures from *spec* and *registry*, then
    calls :func:`generate_dependency_dag` and :func:`generate_er_diagram`.

    Creates *output_dir* if it does not exist.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build project_modules from registry
    project_modules = set(registry.list_modules().keys())
    # Also include the current module
    project_modules.add(module_name)

    # Build dependency_graph: merge spec depends with registry graph
    dep_graph: dict[str, list[str]] = dict(registry._dependency_graph)
    dep_graph[module_name] = list(spec.get("depends", []))

    # Generate dependency DAG
    dag_content = generate_dependency_dag(module_name, dep_graph, project_modules)
    (output_dir / "dependencies.mmd").write_text(dag_content, encoding="utf-8")

    # Build models dict from spec
    spec_models: dict[str, ModelEntry] = {}
    for model in spec.get("models", []):
        model_name = model["_name"]
        inherits = model.get("_inherit", [])
        if isinstance(inherits, str):
            inherits = [inherits]
        spec_models[model_name] = ModelEntry(
            module=module_name,
            fields=model.get("fields", {}),
            inherits=inherits,
            description=model.get("description", ""),
        )

    # Generate ER diagram
    er_content = generate_er_diagram(module_name, spec_models, registry)
    (output_dir / "er_diagram.mmd").write_text(er_content, encoding="utf-8")


def generate_project_diagrams(
    registry: ModelRegistry,
    output_dir: Path,
) -> None:
    """Write ``project_dependencies.mmd`` and ``project_er.mmd`` to *output_dir*.

    Uses the full registry data for a combined project-level view.

    Creates *output_dir* if it does not exist.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    project_modules = set(registry._dependency_graph.keys())

    # Combined dependency DAG: generate for all modules
    lines: list[str] = ["graph TD"]
    all_nodes: set[str] = set()
    all_edges: list[str] = []

    for mod, deps in registry._dependency_graph.items():
        mod_id = _mermaid_id(mod)
        if mod_id not in all_nodes:
            all_nodes.add(mod_id)
            lines.append(f'    {mod_id}["{mod}"]')

        for dep in deps:
            dep_id = _mermaid_id(dep)
            if dep_id not in all_nodes:
                all_nodes.add(dep_id)
                if _is_external_module(dep, project_modules):
                    lines.append(f'    {dep_id}["{dep}"]:::external')
                else:
                    lines.append(f'    {dep_id}["{dep}"]')
            all_edges.append(f"    {mod_id} --> {dep_id}")

    lines.extend(all_edges)
    lines.append(f"    {_EXTERNAL_CLASSDEF}")
    dag_content = "\n".join(lines) + "\n"

    (output_dir / "project_dependencies.mmd").write_text(
        dag_content, encoding="utf-8"
    )

    # Combined ER diagram: all models from all modules
    all_models = dict(registry._models)
    # Use the first module as context for cross-module detection (all are "same project")
    er_lines: list[str] = ["erDiagram"]
    relationships: list[str] = []

    for model_name, entry in all_models.items():
        entity_id = _mermaid_id(model_name)
        key_fields: list[tuple[str, str]] = []

        for fname, fdef in entry.fields.items():
            ftype = fdef.get("type", "")

            if fname in _TECHNICAL_FIELDS:
                continue

            if ftype in _RELATIONAL_TYPES:
                comodel = fdef.get("comodel_name", "")
                if not comodel:
                    continue
                comodel_id = _mermaid_id(comodel)

                # For project ER, cross-module means the comodel's module differs
                comodel_module = _get_model_module(comodel, registry)
                is_cross = (
                    comodel_module is not None and comodel_module != entry.module
                )

                marker = _relationship_marker(ftype, is_cross)
                relationships.append(
                    f"    {entity_id} {marker} {comodel_id} : {fname}"
                )
            else:
                if _is_key_field(fname, fdef):
                    key_fields.append((ftype, fname))

        er_lines.append(f"    {entity_id} {{")
        for ftype, fname in key_fields:
            er_lines.append(f"        {ftype} {fname}")
        er_lines.append("    }")

    er_lines.extend(relationships)
    er_content = "\n".join(er_lines) + "\n"

    (output_dir / "project_er.mmd").write_text(er_content, encoding="utf-8")
