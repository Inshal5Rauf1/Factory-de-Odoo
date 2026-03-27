"""Semantic validation for generated Odoo modules.

Catches field reference errors, XML ID conflicts, ACL mismatches,
manifest dependency gaps, and ORM pattern violations in rendered output
files -- eliminating the Docker round-trip for the majority of
generation bugs.

26 checks total:
  ERRORS (E1-E13, E15-E17, E23-E25) -- generation is broken, will fail at install
  WARNINGS (W1-W9) -- might be wrong, might be intentional

All stdlib: ast, xml.etree, csv, difflib, dataclasses, time, pathlib.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from amil_utils.registry import ModelRegistry

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes  (defined here so other sub-modules can import them)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationIssue:
    """A single semantic validation issue."""

    code: str  # "E1", "W3", etc.
    severity: str  # "error" or "warning"
    file: str  # relative path inside module
    line: int | None  # line number if available
    message: str  # human-readable description
    fixable: bool = False  # can auto_fix handle this?
    suggestion: str | None = None  # e.g., "Did you mean 'amount'?"


@dataclass
class SemanticValidationResult:
    """Aggregated validation output from ``semantic_validate()``."""

    module: str
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_fixable_errors(self) -> bool:
        return any(issue.fixable for issue in self.errors)


# ---------------------------------------------------------------------------
# Imports from sub-modules (after dataclass definitions to avoid cycles)
# ---------------------------------------------------------------------------

from amil_utils.validation.semantic_parsers import (  # noqa: E402
    AstCache,
    _ParsedModel,
    _ParsedXml,
    _load_known_models,
    _parse_python_file,
    _parse_xml_file,
)
from amil_utils.validation.semantic_checks import (  # noqa: E402
    _check_e1,
    _check_e2,
    _check_e3,
    _check_e4,
    _check_e5,
    _check_e6,
    _check_e7,
    _check_e8,
    _check_e9,
    _check_e10,
    _check_e11,
    _check_e12,
    _check_e13,
    _check_e15,
    _check_e16,
    _check_e17,
    _check_e23,
    _check_e24,
    _check_e25,
    _check_w1,
    _check_w2,
    _check_w3,
    _check_w4,
    _check_w5,
    _check_w8,
    _check_w10,
    _check_w11,
    _check_w12,
    check_comodel_depends,
)


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def semantic_validate_patterns(output_dir: Path) -> SemanticValidationResult:
    """Run **only** AST-pattern checks that odoo-ls cannot perform.

    This is the lightweight alternative to :func:`semantic_validate_full`,
    designed for the odoo-ls pipeline where structural validation (field
    refs, model existence, XML IDs, manifest deps) is already handled by
    the language server.

    Checks included (11 pattern checks):
        E1  -- Python syntax (ast.parse)
        E2  -- XML well-formedness
        E7  -- Missing self iteration in @api.depends
        E8  -- Compute doesn't set target field
        E9  -- Constraint doesn't raise ValidationError
        E10 -- Bare field access in for-loop
        E11 -- Wrong mapped/filtered syntax
        E12 -- write/create/unlink in compute
        E13 -- Override missing super()
        E15 -- Cron method missing @api.model
        E16 -- Exclusion zone violation
        W5  -- Action method modifies state without checking

    Parameters
    ----------
    output_dir:
        Path to the module root (contains ``__manifest__.py``).

    Returns
    -------
    SemanticValidationResult
        Structured result with errors, warnings, and duration.
    """
    start = time.perf_counter()
    module_name = output_dir.name
    result = SemanticValidationResult(module=module_name)

    # --- Phase 1: Syntax checks (E1, E2) ---
    e1_issues, failed_py = _check_e1(output_dir)
    result.errors.extend(e1_issues)

    e2_issues, _failed_xml = _check_e2(output_dir)
    result.errors.extend(e2_issues)

    # --- Phase 2: Parse valid Python files for model info ---
    ast_cache: AstCache = {}
    module_models: dict[str, _ParsedModel] = {}

    for py_file in output_dir.rglob("*.py"):
        rel = str(py_file.relative_to(output_dir))
        if rel in failed_py:
            continue
        models, _err = _parse_python_file(py_file, output_dir, ast_cache)
        for m in models:
            module_models[m.model_name] = m

    # --- Phase 3: AST-pattern checks only ---
    # E7: Missing self iteration
    result.errors.extend(_check_e7(output_dir, module_models, ast_cache=ast_cache))

    # E8: Compute doesn't set target field (also emits W8 when targets unknown)
    e8_issues = _check_e8(output_dir, module_models, ast_cache=ast_cache)
    for issue in e8_issues:
        if issue.severity == "warning":
            result.warnings.append(issue)
        else:
            result.errors.append(issue)

    # E9: Constraint doesn't raise ValidationError
    result.errors.extend(_check_e9(output_dir, module_models, ast_cache=ast_cache))

    # E10: Bare field access in for-loop body
    result.errors.extend(_check_e10(output_dir, module_models, ast_cache=ast_cache))

    # E11: Wrong mapped/filtered syntax
    result.errors.extend(_check_e11(output_dir, module_models, ast_cache=ast_cache))

    # E12: write/create/unlink in compute
    result.errors.extend(_check_e12(output_dir, module_models, ast_cache=ast_cache))

    # E13: Override method missing super() call
    result.errors.extend(_check_e13(output_dir, module_models, ast_cache=ast_cache))

    # E15: Cron method missing @api.model
    result.errors.extend(_check_e15(output_dir, module_models, ast_cache=ast_cache))

    # E16: Exclusion zone violation (skeleton diff)
    result.errors.extend(_check_e16(output_dir, module_models, ast_cache=ast_cache))

    # W5: Action method modifies state without checking
    result.warnings.extend(_check_w5(output_dir, module_models, ast_cache=ast_cache))

    elapsed = time.perf_counter() - start
    result.duration_ms = int(elapsed * 1000)
    return result


def semantic_validate_full(
    output_dir: Path,
    registry: ModelRegistry | None = None,
    spec: dict[str, Any] | None = None,
) -> SemanticValidationResult:
    """Run **all** semantic checks on a generated module directory.

    This is the full validation suite (26 checks) including structural
    checks that overlap with odoo-ls.  Use :func:`semantic_validate_patterns`
    when odoo-ls handles the structural layer.

    Parameters
    ----------
    output_dir:
        Path to the module root (contains ``__manifest__.py``).
    registry:
        Optional :class:`ModelRegistry` for comodel lookups.
    spec:
        Optional module spec dict for portal ownership validation (E23).

    Returns
    -------
    SemanticValidationResult
        Structured result with errors, warnings, and duration.
    """
    start = time.perf_counter()
    module_name = output_dir.name
    result = SemanticValidationResult(module=module_name)
    known_models = _load_known_models()

    # --- Phase 1: Syntax checks (E1, E2) ---
    e1_issues, failed_py = _check_e1(output_dir)
    result.errors.extend(e1_issues)

    e2_issues, failed_xml = _check_e2(output_dir)
    result.errors.extend(e2_issues)

    # --- Phase 2: Parse valid files ---
    # Build AST cache during parsing so Phase 3 checks reuse parsed trees.
    ast_cache: AstCache = {}
    module_models: dict[str, _ParsedModel] = {}
    all_imports: list[str] = []

    for py_file in output_dir.rglob("*.py"):
        rel = str(py_file.relative_to(output_dir))
        if rel in failed_py:
            continue  # Short-circuit: skip files that failed E1
        models, _err = _parse_python_file(py_file, output_dir, ast_cache)
        for m in models:
            module_models[m.model_name] = m
            all_imports.extend(m.imports)

    parsed_xmls: list[_ParsedXml] = []
    for xml_file in output_dir.rglob("*.xml"):
        rel = str(xml_file.relative_to(output_dir))
        if rel in failed_xml:
            continue  # Short-circuit: skip files that failed E2
        px, _err = _parse_xml_file(xml_file, output_dir)
        if px:
            parsed_xmls.append(px)

    # --- Phase 3: Cross-reference checks ---
    # E5: XML ID uniqueness
    result.errors.extend(_check_e5(parsed_xmls))

    # E3: Field references
    result.errors.extend(_check_e3(parsed_xmls, module_models, known_models))

    # E4: ACL references
    result.errors.extend(_check_e4(output_dir, module_models))

    # E6: Manifest depends
    result.errors.extend(_check_e6(output_dir, module_models, parsed_xmls))

    # E7: Missing self iteration
    result.errors.extend(_check_e7(output_dir, module_models, ast_cache=ast_cache))

    # E8: Compute doesn't set target field (also emits W8 when targets unknown)
    e8_issues = _check_e8(output_dir, module_models, ast_cache=ast_cache)
    for issue in e8_issues:
        if issue.severity == "warning":
            result.warnings.append(issue)
        else:
            result.errors.append(issue)

    # E9: Constraint doesn't raise ValidationError
    result.errors.extend(_check_e9(output_dir, module_models, ast_cache=ast_cache))

    # E10: Bare field access in for-loop body
    result.errors.extend(_check_e10(output_dir, module_models, ast_cache=ast_cache))

    # E11: Wrong mapped/filtered syntax
    result.errors.extend(_check_e11(output_dir, module_models, ast_cache=ast_cache))

    # E12: write/create/unlink in compute
    result.errors.extend(_check_e12(output_dir, module_models, ast_cache=ast_cache))

    # E13: Override method missing super() call
    result.errors.extend(_check_e13(output_dir, module_models, ast_cache=ast_cache))

    # E15: Cron method missing @api.model
    result.errors.extend(_check_e15(output_dir, module_models, ast_cache=ast_cache))

    # E16: Exclusion zone violation (skeleton diff)
    result.errors.extend(_check_e16(output_dir, module_models, ast_cache=ast_cache))

    # W1: Comodel references
    result.warnings.extend(_check_w1(module_models, known_models, registry))

    # W2: Computed depends
    result.warnings.extend(_check_w2(module_models))

    # W3: Group references
    module_xml_ids: set[str] = set()
    for px in parsed_xmls:
        module_xml_ids.update(px.record_ids.keys())
    result.warnings.extend(_check_w3(parsed_xmls, module_xml_ids))

    # W4: Rule domains
    result.warnings.extend(_check_w4(parsed_xmls, module_models))

    # W5: Action method modifies state without checking
    result.warnings.extend(_check_w5(output_dir, module_models, ast_cache=ast_cache))

    # E17: Extension xpath field references + W6: Unknown base model
    e17_errors, w6_warnings = _check_e17(output_dir, known_models, registry)
    result.errors.extend(e17_errors)
    result.warnings.extend(w6_warnings)

    # E23: Portal ownership path validation
    if spec is not None:
        e23_issues = _check_e23(output_dir, spec, registry)
        for issue in e23_issues:
            if issue.severity == "error":
                result.errors.append(issue)
            else:
                result.warnings.append(issue)

    # E24/E25/W8: Bulk operation validation
    if spec is not None:
        result.errors.extend(_check_e24(output_dir, spec, registry))
        result.errors.extend(_check_e25(output_dir, spec, registry))
        result.warnings.extend(_check_w8(output_dir, spec, registry))

    # W9: Comodel depends cross-validation
    result.warnings.extend(check_comodel_depends(output_dir))

    # W10-W12: Spec-based ORM checks (require spec)
    if spec is not None:
        for issue_dict in _check_w10(output_dir, spec):
            result.warnings.append(ValidationIssue(
                code=issue_dict["code"],
                severity=issue_dict["severity"],
                file="",
                line=None,
                message=issue_dict["message"],
            ))
        for issue_dict in _check_w11(output_dir, spec):
            result.warnings.append(ValidationIssue(
                code=issue_dict["code"],
                severity=issue_dict["severity"],
                file="",
                line=None,
                message=issue_dict["message"],
            ))
        for issue_dict in _check_w12(output_dir, spec):
            result.warnings.append(ValidationIssue(
                code=issue_dict["code"],
                severity=issue_dict["severity"],
                file="",
                line=None,
                message=issue_dict["message"],
            ))

    elapsed = time.perf_counter() - start
    result.duration_ms = int(elapsed * 1000)
    return result


# Backward-compat alias -- existing callers import ``semantic_validate``.
semantic_validate = semantic_validate_full


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_validation_report(result: SemanticValidationResult) -> None:
    """Log a human-friendly semantic validation report."""
    _logger.info("=== Semantic Validation: %s ===", result.module)
    _logger.info("Duration: %dms", result.duration_ms)

    if not result.errors and not result.warnings:
        _logger.info("All checks passed. No issues found.")
        return

    if result.errors:
        _logger.info("ERRORS (%d):", len(result.errors))
        for issue in result.errors:
            loc = f"{issue.file}"
            if issue.line:
                loc += f":{issue.line}"
            _logger.info("  [%s] %s -- %s", issue.code, loc, issue.message)
            if issue.suggestion:
                _logger.info("         Suggestion: %s", issue.suggestion)

    if result.warnings:
        _logger.info("WARNINGS (%d):", len(result.warnings))
        for issue in result.warnings:
            loc = f"{issue.file}"
            if issue.line:
                loc += f":{issue.line}"
            _logger.info("  [%s] %s -- %s", issue.code, loc, issue.message)
            if issue.suggestion:
                _logger.info("         Suggestion: %s", issue.suggestion)

    _logger.info("Summary: %d error(s), %d warning(s)", len(result.errors), len(result.warnings))


# ---------------------------------------------------------------------------
# Re-exports for backward compatibility
#
# Callers (tests, other modules) import private names from this module.
# Keep them importable here so nothing breaks.
# ---------------------------------------------------------------------------

from amil_utils.validation.semantic_parsers import (  # noqa: E402, F401
    _extract_arch_field_refs,
    _extract_depends_decorator,
    _extract_field_call,
    _extract_inherit,
    _extract_model_info,
    _get_inherited_fields,
    _iter_py_trees,
)
