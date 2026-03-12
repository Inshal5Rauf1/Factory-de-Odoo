"""Odoo log parsing for install and test results.

Parses stdout/stderr from Odoo CLI commands to extract:
- Install success/failure from module installation
- Per-test pass/fail results from test execution
- Traceback text for error diagnosis
"""

from __future__ import annotations

import re

from odoo_gen_utils.validation.types import TestResult

# --- Compiled regex patterns ---

# Odoo log line with ERROR or CRITICAL severity
_ERROR_LINE = re.compile(
    r"^\d{4}-\d{2}-\d{2}\s[\d:,]+\s+\d+\s+(ERROR|CRITICAL)\s+\S+\s+(.+)$",
    re.MULTILINE,
)

# Module not found pattern - handles both quoted and unquoted module names
_MODULE_NOT_FOUND = re.compile(
    r"No module named ['\"]([^'\"]+)['\"]|No module named (\S+)",
    re.MULTILINE,
)

# Successful module loading indicator
_MODULES_LOADED = re.compile(
    r"modules loaded",
    re.IGNORECASE,
)

# Odoo 17 test start pattern: "Starting ClassName.test_method ..."
# Also handles nested classes and varied module path formats.
_TEST_START = re.compile(
    r"(\S+\.tests\S*)[\s:]+Starting\s+\S+?\.(test_\S+)\s+\.\.\.",
    re.MULTILINE,
)

# Alternate Odoo 17 format without "Starting" prefix:
# "module.tests.test_file: ClassName.test_method ..."
_TEST_START_ALT = re.compile(
    r"(\S+\.tests\S*)[\s:]+\S+?\.(test_\S+)\s+\.\.\.",
    re.MULTILINE,
)

# Legacy test pass pattern (Odoo <17): "test_name ... ok"
_TEST_PASS = re.compile(
    r"(\S+\.tests\.\S+):\s+(test_\S+)\s+\.\.\.\s+ok",
    re.MULTILINE,
)

# Test failure pattern: FAIL or ERROR followed by test info
_TEST_FAIL = re.compile(
    r"^\d{4}-\d{2}-\d{2}\s[\d:,]+\s+\d+\s+(FAIL|ERROR)\s+\S+\s+\S+\.tests\S*",
    re.MULTILINE,
)

# Test failure with test name on same line
_TEST_FAIL_NAMED = re.compile(
    r"^\d{4}-\d{2}-\d{2}\s[\d:,]+\s+\d+\s+(FAIL|ERROR)\s+\S+\s+\S+\.tests\S*[\s:]+(test_\S+)",
    re.MULTILINE,
)

# Odoo 17 test stats: "module_name: N tests Xs Q queries"
_TEST_STATS = re.compile(
    r"odoo\.tests\.stats:\s+(\S+):\s+(\d+)\s+tests?\s+([\d.]+)s",
    re.MULTILINE,
)

# Odoo 17 result summary: "N failed, M error(s) of P tests"
_TEST_RESULT = re.compile(
    r"(\d+)\s+failed,\s+(\d+)\s+error\(s\)\s+of\s+(\d+)\s+tests?",
    re.MULTILINE,
)

# Legacy test summary (Odoo <17): "Ran N tests in Xs"
_TEST_SUMMARY = re.compile(
    r"Ran\s+(\d+)\s+tests?\s+in\s+([\d.]+)s",
    re.MULTILINE,
)

# Traceback start
_TRACEBACK_START = re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE)


def parse_install_log(log_text: str) -> tuple[bool, str]:
    """Parse Odoo stdout/stderr from module install.

    Returns:
        Tuple of (success, error_message).
        success is True if modules loaded without ERROR/CRITICAL.
        error_message contains the relevant error detail on failure.
    """
    if not log_text or not log_text.strip():
        return (False, "No log output")

    # Check for "No module named" first (specific error)
    module_not_found = _MODULE_NOT_FOUND.search(log_text)
    if module_not_found:
        # group(1) is quoted name, group(2) is unquoted name
        module_name = module_not_found.group(1) or module_not_found.group(2)
        return (False, f"Module not found: {module_name}")

    # Check for ERROR or CRITICAL log lines
    error_matches = _ERROR_LINE.findall(log_text)
    if error_matches:
        # Extract the most relevant error message
        # error_matches is list of (severity, message) tuples
        error_messages = [msg.strip() for _severity, msg in error_matches]
        # Return the first error as the primary message
        return (False, error_messages[0])

    # Check for traceback without Odoo-formatted ERROR lines
    if "Traceback" in log_text:
        tb = extract_traceback(log_text)
        # Extract the last line of the traceback (the exception)
        tb_lines = tb.strip().splitlines()
        if tb_lines:
            return (False, tb_lines[-1].strip())
        return (False, "Traceback detected in log output")

    # Check for successful module loading
    if _MODULES_LOADED.search(log_text):
        return (True, "")

    # No clear success or failure indicators
    return (False, "Unable to determine install result from log output")


