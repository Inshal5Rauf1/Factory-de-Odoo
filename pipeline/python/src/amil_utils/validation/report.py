"""Report formatting for validation results.

Produces both human-readable markdown and machine-readable JSON output
from a ValidationReport dataclass.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from odoo_gen_utils.validation.types import ValidationReport

# Severity ordering: higher priority first
_SEVERITY_ORDER = {
    "fatal": 0,
    "error": 1,
    "warning": 2,
    "refactor": 3,
    "convention": 4,
    "info": 5,
}


def _severity_sort_key(severity: str) -> int:
    """Return sort key for violation severity (lower = higher priority)."""
    return _SEVERITY_ORDER.get(severity, 99)


def _format_violations_section(report: ValidationReport) -> str:
    """Format the pylint-odoo violations section."""
    if not report.pylint_violations:
        return "No violations found.\n"

    sorted_violations = sorted(
        report.pylint_violations,
        key=lambda v: _severity_sort_key(v.severity),
    )

    lines = [
        "| File:Line | Rule | Severity | Message |",
        "| --- | --- | --- | --- |",
    ]
    for v in sorted_violations:
        lines.append(f"| {v.file}:{v.line} | {v.rule_code} | {v.severity} | {v.message} |")

    return "\n".join(lines) + "\n"


def _format_install_section(report: ValidationReport) -> str:
    """Format the Docker install result section."""
    if not report.docker_available:
        return "Skipped (Docker not available)\n"

    if report.install_result is None:
        return "Not run\n"

    if report.install_result.success:
        return "**PASS**\n"

    lines = ["**FAIL**"]
    if report.install_result.error_message:
        lines.append(f"\n{report.install_result.error_message}")
    return "\n".join(lines) + "\n"


def _format_tests_section(report: ValidationReport) -> str:
    """Format the test results section."""
    if not report.docker_available:
        return "Skipped (Docker not available)\n"

    if not report.test_results:
        return "Not run\n"

    lines = [
        "| Test | Status | Error |",
        "| --- | --- | --- |",
    ]
    for tr in report.test_results:
        status = "PASS" if tr.passed else "FAIL"
        error = tr.error_message if tr.error_message else ""
        lines.append(f"| {tr.test_name} | {status} | {error} |")

    return "\n".join(lines) + "\n"


def _format_summary_header(report: ValidationReport) -> str:
    """Format the summary header line with counts."""
    # Lint count
    violation_count = len(report.pylint_violations)
    lint_part = f"**Lint:** {violation_count} violation{'s' if violation_count != 1 else ''}"

    # Install status
    if not report.docker_available:
        install_part = "**Install:** SKIP"
    elif report.install_result is None:
        install_part = "**Install:** SKIP"
    elif report.install_result.success:
        install_part = "**Install:** PASS"
    else:
        install_part = "**Install:** FAIL"

    # Test counts
    if not report.docker_available:
        tests_part = "**Tests:** SKIP"
    elif not report.test_results:
        tests_part = "**Tests:** SKIP"
    else:
        passed = sum(1 for tr in report.test_results if tr.passed)
        total = len(report.test_results)
        tests_part = f"**Tests:** {passed}/{total} passed"

    return f"{lint_part} | {install_part} | {tests_part}"


def format_report_markdown(report: ValidationReport) -> str:
    """Format a ValidationReport as a structured markdown report.

    Produces a 3-section report with summary header:
    1. pylint-odoo violations (table sorted by severity)
    2. Docker install result (PASS/FAIL/Not run/Skipped)
    3. Test results (per-test table)

    Plus optional diagnosis section.

    Args:
        report: The ValidationReport to format.

    Returns:
        Formatted markdown string.
    """
    sections = []

    # Title
    sections.append(f"# Validation Report: {report.module_name}\n")

    # Summary header
    sections.append(_format_summary_header(report))
    sections.append("")

    # Section 1: Lint violations
    sections.append("## pylint-odoo Violations\n")
    sections.append(_format_violations_section(report))

    # Section 2: Docker install
    sections.append("## Docker Install\n")
    sections.append(_format_install_section(report))

    # Section 3: Test results
    sections.append("## Test Results\n")
    sections.append(_format_tests_section(report))

    # Optional diagnosis section
    if report.diagnosis:
        sections.append("## Diagnosis\n")
        for entry in report.diagnosis:
            sections.append(f"- {entry}")
        sections.append("")

    return "\n".join(sections)


def _tuples_to_lists(obj: Any) -> Any:
    """Recursively convert tuples to lists in a nested structure."""
    if isinstance(obj, dict):
        return {k: _tuples_to_lists(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_tuples_to_lists(item) for item in obj]
    return obj


def format_report_json(report: ValidationReport) -> dict[str, Any]:
    """Convert a ValidationReport to a plain dict for JSON serialization.

    Tuples are converted to lists for JSON compatibility.

    Args:
        report: The ValidationReport to convert.

    Returns:
        A dict that can be passed to json.dumps().
    """
    raw = dataclasses.asdict(report)
    return _tuples_to_lists(raw)
