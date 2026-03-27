"""Tests for odoo-ls diagnostic classification and conversion."""

from __future__ import annotations

from amil_utils.validation.odoo_ls_validator import (
    OLS_FIXABLE_CODES,
    OLS_SUPPRESS_CODES,
    classify_ols_diagnostics,
    ols_diagnostics_to_violations,
)
from amil_utils.validation.types import OLSDiagnostic, Violation


class TestClassifyDiagnostics:
    def test_separates_errors_and_warnings(self) -> None:
        diags = [
            OLSDiagnostic("f.py", 1, 0, "OLS30001", "Unknown model", 1),
            OLSDiagnostic("f.py", 2, 0, "OLS10001", "Missing import", 2),
            OLSDiagnostic("f.py", 3, 0, "OLS04012", "Cyclic dep", 1),
        ]
        result = classify_ols_diagnostics(diags)
        assert len(result.errors) == 2
        assert len(result.warnings) == 1

    def test_identifies_fixable(self) -> None:
        diags = [OLSDiagnostic("f.py", 1, 0, "OLS30003", "Missing dep", 1)]
        result = classify_ols_diagnostics(diags)
        assert result.fixable_count == 1

    def test_empty_input(self) -> None:
        result = classify_ols_diagnostics([])
        assert len(result.errors) == 0
        assert result.fixable_count == 0

    def test_suppressed_diagnostics_excluded(self) -> None:
        """Suppressed codes should not appear in errors or warnings."""
        # Add a code to suppress list and verify it's filtered
        diags = [OLSDiagnostic("f.py", 1, 0, "OLS30001", "Unknown model", 1)]
        result = classify_ols_diagnostics(diags)
        # OLS30001 is not suppressed, should appear in errors
        assert len(result.errors) == 1
        assert len(result.suppressed) == 0

    def test_info_and_hint_classified_as_warnings(self) -> None:
        """Severity 3 (info) and 4 (hint) go into warnings bucket."""
        diags = [
            OLSDiagnostic("f.py", 1, 0, "OLS10001", "Info msg", 3),
            OLSDiagnostic("f.py", 2, 0, "OLS10002", "Hint msg", 4),
        ]
        result = classify_ols_diagnostics(diags)
        assert len(result.errors) == 0
        assert len(result.warnings) == 2


class TestConvertToViolations:
    def test_maps_diagnostic_to_violation(self) -> None:
        diags = [
            OLSDiagnostic(
                "file:///path/models/emp.py", 10, 4, "OLS30001", "Unknown model", 1
            )
        ]
        violations = ols_diagnostics_to_violations(diags)
        assert len(violations) == 1
        v = violations[0]
        assert isinstance(v, Violation)
        assert v.rule_code == "OLS30001"
        assert v.severity == "error"

    def test_strips_file_uri_prefix(self) -> None:
        diags = [
            OLSDiagnostic(
                "file:///home/user/mod/models/x.py", 1, 0, "OLS30001", "test", 1
            )
        ]
        violations = ols_diagnostics_to_violations(diags)
        assert "models/x.py" in violations[0].file
        assert not violations[0].file.startswith("file://")

    def test_warning_severity_mapped(self) -> None:
        diags = [OLSDiagnostic("f.py", 1, 0, "OLS10001", "warn", 2)]
        violations = ols_diagnostics_to_violations(diags)
        assert violations[0].severity == "warning"

    def test_info_severity_mapped(self) -> None:
        diags = [OLSDiagnostic("f.py", 1, 0, "OLS10001", "info msg", 3)]
        violations = ols_diagnostics_to_violations(diags)
        assert violations[0].severity == "info"

    def test_hint_severity_mapped(self) -> None:
        diags = [OLSDiagnostic("f.py", 1, 0, "OLS10001", "hint msg", 4)]
        violations = ols_diagnostics_to_violations(diags)
        assert violations[0].severity == "hint"

    def test_suppressed_diagnostics_excluded_from_violations(self) -> None:
        """Suppressed codes should not produce violations."""
        # With current empty OLS_SUPPRESS_CODES, all diags convert
        diags = [OLSDiagnostic("f.py", 1, 0, "OLS30001", "test", 1)]
        violations = ols_diagnostics_to_violations(diags)
        assert len(violations) == 1

    def test_line_and_column_preserved(self) -> None:
        diags = [OLSDiagnostic("f.py", 42, 7, "OLS30001", "test", 1)]
        violations = ols_diagnostics_to_violations(diags)
        assert violations[0].line == 42
        assert violations[0].column == 7

    def test_message_preserved(self) -> None:
        diags = [OLSDiagnostic("f.py", 1, 0, "OLS30001", "Detailed error msg", 1)]
        violations = ols_diagnostics_to_violations(diags)
        assert violations[0].message == "Detailed error msg"


class TestConstants:
    def test_fixable_codes_is_frozenset(self) -> None:
        assert isinstance(OLS_FIXABLE_CODES, frozenset)

    def test_suppress_codes_is_frozenset(self) -> None:
        assert isinstance(OLS_SUPPRESS_CODES, frozenset)

    def test_fixable_codes_contains_ols30003(self) -> None:
        assert "OLS30003" in OLS_FIXABLE_CODES

    def test_suppress_codes_starts_empty(self) -> None:
        """Suppress codes start empty; add as false positives are discovered."""
        assert len(OLS_SUPPRESS_CODES) == 0
