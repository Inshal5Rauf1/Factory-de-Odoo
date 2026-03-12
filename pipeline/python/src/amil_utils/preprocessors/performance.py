"""Performance enrichment for model fields and indexes."""

from __future__ import annotations

import logging
import re
from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.renderer_utils import INDEXABLE_TYPES, NON_INDEXABLE_TYPES
from odoo_gen_utils.utils.validate import validate_identifier

logger = logging.getLogger(__name__)

_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# SQL keywords that are NEVER allowed in WHERE clauses for composite indexes
_DANGEROUS_SQL_KEYWORDS = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|"
    r"UNION|INTO|GRANT|REVOKE|COPY|pg_)\b",
    re.IGNORECASE,
)
# Only allow simple predicates: identifiers, operators, literals, AND/OR/NOT
_SAFE_WHERE_CHARS = re.compile(r"^[a-zA-Z0-9_\s=!<>().',\-]+$")


def _validate_where_clause(where_clause: str | None) -> bool:
    """Validate a WHERE clause contains only safe SQL predicates.

    Rejects clauses containing dangerous SQL keywords (DROP, DELETE, UNION, etc.)
    or suspicious characters (semicolons, double-dashes).
    """
    if not where_clause:
        return True
    if not isinstance(where_clause, str):
        return False
    clause = where_clause.strip()
    if not clause:
        return True
    if _DANGEROUS_SQL_KEYWORDS.search(clause):
        return False
    if ";" in clause:
        return False
    if "--" in clause:
        return False
    if not _SAFE_WHERE_CHARS.match(clause):
        return False
    return True


@register_preprocessor(order=40, name="performance")
def _process_performance(spec: dict[str, Any]) -> dict[str, Any]:
    """Enrich fields with index/store and models with _order/_sql_constraints.

    Analyzes:
    1. Search view fields (Char/Many2one/Selection) -> index=True
    2. Record rule domains (company_id) -> index=True
    3. Model _order -> index=True on order fields
    4. Computed fields in tree views/search/order -> store=True
    5. unique_together spec -> _sql_constraints
    6. TransientModel flag -> _transient_max_hours/_transient_max_count

    Pure function -- does NOT mutate the input spec.
    """
    models = spec.get("models", [])
    if not models:
        return spec

    new_models = []
    for model in models:
        new_model = _enrich_model_performance(model)
        new_models.append(new_model)

    return {**spec, "models": new_models}


