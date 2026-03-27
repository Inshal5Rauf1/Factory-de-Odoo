"""Tests for Odoo log parser."""

from __future__ import annotations

from amil_utils.validation.log_parser import (
    extract_traceback,
    parse_install_log,
    parse_test_log,
)
from amil_utils.validation.types import TestResult


# --- parse_install_log tests ---


class TestParseInstallLogSuccess:
    """Log with successful module load returns (True, "")."""

    def test_parse_install_log_success(self) -> None:
        log = (
            "2026-03-02 10:00:00,000 1 INFO test_db odoo.modules.loading: "
            "1 modules loaded, 0 modules updated, 0 tests\n"
            "2026-03-02 10:00:01,000 1 INFO test_db odoo.modules.loading: "
            "Modules loaded.\n"
        )
        success, error_msg = parse_install_log(log)
        assert success is True
        assert error_msg == ""


class TestParseInstallLogFailure:
    """Log with ERROR or Traceback returns (False, error message)."""

    def test_parse_install_log_error_line(self) -> None:
        log = (
            "2026-03-02 10:00:00,000 1 ERROR test_db "
            "odoo.modules.registry: Failed to load module test_mod\n"
            "Traceback (most recent call last):\n"
            '  File "/usr/lib/python3/dist-packages/odoo/modules/registry.py", '
            "line 100, in new\n"
            "    odoo.modules.load_modules(registry, force_demo, status, update_module)\n"
            "KeyError: 'missing_field'\n"
        )
        success, error_msg = parse_install_log(log)
        assert success is False
        assert "missing_field" in error_msg or "Failed to load" in error_msg

    def test_parse_install_log_critical(self) -> None:
        log = (
            "2026-03-02 10:00:00,000 1 CRITICAL test_db "
            "odoo.service.server: Failed to initialize database\n"
        )
        success, error_msg = parse_install_log(log)
        assert success is False
        assert error_msg != ""


class TestParseInstallLogModuleNotFound:
    """Log with 'No module named' returns module not found error."""

    def test_parse_install_log_module_not_found(self) -> None:
        log = (
            "2026-03-02 10:00:00,000 1 ERROR test_db "
            "odoo.modules.module: No module named 'my_missing_mod'\n"
        )
        success, error_msg = parse_install_log(log)
        assert success is False
        assert "my_missing_mod" in error_msg


class TestParseInstallLogEmpty:
    """Empty log returns (False, 'No log output')."""

    def test_parse_install_log_empty(self) -> None:
        success, error_msg = parse_install_log("")
        assert success is False
        assert "No log output" in error_msg

    def test_parse_install_log_whitespace(self) -> None:
        success, error_msg = parse_install_log("   \n  \n  ")
        assert success is False
        assert "No log output" in error_msg


# --- parse_test_log tests ---


class TestParseTestLogAllPass:
    """Log with all passing tests returns TestResult with passed=True."""

    def test_parse_test_log_all_pass_legacy(self) -> None:
        """Legacy format: test_name ... ok."""
        log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_create ... ok\n"
            "2026-03-02 10:00:00,050 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_read ... ok\n"
            "2026-03-02 10:00:00,100 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_write ... ok\n"
            "2026-03-02 10:00:00,200 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: Ran 3 tests in 0.5s\n"
        )
        results = parse_test_log(log)
        assert len(results) == 3
        assert all(isinstance(r, TestResult) for r in results)
        assert all(r.passed is True for r in results)

    def test_parse_test_log_all_pass_odoo17(self) -> None:
        """Odoo 17 format: Starting ClassName.test_method ..."""
        log = (
            "2026-03-03 14:01:30,973 1 INFO test_db "
            "odoo.addons.docker_test_module.tests.test_basic: "
            "Starting TestDockerTestModel.test_create_record ... \n"
            "2026-03-03 14:01:32,381 1 INFO test_db "
            "odoo.tests.stats: docker_test_module: 1 tests 0.02s 9 queries\n"
            "2026-03-03 14:01:32,381 1 INFO test_db "
            "odoo.tests.result: 0 failed, 0 error(s) of 1 tests\n"
        )
        results = parse_test_log(log)
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].test_name == "test_create_record"
        assert results[0].duration_seconds > 0


