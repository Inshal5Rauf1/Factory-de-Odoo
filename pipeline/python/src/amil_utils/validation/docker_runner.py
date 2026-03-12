"""Docker lifecycle management for Odoo module validation.

Manages ephemeral Docker Compose environments (Odoo 17 + PostgreSQL 16)
for module installation and test execution. Containers are always torn
down after validation, even on errors.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from odoo_gen_utils.validation.log_parser import parse_install_log, parse_test_log
from odoo_gen_utils.validation.types import InstallResult, Result, TestResult

logger = logging.getLogger(__name__)

_VALID_MODULE_NAME = re.compile(r"[a-z][a-z0-9_]+$")


def _validate_module_name(name: str) -> str | None:
    """Validate an Odoo module name.

    Returns None if valid, or an error message if invalid.
    """
    if not _VALID_MODULE_NAME.fullmatch(name):
        return (
            f"Invalid module name '{name}': must start with a lowercase letter "
            f"and contain only lowercase letters, digits, and underscores"
        )
    return None


def check_docker_available() -> bool:
    """Check if Docker CLI is present and functional.

    Returns:
        True if docker is installed and the daemon is reachable.
    """
    if shutil.which("docker") is None:
        return False

    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def get_compose_file() -> Path:
    """Return the path to the docker-compose.yml shipped with the package.

    Resolution order:
    1. ``ODOO_GEN_COMPOSE_FILE`` environment variable (explicit override).
    2. ``importlib.resources`` lookup inside ``odoo_gen_utils/data/``.

    Returns:
        Path to docker-compose.yml.
    """
    env_path = os.environ.get("ODOO_GEN_COMPOSE_FILE")
    if env_path:
        return Path(env_path)

    from importlib.resources import files

    ref = files("odoo_gen_utils").joinpath("data", "docker-compose.yml")
    return Path(str(ref))


def _run_compose(
    compose_file: Path,
    args: list[str],
    env: dict[str, str],
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run a docker compose command with the given arguments.

    Args:
        compose_file: Path to docker-compose.yml.
        args: Arguments to pass after 'docker compose -f <file>'.
        env: Environment variables to merge with os.environ.
        timeout: Subprocess timeout in seconds.

    Returns:
        CompletedProcess with stdout and stderr captured as text.
    """
    cmd = ["docker", "compose", "-f", str(compose_file), *args]
    merged_env = {**os.environ, **env}
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=merged_env,
    )


def _teardown(compose_file: Path, env: dict[str, str]) -> None:
    """Tear down Docker containers and volumes.

    Runs 'docker compose down -v --remove-orphans' with up to 3 retry
    attempts using exponential backoff. Logs to stderr on final failure.
    This function never raises.
    """
    cmd = [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "down",
        "-v",
        "--remove-orphans",
    ]
    merged_env = {**os.environ, **env}
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,
                env=merged_env,
            )
            return  # Success — exit immediately
        except Exception:
            if attempt < max_attempts:
                backoff = 2 ** (attempt - 1)  # 1s, 2s
                logger.warning(
                    "Teardown attempt %d/%d failed, retrying in %ds",
                    attempt,
                    max_attempts,
                    backoff,
                    exc_info=True,
                )
                time.sleep(backoff)
            else:
                logger.error(
                    "Teardown failed after %d attempts — containers/volumes may be leaked",
                    max_attempts,
                    exc_info=True,
                )
                # logger.error above already logs; avoid redundant print