def _enrich_model_performance(model: dict[str, Any]) -> dict[str, Any]:
    """Enrich a single model dict with performance attributes.

    Pure function -- returns a new model dict without mutating the input.
    """
    fields = model.get("fields", [])
    field_names = {f["name"] for f in fields}

    # --- Determine which fields need index=True ---

    # Search view fields: Char, Many2one (appear in <search>), Selection (group-by)
    search_fields = {
        f["name"] for f in fields
        if f.get("type") in ("Char", "Many2one", "Selection")
        and not f.get("internal")
    }

    # Order fields: parse model.order
    order_str = model.get("order", "")
    order_parts = [part.strip().split()[0] for part in order_str.split(",") if part.strip()]
    order_fields = {name for name in order_parts if name in field_names}

    # Domain fields: company_id is used in record rules
    domain_fields: set[str] = set()
    if any(f["name"] == "company_id" for f in fields):
        domain_fields.add("company_id")

    index_fields = search_fields | order_fields | domain_fields

    # --- Determine which computed fields need store=True ---

    # View fields (excluding internal)
    view_fields = [f for f in fields if not f.get("internal")]

    # Tree view fields: first 6 non-One2many/Html/Text fields
    tree_fields: set[str] = set()
    count = 0
    for f in view_fields:
        if f.get("type") not in ("One2many", "Html", "Text"):
            tree_fields.add(f["name"])
            count += 1
            if count >= 6:
                break

    visible_fields = tree_fields | search_fields | order_fields

    # --- Build new fields list (immutable) ---
    new_fields = []
    for field in fields:
        enriched = {**field}
        ftype = field.get("type", "")

        # Index enrichment
        if field["name"] in index_fields and ftype in INDEXABLE_TYPES:
            enriched["index"] = True

        # Store enrichment for computed fields
        if field.get("compute") and field["name"] in visible_fields:
            if not field.get("store"):
                enriched["store"] = True

        new_fields.append(enriched)

    new_model: dict[str, Any] = {**model, "fields": new_fields}

    # --- model_order: validated _order string ---
    if order_str:
        valid_parts = []
        for part in order_str.split(","):
            part = part.strip()
            if not part:
                continue
            field_name = part.split()[0]
            if field_name in field_names:
                valid_parts.append(part)
        if valid_parts:
            new_model["model_order"] = ", ".join(valid_parts)

    # --- unique_together -> sql_constraints ---
    unique_together = model.get("unique_together", [])
    if unique_together:
        sql_constraints = list(model.get("sql_constraints", []))
        for unique in unique_together:
            ufields = unique.get("fields", [])
            # DEBT-07: Warn on invalid field references instead of silent skip
            missing = [f for f in ufields if f not in field_names]
            if missing:
                logger.warning(
                    "unique_together on model '%s' references non-existent "
                    "fields %s — skipping. Available fields: %s",
                    model.get("name", "?"),
                    missing,
                    sorted(field_names),
                )
                continue
            # C2 fix: Validate field names before SQL interpolation
            for uf in ufields:
                validate_identifier(uf, "unique_together field")
            constraint_name = "unique_" + "_".join(ufields)
            definition = "UNIQUE(%s)" % ", ".join(ufields)
            message = unique.get("message", "%s must be unique." % ", ".join(ufields))
            sql_constraints.append({
                "name": constraint_name,
                "definition": definition,
                "message": message,
            })
        new_model["sql_constraints"] = sql_constraints

    # --- FLAW-14: Composite index hints ---
    index_hints = model.get("index_hints", [])
    if index_hints:
        composite_indexes = []
        for hint in index_hints:
            hint_fields = hint.get("fields", [])
            missing = [f for f in hint_fields if f not in field_names]
            if missing:
                logger.warning(
                    "index_hint on model '%s' references non-existent "
                    "fields %s — skipping.",
                    model.get("name", "?"),
                    missing,
                )
                continue
            idx_name = hint.get("name", "idx_" + "_".join(hint_fields))
            # Validate identifiers to prevent SQL injection in generated code
            unsafe = [f for f in hint_fields if not _SAFE_IDENTIFIER.match(f)]
            if not _SAFE_IDENTIFIER.match(idx_name):
                unsafe.append(idx_name)
            if unsafe:
                logger.warning(
                    "index_hint on model '%s' has unsafe identifiers %s — skipping.",
                    model.get("name", "?"),
                    unsafe,
                )
                continue
            where_clause = hint.get("where")
            if where_clause and not isinstance(where_clause, str):
                logger.warning(
                    "index_hint on model '%s' has non-string where clause — skipping.",
                    model.get("name", "?"),
                )
                continue
            if not _validate_where_clause(where_clause):
                logger.warning(
                    "index_hint on model '%s' has unsafe where clause %r — skipping.",
                    model.get("name", "?"),
                    where_clause,
                )
                continue
            composite_indexes.append({
                "name": idx_name,
                "fields": hint_fields,
                "where": where_clause,
                "unique": hint.get("unique", False),
            })
        if composite_indexes:
            new_model["composite_indexes"] = composite_indexes

    # --- FLAW-14: Read group optimization hints ---
    # Auto-detect fields commonly used in group-by operations
    groupby_fields = [
        f["name"] for f in new_fields
        if f.get("type") in ("Selection", "Many2one", "Date", "Datetime")
        and f.get("index")
    ]
    if groupby_fields:
        new_model["read_group_fields"] = groupby_fields

    # --- TransientModel cleanup ---
    if model.get("transient"):
        new_model["transient_max_hours"] = model.get("transient_max_hours", 1.0)
        new_model["transient_max_count"] = model.get("transient_max_count", 0)

    return new_model
