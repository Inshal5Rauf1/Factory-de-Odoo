"""Tests for Docker runner with mocked subprocess."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from amil_utils.validation.docker_runner import (
    _unique_project_name,
    check_docker_available,
    docker_install_module,
    docker_run_tests,
    get_compose_file,
)
from amil_utils.validation.types import InstallResult, Result, TestResult


# --- Fixtures ---


@pytest.fixture()
def module_dir(tmp_path: Path) -> Path:
    """Create a minimal module directory with a valid Odoo module name."""
    mod = tmp_path / "test_mod"
    mod.mkdir()
    return mod


@pytest.fixture()
def compose_file(tmp_path: Path) -> Path:
    """Return a temporary compose file path."""
    return tmp_path / "docker-compose.yml"


# --- check_docker_available tests ---


class TestCheckDockerAvailablePresent:
    """When docker CLI is present, returns True."""

    @patch("amil_utils.validation.docker_runner.subprocess.run")
    @patch("amil_utils.validation.docker_runner.shutil.which")
    def test_docker_available(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = MagicMock(returncode=0)
        assert check_docker_available() is True
        mock_which.assert_called_once_with("docker")


class TestCheckDockerAvailableMissing:
    """When docker CLI is missing, returns False."""

    @patch("amil_utils.validation.docker_runner.shutil.which")
    def test_docker_not_available(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None
        assert check_docker_available() is False


# --- get_compose_file tests ---


class TestGetComposeFilePath:
    """get_compose_file returns path to docker/docker-compose.yml."""

    def test_compose_file_path(self) -> None:
        result = get_compose_file()
        assert isinstance(result, Path)
        assert result.name == "docker-compose.yml"
        assert "docker" in str(result)


# --- docker_install_module tests ---


class TestDockerInstallModuleSuccess:
    """Successful install returns InstallResult(success=True)."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_docker_install_success(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        mock_available.return_value = True
        # First call: pre-cleanup (down --remove-orphans)
        # Second call: start db only (not full stack)
        # Third call: run --rm (not exec) for install
        success_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.modules.loading: 1 modules loaded, 0 modules updated, 0 tests\n"
            "2026-03-02 10:00:01,000 1 INFO test_db "
            "odoo.modules.loading: Modules loaded.\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=success_log, stderr="", returncode=0),  # run --rm
        ]

        result = docker_install_module(module_dir, compose_file=compose_file)

        assert isinstance(result, Result)
        assert result.success is True
        assert isinstance(result.data, InstallResult)
        assert result.data.success is True
        assert result.data.error_message == ""


class TestDockerInstallUsesRunNotExec:
    """docker_install_module uses 'run --rm' pattern, not 'exec'."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_first_call_starts_db_only(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        mock_available.return_value = True
        success_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.modules.loading: Modules loaded.\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=success_log, stderr="", returncode=0),  # run --rm
        ]

        docker_install_module(module_dir, compose_file=compose_file)

        # Second call (index 1) must start only db service (index 0 is pre-cleanup)
        db_call_args = mock_run.call_args_list[1]
        assert "db" in db_call_args[0][1], (
            f"DB startup _run_compose call should include 'db', "
            f"got args: {db_call_args[0][1]}"
        )

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_second_call_uses_run_rm_not_exec(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        mock_available.return_value = True
        success_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.modules.loading: Modules loaded.\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=success_log, stderr="", returncode=0),  # run --rm
        ]

        docker_install_module(module_dir, compose_file=compose_file)

        # Third call (index 2) must use 'run --rm', not 'exec'
        install_call_args = mock_run.call_args_list[2]
        install_args = install_call_args[0][1]
        assert "run" in install_args, (
            f"Install _run_compose call should use 'run', got args: {install_args}"
        )
        assert "--rm" in install_args, (
            f"Install _run_compose call should include '--rm', got args: {install_args}"
        )
        assert "exec" not in install_args, (
            f"Install _run_compose call should NOT use 'exec', got args: {install_args}"
        )


class TestDockerInstallModuleFailure:
    """Failed install returns InstallResult(success=False)."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_docker_install_failure(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        mock_available.return_value = True
        error_log = (
            "2026-03-02 10:00:00,000 1 ERROR test_db "
            "odoo.modules.registry: Failed to load module test_mod\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=error_log, stderr="", returncode=1),  # run --rm
        ]

        result = docker_install_module(module_dir, compose_file=compose_file)

        assert isinstance(result, Result)
        assert result.success is True  # Result wraps InstallResult; install failure is in .data
        assert isinstance(result.data, InstallResult)
        assert result.data.success is False
        assert result.data.error_message != ""


