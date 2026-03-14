"""Tests for report formatting (report.py).

Verifies markdown and JSON output for various ValidationReport states.
"""

from __future__ import annotations

import json

from amil_utils.validation.report import format_report_json, format_report_markdown
from amil_utils.validation.types import (
    InstallResult,
    TestResult,
    ValidationReport,
    Violation,
)


def _make_violation(
    file: str = "model.py",
    line: int = 10,
    rule_code: str = "C8101",
    symbol: str = "manifest-required-author",
    severity: str = "convention",
    message: str = "Author is required",
) -> Violation:
    """Helper to create a Violation with defaults."""
    return Violation(
        file=file,
        line=line,
        column=0,
        rule_code=rule_code,
        symbol=symbol,
        severity=severity,
        message=message,
    )


class TestFormatReportMarkdown:
    """Tests for format_report_markdown function."""

    def test_format_report_markdown_empty(self) -> None:
        """Report with no data produces 'No violations', 'Not run' sections."""
        report = ValidationReport(module_name="test_mod")
        md = format_report_markdown(report)

        assert "test_mod" in md
        assert "No violations found" in md
        assert "Not run" in md

    def test_format_report_markdown_with_violations(self) -> None:
        """Report with 2 violations produces a markdown table."""
        v1 = _make_violation(
            file="model.py",
            line=10,
            rule_code="C8101",
            severity="convention",
            message="Author needed",
        )
        v2 = _make_violation(
            file="views/form.xml",
            line=20,
            rule_code="W8105",
            symbol="attribute-deprecated",
            severity="warning",
            message="Deprecated attrs",
        )
        report = ValidationReport(
            module_name="test_mod",
            pylint_violations=(v1, v2),
        )
        md = format_report_markdown(report)

        # Table headers
        assert "File:Line" in md
        assert "Rule" in md
        assert "Severity" in md
        assert "Message" in md
        # Content rows
        assert "model.py:10" in md
        assert "views/form.xml:20" in md
        assert "C8101" in md
        assert "W8105" in md

    def test_format_report_markdown_with_install_success(self) -> None:
        """Report with install_result.success=True shows PASS."""
        report = ValidationReport(
            module_name="test_mod",
            install_result=InstallResult(success=True, log_output="OK", error_message=""),
        )
        md = format_report_markdown(report)
        assert "PASS" in md

    def test_format_report_markdown_with_install_failure(self) -> None:
        """Report with install_result.success=False shows FAIL with error."""
        report = ValidationReport(
            module_name="test_mod",
            install_result=InstallResult(
                success=False,
                log_output="error log...",
                error_message="Module not found",
            ),
        )
        md = format_report_markdown(report)
        assert "FAIL" in md
        assert "Module not found" in md

    def test_format_report_markdown_with_test_results(self) -> None:
        """Report with 3 test results (2 pass, 1 fail) shows per-test table."""
        test_results = (
            TestResult(test_name="test_create", passed=True),
            TestResult(test_name="test_read", passed=True),
            TestResult(test_name="test_delete", passed=False, error_message="Not found"),
        )
        report = ValidationReport(
            module_name="test_mod",
            test_results=test_results,
        )
        md = format_report_markdown(report)

        assert "test_create" in md
        assert "test_read" in md
        assert "test_delete" in md
        assert "Not found" in md

    def test_format_report_markdown_summary_header(self) -> None:
        """Summary line shows counts."""
        v1 = _make_violation()
        v2 = _make_violation(file="other.py", line=5)
        report = ValidationReport(
            module_name="test_mod",
            pylint_violations=(v1, v2),
            install_result=InstallResult(success=True, log_output="", error_message=""),
            test_results=(
                TestResult(test_name="t1", passed=True),
                TestResult(test_name="t2", passed=False),
                TestResult(test_name="t3", passed=True),
            ),
        )
        md = format_report_markdown(report)

        # Summary should mention violation count
        assert "2 violations" in md or "2 violation" in md
        # Summary should mention install pass
        assert "PASS" in md
        # Summary should mention test counts
        assert "2/3" in md or "2 / 3" in md

    def test_format_report_markdown_docker_unavailable(self) -> None:
        """When docker_available=False, install and test show skipped."""
        report = ValidationReport(
            module_name="test_mod",
            docker_available=False,
        )
        md = format_report_markdown(report)
        assert "Docker not available" in md

    def test_format_report_markdown_with_diagnosis(self) -> None:
        """Diagnosis entries appear as bulleted list."""
        report = ValidationReport(
            module_name="test_mod",
            diagnosis=("Check manifest author", "Fix XML syntax"),
        )
        md = format_report_markdown(report)
        assert "Check manifest author" in md
        assert "Fix XML syntax" in md

    def test_format_report_markdown_severity_sort(self) -> None:
        """Violations are sorted by severity (error before convention)."""
        v_conv = _make_violation(severity="convention", file="a.py", line=1, message="conv")
        v_err = _make_violation(severity="error", file="b.py", line=2, message="err")
        v_warn = _make_violation(severity="warning", file="c.py", line=3, message="warn")
        report = ValidationReport(
            module_name="test_mod",
            pylint_violations=(v_conv, v_err, v_warn),
        )
        md = format_report_markdown(report)
        # error should appear before convention in the output
        err_pos = md.index("err")
        conv_pos = md.index("conv")
        assert err_pos < conv_pos, "error violations should appear before convention violations"


class TestFormatReportJson:
    """Tests for format_report_json function."""

    def test_format_report_json(self) -> None:
        """format_report_json returns dict with correct keys."""
        v = _make_violation()
        report = ValidationReport(
            module_name="test_mod",
            pylint_violations=(v,),
            install_result=InstallResult(success=True, log_output="", error_message=""),
            test_results=(TestResult(test_name="t1", passed=True),),
            diagnosis=("check it",),
        )
        result = format_report_json(report)

        assert isinstance(result, dict)
        assert result["module_name"] == "test_mod"
        assert "pylint_violations" in result
        assert "install_result" in result
        assert "test_results" in result
        assert "diagnosis" in result
        # Violations should be dicts, not Violation objects
        assert isinstance(result["pylint_violations"][0], dict)

    def test_format_report_json_roundtrip(self) -> None:
        """JSON output is valid JSON (json.dumps succeeds)."""
        report = ValidationReport(
            module_name="test_mod",
            pylint_violations=(_make_violation(),),
        )
        result = format_report_json(report)
        serialized = json.dumps(result)
        assert isinstance(serialized, str)
        # Round-trip: parse back and verify
        parsed = json.loads(serialized)
        assert parsed["module_name"] == "test_mod"

    def test_format_report_json_empty(self) -> None:
        """Empty report produces valid JSON dict."""
        report = ValidationReport(module_name="empty_mod")
        result = format_report_json(report)

        assert result["module_name"] == "empty_mod"
        assert result["pylint_violations"] == []
        assert result["install_result"] is None
        assert result["test_results"] == []
        assert result["diagnosis"] == []
