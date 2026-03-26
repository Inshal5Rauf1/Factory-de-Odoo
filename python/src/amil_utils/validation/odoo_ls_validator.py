"""Odoo-LS diagnostic classifier and Violation converter.

Maps odoo-ls language-server diagnostics to Factory de Odoo's
standard :class:`Violation` type, classifies fixable vs unfixable
codes, and filters known false-positive codes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from amil_utils.validation.types import OLSDiagnostic, Violation

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OLS_FIXABLE_CODES: frozenset[str] = frozenset({
    "OLS30003",  # Missing manifest dependency — auto-fixable
})
"""Diagnostic codes that the pipeline can auto-fix."""

OLS_SUPPRESS_CODES: frozenset[str] = frozenset()
"""Known false-positive codes to suppress (add entries as discovered)."""

_SEVERITY_MAP: dict[int, str] = {
    1: "error",
    2: "warning",
    3: "info",
    4: "hint",
}

# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OLSClassificationResult:
    """Immutable result of classifying a batch of OLS diagnostics."""

    errors: tuple[OLSDiagnostic, ...]
    warnings: tuple[OLSDiagnostic, ...]
    suppressed: tuple[OLSDiagnostic, ...]
    fixable_count: int


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_ols_diagnostics(
    diagnostics: Sequence[OLSDiagnostic],
) -> OLSClassificationResult:
    """Separate *diagnostics* into errors, warnings, and suppressed.

    * Severity 1 -> errors
    * Severity 2, 3, 4 -> warnings
    * Codes in :data:`OLS_SUPPRESS_CODES` -> suppressed (excluded from
      errors/warnings)

    ``fixable_count`` tallies diagnostics whose code is in
    :data:`OLS_FIXABLE_CODES` (among the non-suppressed set).
    """
    errors: list[OLSDiagnostic] = []
    warnings: list[OLSDiagnostic] = []
    suppressed: list[OLSDiagnostic] = []
    fixable_count = 0

    for diag in diagnostics:
        if diag.code in OLS_SUPPRESS_CODES:
            suppressed.append(diag)
            continue

        if diag.code in OLS_FIXABLE_CODES:
            fixable_count += 1

        if diag.severity == 1:
            errors.append(diag)
        else:
            warnings.append(diag)

    return OLSClassificationResult(
        errors=tuple(errors),
        warnings=tuple(warnings),
        suppressed=tuple(suppressed),
        fixable_count=fixable_count,
    )


def _strip_file_uri(path: str) -> str:
    """Remove the ``file://`` URI prefix if present."""
    prefix = "file://"
    if path.startswith(prefix):
        return path[len(prefix):]
    return path


def ols_diagnostics_to_violations(
    diagnostics: Sequence[OLSDiagnostic],
) -> list[Violation]:
    """Convert OLS diagnostics to standard :class:`Violation` objects.

    Diagnostics whose code appears in :data:`OLS_SUPPRESS_CODES` are
    silently dropped.  The ``file://`` URI prefix is stripped from paths.
    """
    violations: list[Violation] = []

    for diag in diagnostics:
        if diag.code in OLS_SUPPRESS_CODES:
            continue

        violations.append(
            Violation(
                file=_strip_file_uri(diag.file),
                line=diag.line,
                column=diag.column,
                rule_code=diag.code,
                symbol=diag.code,
                severity=_SEVERITY_MAP.get(diag.severity, "error"),
                message=diag.message,
            )
        )

    return violations