class TestDockerInstallTeardown:
    """docker compose down -v is ALWAYS called, even on failure."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_teardown_always_called(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        mock_available.return_value = True
        # Pre-cleanup succeeds; all subsequent calls (db startup retries) fail
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            Exception("Subprocess failed"),  # db attempt 1
            Exception("Subprocess failed"),  # db attempt 2
            Exception("Subprocess failed"),  # db attempt 3
        ]

        result = docker_install_module(module_dir, compose_file=compose_file)

        # 2 teardowns from _start_db_with_retry retries + 1 from finally block
        assert mock_teardown.call_count == 3
        assert isinstance(result, Result)
        assert result.success is False


# --- docker_run_tests tests ---


class TestDockerRunTestsSuccess:
    """Successful test run returns tuple of TestResult with passed=True."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_docker_run_tests_success(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        mock_available.return_value = True
        test_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_create ... ok\n"
            "2026-03-02 10:00:00,050 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_read ... ok\n"
            "2026-03-02 10:00:00,100 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: Ran 2 tests in 0.1s\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=test_log, stderr="", returncode=0),  # run --rm
        ]

        result = docker_run_tests(module_dir, compose_file=compose_file)

        assert isinstance(result, Result)
        assert result.success is True
        assert len(result.data) == 2
        assert all(isinstance(r, TestResult) for r in result.data)
        assert all(r.passed is True for r in result.data)


class TestDockerRunTestsFailure:
    """Test run with failures returns TestResult with passed=False."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_docker_run_tests_failure(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        mock_available.return_value = True
        test_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_create ... ok\n"
            "2026-03-02 10:00:00,100 1 FAIL test_db "
            "odoo.addons.test_mod.tests.test_model: test_invalid\n"
            "AssertionError: expected True got False\n"
            "2026-03-02 10:00:00,200 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: Ran 2 tests in 0.2s\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=test_log, stderr="", returncode=1),  # run --rm
        ]

        result = docker_run_tests(module_dir, compose_file=compose_file)

        assert isinstance(result, Result)
        assert result.success is True
        passed = [r for r in result.data if r.passed]
        failed = [r for r in result.data if not r.passed]
        assert len(passed) == 1
        assert len(failed) == 1


class TestDockerRunTestsTeardown:
    """docker compose down -v is ALWAYS called after test run."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_teardown_always_called(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        mock_available.return_value = True
        # Pre-cleanup succeeds; all subsequent calls (db startup retries) fail
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            Exception("Test exec failed"),  # db attempt 1
            Exception("Test exec failed"),  # db attempt 2
            Exception("Test exec failed"),  # db attempt 3
        ]

        result = docker_run_tests(module_dir, compose_file=compose_file)

        # 2 teardowns from _start_db_with_retry retries + 1 from finally block
        assert mock_teardown.call_count == 3
        assert isinstance(result, Result)
        assert result.success is False


# --- Docker not available tests ---


class TestDockerNotAvailableInstall:
    """When Docker unavailable, install returns graceful degradation."""

    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_docker_not_available_install(
        self, mock_available: MagicMock, module_dir: Path
    ) -> None:
        mock_available.return_value = False

        result = docker_install_module(module_dir)

        assert isinstance(result, Result)
        assert result.success is False
        assert "Docker not available" in result.errors


class TestDockerNotAvailableTests:
    """When Docker unavailable, run_tests returns empty tuple."""

    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_docker_not_available_tests(
        self, mock_available: MagicMock, module_dir: Path
    ) -> None:
        mock_available.return_value = False

        result = docker_run_tests(module_dir)

        assert isinstance(result, Result)
        assert result.success is False
        assert "Docker not available" in result.errors


# --- Timeout test ---