def parse_test_log(log_text: str) -> tuple[TestResult, ...]:
    """Parse Odoo test output to extract per-test pass/fail results.

    Supports both Odoo 17 format (``Starting Class.test_method ...``)
    and legacy format (``test_method ... ok``).

    Returns:
        Tuple of TestResult dataclasses, one per test found.
    """
    if not log_text or not log_text.strip():
        return ()

    results: list[TestResult] = []
    seen_tests: set[str] = set()

    # Collect failed test names first so we can mark them
    failed_tests: dict[str, str] = {}
    for match in _TEST_FAIL_NAMED.finditer(log_text):
        test_name = match.group(2)
        failure_type = match.group(1)
        if test_name not in failed_tests:
            error_msg = _extract_failure_message(log_text, match.end())
            failed_tests[test_name] = error_msg or f"{failure_type}: {test_name}"

    # Odoo 17 format: "Starting ClassName.test_method ..."
    # Try primary pattern first, then alternate for broader coverage
    for pattern in (_TEST_START, _TEST_START_ALT):
        for match in pattern.finditer(log_text):
            test_name = match.group(2)
            if test_name not in seen_tests:
                seen_tests.add(test_name)
                if test_name in failed_tests:
                    results.append(
                        TestResult(
                            test_name=test_name,
                            passed=False,
                            error_message=failed_tests[test_name],
                        )
                    )
                else:
                    results.append(TestResult(test_name=test_name, passed=True))

    # Legacy format (Odoo <17): "test_name ... ok"
    for match in _TEST_PASS.finditer(log_text):
        test_name = match.group(2)
        if test_name not in seen_tests:
            seen_tests.add(test_name)
            results.append(TestResult(test_name=test_name, passed=True))

    # Legacy failures not already captured
    for match in _TEST_FAIL_NAMED.finditer(log_text):
        test_name = match.group(2)
        if test_name not in seen_tests:
            seen_tests.add(test_name)
            error_msg = _extract_failure_message(log_text, match.end())
            results.append(
                TestResult(
                    test_name=test_name,
                    passed=False,
                    error_message=error_msg or f"{match.group(1)}: {test_name}",
                )
            )

    # Parse duration from Odoo 17 stats or legacy summary
    total_duration = 0.0
    stats_match = _TEST_STATS.search(log_text)
    summary_match = _TEST_SUMMARY.search(log_text)
    if stats_match:
        total_duration = float(stats_match.group(3))
    elif summary_match:
        total_duration = float(summary_match.group(2))

    if total_duration > 0 and results:
        avg_duration = total_duration / len(results)
        results = [
            TestResult(
                test_name=r.test_name,
                passed=r.passed,
                error_message=r.error_message,
                duration_seconds=avg_duration,
            )
            for r in results
        ]

    return tuple(results)


def _extract_failure_message(log_text: str, start_pos: int) -> str:
    """Extract error message following a FAIL/ERROR test line.

    Collects contiguous non-log-formatted lines (up to 10) after the
    failure marker, providing full traceback/assertion context.
    """
    remaining = log_text[start_pos:].strip()
    lines = remaining.splitlines()
    collected: list[str] = []
    for line in lines[:20]:  # Scan up to 20 lines to find up to 10 relevant
        stripped = line.strip()
        if not stripped:
            if collected:
                break  # Blank line after content = end of message
            continue
        if re.match(r"^\d{4}-\d{2}-\d{2}", stripped):
            if collected:
                break  # Hit the next log line = end of message
            continue
        collected.append(stripped)
        if len(collected) >= 10:
            break
    return "\n".join(collected)


def extract_traceback(log_text: str) -> str:
    """Extract Python traceback from log for diagnosis.

    Finds 'Traceback (most recent call last):' and captures until
    the exception line (next line that starts at column 0 and is not
    indented, after at least one indented line).

    Returns:
        The traceback text, or empty string if not found.
    """
    if not log_text:
        return ""

    match = _TRACEBACK_START.search(log_text)
    if not match:
        return ""

    # Start from the traceback line
    start = match.start()
    lines = log_text[start:].splitlines()

    if not lines:
        return ""

    tb_lines: list[str] = [lines[0]]  # "Traceback (most recent call last):"
    found_indented = False

    for line in lines[1:]:
        if line.startswith("  ") or line.startswith("\t"):
            found_indented = True
            tb_lines.append(line)
        elif found_indented:
            # This is the exception line (e.g., "KeyError: 'missing_field'")
            tb_lines.append(line)
            break
        else:
            # Unexpected format, include it and keep looking
            tb_lines.append(line)
            if not line.strip():
                continue
            # Non-indented, non-empty line before any indented line
            # This might be a continuation or malformed traceback
            break

    return "\n".join(tb_lines)
