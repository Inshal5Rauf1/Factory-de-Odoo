"""Logic writer package -- stub detection, context assembly, and report generation.

Public API:
    detect_stubs: Scan module directory for TODO method stubs
    StubInfo: Frozen dataclass describing a detected stub
    build_stub_context: Assemble per-stub context from spec + registry
    StubContext: Frozen dataclass describing assembled context
    classify_complexity: Deterministic budget/quality routing
    generate_stub_report: Orchestrate full pipeline and write .odoo-gen-stubs.json
    StubReport: Frozen dataclass summarising the generated report
"""

from __future__ import annotations

from odoo_gen_utils.logic_writer.classifier import classify_complexity
from odoo_gen_utils.logic_writer.context_builder import (
    StubContext,
    build_stub_context,
)
from odoo_gen_utils.logic_writer.report import StubReport, generate_stub_report
from odoo_gen_utils.logic_writer.stub_detector import StubInfo, detect_stubs

__all__ = [
    "build_stub_context",
    "classify_complexity",
    "detect_stubs",
    "generate_stub_report",
    "StubContext",
    "StubInfo",
    "StubReport",
]