def _start_db_with_retry(
    compose_file: Path,
    env: dict[str, str],
    max_attempts: int = 3,
    timeout: int = 120,
) -> None:
    """Start the database service with retry and teardown between attempts.

    Raises the last exception if all attempts fail.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            _run_compose(compose_file, ["up", "-d", "--wait", "db"], env, timeout=timeout)
            return  # Success
        except Exception:
            if attempt < max_attempts:
                backoff = 2 ** (attempt - 1)  # 1s, 2s
                logger.warning(
                    "DB startup attempt %d/%d failed, tearing down and retrying in %ds",
                    attempt,
                    max_attempts,
                    backoff,
                    exc_info=True,
                )
                _teardown(compose_file, env)
                time.sleep(backoff)
            else:
                raise


def docker_install_module(
    module_path: Path,
    compose_file: Path | None = None,
    timeout: int = 300,
) -> Result[InstallResult]:
    """Install an Odoo module in an ephemeral Docker environment.

    Starts Odoo 17 + PostgreSQL 16 containers, runs module installation,
    parses the log output for success/failure, and tears down containers.

    Args:
        module_path: Path to the Odoo module directory.
        compose_file: Path to docker-compose.yml. Uses default if None.
        timeout: Timeout in seconds for the install command.

    Returns:
        Result.ok(InstallResult) on successful execution,
        Result.fail(message) on infrastructure errors.
    """
    if not check_docker_available():
        return Result.fail("Docker not available")

    if compose_file is None:
        compose_file = get_compose_file()

    module_name = module_path.name
    name_error = _validate_module_name(module_name)
    if name_error:
        return Result.fail(name_error)

    env = {
        "MODULE_PATH": str(module_path.resolve()),
        "MODULE_NAME": module_name,
    }

    try:
        # Start only the database service with retry for transient failures.
        _start_db_with_retry(compose_file, env)

        # Install in a fresh container (no entrypoint server conflict).
        result = _run_compose(
            compose_file,
            [
                "run",
                "--rm",
                "-T",
                "odoo",
                "odoo",
                "-i",
                module_name,
                "-d",
                "test_db",
                "--stop-after-init",
                "--no-http",
                "--log-level=info",
            ],
            env,
            timeout=timeout,
        )

        combined_output = result.stdout + result.stderr
        success, error_msg = parse_install_log(combined_output)

        return Result.ok(
            InstallResult(
                success=success,
                log_output=combined_output,
                error_message=error_msg,
            )
        )
    except subprocess.TimeoutExpired:
        return Result.fail(f"Timeout after {timeout}s waiting for module install")
    except Exception as exc:
        return Result.fail(str(exc))
    finally:
        _teardown(compose_file, env)


def docker_run_tests(
    module_path: Path,
    compose_file: Path | None = None,
    timeout: int = 600,
) -> Result[tuple[TestResult, ...]]:
    """Run Odoo module tests in an ephemeral Docker environment.

    Starts Odoo 17 + PostgreSQL 16 containers, runs module tests with
    --test-enable, parses per-test results from the log output, and
    tears down containers.

    Args:
        module_path: Path to the Odoo module directory.
        compose_file: Path to docker-compose.yml. Uses default if None.
        timeout: Timeout in seconds for the test command.

    Returns:
        Result.ok(test_results) on successful execution,
        Result.fail(message) on infrastructure errors.
    """
    if not check_docker_available():
        return Result.fail("Docker not available")

    if compose_file is None:
        compose_file = get_compose_file()

    module_name = module_path.name
    name_error = _validate_module_name(module_name)
    if name_error:
        return Result.fail(name_error)

    env = {
        "MODULE_PATH": str(module_path.resolve()),
        "MODULE_NAME": module_name,
    }

    try:
        # Start only the database service with retry for transient failures.
        _start_db_with_retry(compose_file, env)

        # Run tests in a fresh container (no entrypoint server conflict).
        # --test-tags filters to only this module's tests, avoiding the
        # 900+ base module tests that would otherwise run.
        result = _run_compose(
            compose_file,
            [
                "run",
                "--rm",
                "-T",
                "odoo",
                "odoo",
                "-i",
                module_name,
                "-d",
                "test_db",
                "--test-enable",
                f"--test-tags={module_name}",
                "--stop-after-init",
                "--no-http",
                "--log-level=test",
            ],
            env,
            timeout=timeout,
        )

        combined_output = result.stdout + result.stderr
        return Result.ok(parse_test_log(combined_output))
    except subprocess.TimeoutExpired:
        logger.warning("Docker test run timed out after %ds", timeout)
        return Result.fail(f"Docker test run timed out after {timeout}s")
    except Exception as exc:
        logger.warning("Docker test run failed", exc_info=True)
        return Result.fail(f"Docker test run failed: {exc}")
    finally:
        _teardown(compose_file, env)