class TestParseTestLogWithFailures:
    """Log with test failure patterns returns TestResult with passed=False."""

    def test_parse_test_log_with_failure_legacy(self) -> None:
        """Legacy format failure."""
        log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_create ... ok\n"
            "2026-03-02 10:00:00,100 1 FAIL test_db "
            "odoo.addons.test_mod.tests.test_model: test_invalid\n"
            "AssertionError: expected True got False\n"
            "2026-03-02 10:00:00,200 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: Ran 2 tests in 0.2s\n"
        )
        results = parse_test_log(log)
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        assert len(passed) == 1
        assert len(failed) == 1
        assert failed[0].test_name == "test_invalid"

    def test_parse_test_log_with_failure_odoo17(self) -> None:
        """Odoo 17 format: Starting ... followed by FAIL log."""
        log = (
            "2026-03-03 14:01:30,973 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: "
            "Starting TestModel.test_create ... \n"
            "2026-03-03 14:01:30,980 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: "
            "Starting TestModel.test_fail_example ... \n"
            "2026-03-03 14:01:30,985 1 FAIL test_db "
            "odoo.addons.test_mod.tests.test_model: test_fail_example\n"
            "AssertionError: expected 42 got 0\n"
            "2026-03-03 14:01:32,381 1 INFO test_db "
            "odoo.tests.stats: test_mod: 2 tests 0.05s 15 queries\n"
        )
        results = parse_test_log(log)
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        assert len(passed) == 1
        assert len(failed) == 1
        assert passed[0].test_name == "test_create"
        assert failed[0].test_name == "test_fail_example"


class TestParseTestLogNoTests:
    """Log without test output returns empty tuple."""

    def test_parse_test_log_no_tests(self) -> None:
        log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.modules.loading: Modules loaded.\n"
        )
        results = parse_test_log(log)
        assert results == ()


class TestParseTestLogMixed:
    """Log with 2 passes and 1 fail returns correct TestResult tuples."""

    def test_parse_test_log_mixed_results_legacy(self) -> None:
        """Legacy format mixed results."""
        log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_create ... ok\n"
            "2026-03-02 10:00:00,050 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_read ... ok\n"
            "2026-03-02 10:00:00,100 1 ERROR test_db "
            "odoo.addons.test_mod.tests.test_model: test_delete\n"
            "ValueError: Cannot delete record\n"
            "2026-03-02 10:00:00,200 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: Ran 3 tests in 0.3s\n"
        )
        results = parse_test_log(log)
        assert len(results) == 3
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        assert len(passed) == 2
        assert len(failed) == 1
        assert failed[0].test_name == "test_delete"


# --- extract_traceback tests ---


class TestExtractTraceback:
    """Extract Python traceback text from log output."""

    def test_extract_traceback_present(self) -> None:
        log = (
            "2026-03-02 10:00:00,000 1 ERROR test_db "
            "odoo.modules.registry: Failed to load module\n"
            "Traceback (most recent call last):\n"
            '  File "/usr/lib/python3/dist-packages/odoo/modules/registry.py", '
            "line 100, in new\n"
            "    odoo.modules.load_modules(registry)\n"
            "KeyError: 'missing_field'\n"
            "2026-03-02 10:00:01,000 1 INFO test_db odoo.modules.loading: done\n"
        )
        tb = extract_traceback(log)
        assert "Traceback (most recent call last):" in tb
        assert "KeyError" in tb

    def test_extract_traceback_absent(self) -> None:
        log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.modules.loading: Modules loaded.\n"
        )
        tb = extract_traceback(log)
        assert tb == ""

    def test_extract_traceback_multiple(self) -> None:
        log = (
            "Traceback (most recent call last):\n"
            '  File "a.py", line 1, in func\n'
            "    raise ValueError\n"
            "ValueError: first\n"
            "Some other log line\n"
            "Traceback (most recent call last):\n"
            '  File "b.py", line 2, in other_func\n'
            "    raise KeyError\n"
            "KeyError: second\n"
        )
        tb = extract_traceback(log)
        # Should extract at least the first traceback
        assert "Traceback (most recent call last):" in tb