class TestDockerTimeout:
    """When subprocess times out, returns failure result."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_docker_install_timeout(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        mock_available.return_value = True
        # Pre-cleanup succeeds, DB startup succeeds, install command times out
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # DB startup
            subprocess.TimeoutExpired(cmd="docker", timeout=300),  # Install
        ]

        result = docker_install_module(module_dir, compose_file=compose_file)

        assert isinstance(result, Result)
        assert result.success is False
        assert any("timeout" in e.lower() for e in result.errors)
        mock_teardown.assert_called_once()


# --- Integration-level tests (real log parsing, mocked Docker) ---


class TestInstallIntegrationWithRealLogParsing:
    """Mock only subprocess (not log parser) to verify end-to-end log parsing."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_real_odoo17_success_log_parsed(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """Real Odoo 17 install success log is correctly parsed as success."""
        mock_available.return_value = True
        # Realistic Odoo 17 install log output
        odoo17_log = (
            "2026-03-02 10:00:00,123 1 INFO test_db odoo.modules.loading: "
            "Loading module test_mod (1/2)\n"
            "2026-03-02 10:00:01,456 1 INFO test_db odoo.modules.loading: "
            "Loading module base (2/2)\n"
            "2026-03-02 10:00:02,789 1 INFO test_db odoo.modules.loading: "
            "2 modules loaded, 0 modules updated, 0 tests\n"
            "2026-03-02 10:00:03,012 1 INFO test_db odoo.modules.loading: "
            "Modules loaded.\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=odoo17_log, stderr="", returncode=0),  # run --rm
        ]

        result = docker_install_module(module_dir, compose_file=compose_file)

        assert result.success is True
        assert result.data.success is True
        assert result.data.error_message == ""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_real_odoo17_error_log_parsed(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """Real Odoo 17 install error log is correctly parsed as failure."""
        mock_available.return_value = True
        odoo17_error_log = (
            "2026-03-02 10:00:00,123 1 INFO test_db odoo.modules.loading: "
            "Loading module test_mod (1/1)\n"
            "2026-03-02 10:00:01,456 1 ERROR test_db "
            "odoo.modules.registry: Failed to load module test_mod\n"
            "Traceback (most recent call last):\n"
            '  File "/odoo/odoo/modules/registry.py", line 91, in new\n'
            "    odoo.modules.load_modules(cr, force_demo)\n"
            "KeyError: 'missing_field'\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=odoo17_error_log, stderr="", returncode=1),  # run --rm
        ]

        result = docker_install_module(module_dir, compose_file=compose_file)

        assert result.success is True  # Result envelope succeeds
        assert result.data.success is False  # Install itself failed
        assert result.data.error_message != ""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_empty_log_output_parsed_as_failure(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """Empty log output results in install failure (not crash)."""
        mock_available.return_value = True
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout="", stderr="", returncode=0),  # run --rm
        ]

        result = docker_install_module(module_dir, compose_file=compose_file)

        assert result.success is True
        assert result.data.success is False
        assert result.data.error_message != ""


class TestRunTestsIntegrationWithRealLogParsing:
    """Mock only subprocess to verify end-to-end test log parsing."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_odoo17_test_start_format_parsed(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """Odoo 17 'Starting ClassName.test_method ...' format is parsed."""
        mock_available.return_value = True
        odoo17_test_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: Starting TestModel.test_create ...\n"
            "2026-03-02 10:00:00,500 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: Starting TestModel.test_write ...\n"
            "2026-03-02 10:00:01,000 1 INFO test_db "
            "odoo.tests.stats: test_mod: 2 tests 1.0s 42 queries\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=odoo17_test_log, stderr="", returncode=0),  # run --rm
        ]

        result = docker_run_tests(module_dir, compose_file=compose_file)

        assert result.success is True
        assert len(result.data) == 2
        assert all(r.passed for r in result.data)
        test_names = {r.test_name for r in result.data}
        assert "test_create" in test_names
        assert "test_write" in test_names

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_mixed_pass_fail_parsed(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """Mix of passing and failing tests parsed correctly."""
        mock_available.return_value = True
        mixed_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: Starting TestModel.test_create ...\n"
            "2026-03-02 10:00:00,500 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: Starting TestModel.test_write ...\n"
            "2026-03-02 10:00:01,000 1 FAIL test_db "
            "odoo.addons.test_mod.tests.test_model: test_write\n"
            "AssertionError: expected 42 got 0\n"
            "2026-03-02 10:00:01,500 1 INFO test_db "
            "odoo.tests.stats: test_mod: 2 tests 1.5s 50 queries\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=mixed_log, stderr="", returncode=1),  # run --rm
        ]

        result = docker_run_tests(module_dir, compose_file=compose_file)

        assert result.success is True
        passed = [r for r in result.data if r.passed]
        failed = [r for r in result.data if not r.passed]
        assert len(passed) == 1
        assert passed[0].test_name == "test_create"
        assert len(failed) == 1
        assert failed[0].test_name == "test_write"
        assert failed[0].error_message != ""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_log_in_stderr_also_parsed(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """Log output in stderr (not stdout) is still parsed correctly."""
        mock_available.return_value = True
        stderr_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_read ... ok\n"
            "2026-03-02 10:00:00,100 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: Ran 1 tests in 0.1s\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout="", stderr=stderr_log, returncode=0),  # run --rm
        ]

        result = docker_run_tests(module_dir, compose_file=compose_file)

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0].test_name == "test_read"
        assert result.data[0].passed is True


# --- Module name validation tests ---


class TestModuleNameValidation:
    """SEC-09: Module name is validated before use in Docker env."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_invalid_module_name_rejected_install(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Install rejects module with invalid name (starts with uppercase)."""
        mock_available.return_value = True
        bad_mod = tmp_path / "BadModule"
        bad_mod.mkdir()

        result = docker_install_module(bad_mod, compose_file=tmp_path / "c.yml")
        assert result.success is False
        assert any("invalid" in e.lower() for e in result.errors)

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_invalid_module_name_rejected_tests(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Run tests rejects module with invalid name (special chars)."""
        mock_available.return_value = True
        bad_mod = tmp_path / "my-module!"
        bad_mod.mkdir()

        result = docker_run_tests(bad_mod, compose_file=tmp_path / "c.yml")
        assert result.success is False
        assert any("invalid" in e.lower() for e in result.errors)


# --- Unique project name tests ---


class TestUniqueProjectNameFormat:
    """Project name should be factory-{module}-{hex8}."""

    def test_format(self) -> None:
        name = _unique_project_name("hr_payroll")
        assert name.startswith("factory-hr_payroll-")
        suffix = name.split("-")[-1]
        assert len(suffix) == 8
        # Verify suffix is valid hex
        int(suffix, 16)

    def test_different_modules_have_different_prefixes(self) -> None:
        name1 = _unique_project_name("hr_payroll")
        name2 = _unique_project_name("sale_order")
        assert name1.startswith("factory-hr_payroll-")
        assert name2.startswith("factory-sale_order-")


class TestUniqueProjectNamesAreUnique:
    """Two calls should produce different names."""

    def test_uniqueness(self) -> None:
        name1 = _unique_project_name("test_mod")
        name2 = _unique_project_name("test_mod")
        assert name1 != name2


class TestProjectNameUsedInComposeCommands:
    """Verify --project-name is passed to all docker compose calls."""

    @patch("amil_utils.validation.docker_runner._unique_project_name")
    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_install_passes_project_name(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        mock_proj_name: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """docker_install_module passes project_name to _run_compose and _teardown."""
        mock_available.return_value = True
        mock_proj_name.return_value = "factory-test_mod-abcd1234"
        success_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.modules.loading: Modules loaded.\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=success_log, stderr="", returncode=0),  # run --rm
        ]

        docker_install_module(module_dir, compose_file=compose_file)

        # All _run_compose calls should include project_name
        for call_args in mock_run.call_args_list:
            assert call_args.kwargs.get("project_name") == "factory-test_mod-abcd1234" or \
                (len(call_args.args) >= 4 and call_args.args[3] == "factory-test_mod-abcd1234") or \
                "project_name" in str(call_args)

    @patch("amil_utils.validation.docker_runner._unique_project_name")
    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_run_tests_passes_project_name(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        mock_proj_name: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """docker_run_tests passes project_name to _run_compose and _teardown."""
        mock_available.return_value = True
        mock_proj_name.return_value = "factory-test_mod-abcd1234"
        test_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_create ... ok\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=test_log, stderr="", returncode=0),  # run --rm
        ]

        docker_run_tests(module_dir, compose_file=compose_file)

        # _teardown should be called with project_name
        mock_teardown.assert_called()
        for tc in mock_teardown.call_args_list:
            assert tc.kwargs.get("project_name") == "factory-test_mod-abcd1234" or \
                (len(tc.args) >= 3 and tc.args[2] == "factory-test_mod-abcd1234")


class TestPreCleanupOnStart:
    """Pre-cleanup with down --remove-orphans runs before starting containers."""

    @patch("amil_utils.validation.docker_runner._unique_project_name")
    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_pre_cleanup_is_first_compose_call(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        mock_proj_name: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """First _run_compose call should be down --remove-orphans (pre-cleanup)."""
        mock_available.return_value = True
        mock_proj_name.return_value = "factory-test_mod-abcd1234"
        success_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.modules.loading: Modules loaded.\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=success_log, stderr="", returncode=0),  # run --rm
        ]

        docker_install_module(module_dir, compose_file=compose_file)

        # First call should be the pre-cleanup (down --remove-orphans)
        first_call_args = mock_run.call_args_list[0]
        compose_args = first_call_args[0][1]  # second positional arg is the args list
        assert "down" in compose_args
        assert "--remove-orphans" in compose_args


# --- Odoo version parameterization tests ---


class TestInstallPassesOdooVersionEnv:
    """docker_install_module passes ODOO_MAJOR_VERSION in compose env."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_odoo_version_17_sets_major_17(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """odoo_version='17.0' should set ODOO_MAJOR_VERSION=17 in compose env."""
        mock_available.return_value = True
        success_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.modules.loading: Modules loaded.\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=success_log, stderr="", returncode=0),  # run --rm
        ]

        docker_install_module(
            module_dir, compose_file=compose_file, odoo_version="17.0"
        )

        # All _run_compose calls should include ODOO_MAJOR_VERSION=17 in env
        for call_obj in mock_run.call_args_list:
            env_arg = call_obj[0][2]  # third positional arg is the env dict
            assert env_arg.get("ODOO_MAJOR_VERSION") == "17", (
                f"Expected ODOO_MAJOR_VERSION='17' in env, got: {env_arg}"
            )

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_default_odoo_version_is_19(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """Default odoo_version should produce ODOO_MAJOR_VERSION=19."""
        mock_available.return_value = True
        success_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.modules.loading: Modules loaded.\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=success_log, stderr="", returncode=0),  # run --rm
        ]

        docker_install_module(module_dir, compose_file=compose_file)

        # All _run_compose calls should include ODOO_MAJOR_VERSION=19 in env
        for call_obj in mock_run.call_args_list:
            env_arg = call_obj[0][2]  # third positional arg is the env dict
            assert env_arg.get("ODOO_MAJOR_VERSION") == "19", (
                f"Expected ODOO_MAJOR_VERSION='19' in env, got: {env_arg}"
            )


class TestRunTestsPassesOdooVersionEnv:
    """docker_run_tests passes ODOO_MAJOR_VERSION in compose env."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_odoo_version_18_sets_major_18(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """odoo_version='18.0' should set ODOO_MAJOR_VERSION=18 in compose env."""
        mock_available.return_value = True
        test_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_create ... ok\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=test_log, stderr="", returncode=0),  # run --rm
        ]

        docker_run_tests(
            module_dir, compose_file=compose_file, odoo_version="18.0"
        )

        # All _run_compose calls should include ODOO_MAJOR_VERSION=18 in env
        for call_obj in mock_run.call_args_list:
            env_arg = call_obj[0][2]  # third positional arg is the env dict
            assert env_arg.get("ODOO_MAJOR_VERSION") == "18", (
                f"Expected ODOO_MAJOR_VERSION='18' in env, got: {env_arg}"
            )

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_default_odoo_version_is_19(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """Default odoo_version for run_tests should produce ODOO_MAJOR_VERSION=19."""
        mock_available.return_value = True
        test_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.addons.test_mod.tests.test_model: test_create ... ok\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=test_log, stderr="", returncode=0),  # run --rm
        ]

        docker_run_tests(module_dir, compose_file=compose_file)

        # All _run_compose calls should include ODOO_MAJOR_VERSION=19 in env
        for call_obj in mock_run.call_args_list:
            env_arg = call_obj[0][2]  # third positional arg is the env dict
            assert env_arg.get("ODOO_MAJOR_VERSION") == "19", (
                f"Expected ODOO_MAJOR_VERSION='19' in env, got: {env_arg}"
            )


class TestTeardownReceivesOdooVersionEnv:
    """_teardown receives ODOO_MAJOR_VERSION so 'down' uses the correct image."""

    @patch("amil_utils.validation.docker_runner._teardown")
    @patch("amil_utils.validation.docker_runner._run_compose")
    @patch("amil_utils.validation.docker_runner.check_docker_available")
    def test_teardown_env_includes_odoo_major_version(
        self,
        mock_available: MagicMock,
        mock_run: MagicMock,
        mock_teardown: MagicMock,
        module_dir: Path,
        compose_file: Path,
    ) -> None:
        """_teardown should receive env dict with ODOO_MAJOR_VERSION."""
        mock_available.return_value = True
        success_log = (
            "2026-03-02 10:00:00,000 1 INFO test_db "
            "odoo.modules.loading: Modules loaded.\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout="", stderr="", returncode=0),  # pre-cleanup
            MagicMock(stdout="", stderr="", returncode=0),  # up -d --wait db
            MagicMock(stdout=success_log, stderr="", returncode=0),  # run --rm
        ]

        docker_install_module(
            module_dir, compose_file=compose_file, odoo_version="17.0"
        )

        # _teardown should have been called with env containing ODOO_MAJOR_VERSION
        mock_teardown.assert_called()
        teardown_call = mock_teardown.call_args
        teardown_env = teardown_call[0][1]  # second positional arg is env dict
        assert teardown_env.get("ODOO_MAJOR_VERSION") == "17", (
            f"Expected ODOO_MAJOR_VERSION='17' in teardown env, got: {teardown_env}"
        )
