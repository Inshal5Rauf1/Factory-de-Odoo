"""JSON stub report generation -- orchestrates detection + context + classification.

Produces a ``.odoo-gen-stubs.json`` sidecar file in the module output
directory matching the locked schema from CONTEXT.md.  The report is
the contract between the deterministic belt and the external LLM layer
(Claude Code / odoo-gsd) that fills the stubs.

This module is a **leaf** -- it imports only from sibling modules
(``stub_detector``, ``context_builder``, ``classifier``) and
``registry`` from the parent package.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from odoo_gen_utils.logic_writer.classifier import classify_complexity
from odoo_gen_utils.logic_writer.context_builder import StubContext, build_stub_context
from odoo_gen_utils.logic_writer.stub_detector import StubInfo, detect_stubs
from odoo_gen_utils.registry import ModelRegistry

logger = logging.getLogger(__name__)

_REPORT_FILENAME = ".odoo-gen-stubs.json"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StubReport:
    """Summary of a generated stub report."""

    total_stubs: int
    budget_count: int
    quality_count: int
    report_path: Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_stub_report(
    module_dir: Path,
    spec: dict[str, Any],
    registry: ModelRegistry | None = None,
) -> StubReport:
    """Generate ``.odoo-gen-stubs.json`` in *module_dir*.

    Orchestrates the full pipeline:
    1. Detect stubs via AST scanning.
    2. Build context for each stub from spec + registry.
    3. Classify complexity for each stub.
    4. Write JSON report matching the locked schema.
    5. Return :class:`StubReport` summary.
    """
    stubs = detect_stubs(module_dir)

    entries: list[dict[str, Any]] = []
    budget_count = 0
    quality_count = 0

    for stub in stubs:
        context = build_stub_context(stub, spec, registry, module_dir=module_dir)
        complexity = classify_complexity(stub, context.business_rules)

        entries.append(_stub_to_dict(stub, context, complexity))

        if complexity == "budget":
            budget_count += 1
        else:
            quality_count += 1

    total_stubs = len(entries)

    report = {
        "_meta": {
            "generator": "odoo-gen-utils",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "module": module_dir.name,
            "total_stubs": total_stubs,
            "budget_count": budget_count,
            "quality_count": quality_count,
        },
        "stubs": entries,
    }

    report_path = module_dir / _REPORT_FILENAME
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info(
        "Stub report: %d stubs (%d budget, %d quality) -> %s",
        total_stubs,
        budget_count,
        quality_count,
        report_path,
    )

    return StubReport(
        total_stubs=total_stubs,
        budget_count=budget_count,
        quality_count=quality_count,
        report_path=report_path,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _stub_to_dict(
    stub: StubInfo,
    context: StubContext,
    complexity: str,
) -> dict[str, Any]:
    """Convert a single stub + context + complexity to the JSON schema dict.

    Enriched fields (method_type, computation_hint, constraint_type,
    target_field_types, error_messages) are included conditionally --
    empty/default values are omitted to avoid JSON clutter.
    """
    result: dict[str, Any] = {
        "id": f"{stub.model_name}__{stub.method_name}",
        "file": stub.file,
        "line": stub.line,
        "class": stub.class_name,
        "model": stub.model_name,
        "method": stub.method_name,
        "method_type": context.method_type,
        "decorator": stub.decorator,
        "target_fields": list(stub.target_fields),
        "complexity": complexity,
    }

    # Conditionally include enriched fields (omit empty/default values)
    if context.target_field_types:
        result["target_field_types"] = dict(context.target_field_types)

    if context.computation_hint:
        result["computation_hint"] = context.computation_hint

    if context.constraint_type:
        result["constraint_type"] = context.constraint_type

    if context.error_messages:
        result["error_messages"] = list(context.error_messages)

    if context.stub_zone:
        result["stub_zone"] = context.stub_zone
    if context.exclusion_zones:
        result["exclusion_zones"] = list(context.exclusion_zones)
    if context.action_context:
        result["action_context"] = context.action_context
    if context.cron_context:
        result["cron_context"] = context.cron_context
    if context.chain_context:
        result["chain_context"] = context.chain_context

    result["context"] = {
        "model_fields": dict(context.model_fields),
        "related_fields": dict(context.related_fields),
        "business_rules": list(context.business_rules),
        "registry_source": context.registry_source,
    }

    return result
