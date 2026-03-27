"""Golden path E2E regression test for the full Odoo module pipeline.

Renders a realistic module spec (hr_training with mail dependency, computed fields,
and plain models) through the template engine, Docker-installs it in Odoo 17.0,
and runs its Odoo tests -- proving the full pipeline produces a working module
and catching template regressions automatically.

Tests are designed to run in order:
  1. test_golden_path_render - renders the module, asserts expected files exist
  2. test_golden_path_docker_install - installs in Docker, asserts success
  3. test_golden_path_docker_tests - runs Odoo tests, asserts all pass

If the render fixture fails, both Docker tests are automatically skipped (fixture
error). Tests 2 and 3 run in alphabetical order (docker_install before docker_tests).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from amil_utils.renderer import get_template_dir, render_module
from amil_utils.validation.docker_runner import (
    check_docker_available,
    docker_install_module,
    docker_run_tests,
)

pytestmark = pytest.mark.docker

skip_no_docker = pytest.mark.skipif(
    not check_docker_available(),
    reason="Docker daemon not available -- skipping Docker integration tests",
)

# ---------------------------------------------------------------------------
# Golden path spec: exercises mail dependency, computed fields, plain models,
# conditional api import (needs_api True vs False), and inherit_list with
# mail.thread on both models.
# ---------------------------------------------------------------------------
GOLDEN_PATH_SPEC: dict = {
    "module_name": "hr_training",
    "depends": ["base", "mail"],
    "models": [
        {
            "name": "hr.training.course",
            "description": "Training Course",
            "fields": [
                {
                    "name": "name",
                    "type": "Char",
                    "required": True,
                    "string": "Course Name",
                },
                {
                    "name": "duration",
                    "type": "Integer",
                    "string": "Duration (Hours)",
                },
                {
                    "name": "description",
                    "type": "Text",
                    "string": "Description",
                },
                {
                    "name": "total_hours",
                    "type": "Float",
                    "string": "Total Hours",
                    "compute": "_compute_total_hours",
                    "depends": ["duration"],
                },
                {
                    "name": "state",
                    "type": "Selection",
                    "string": "Status",
                    "selection": [
                        ["draft", "Draft"],
                        ["confirmed", "Confirmed"],
                        ["done", "Done"],
                    ],
                    "default": "draft",
                },
            ],
        },
        {
            "name": "hr.training.session",
            "description": "Training Session",
            "fields": [
                {
                    "name": "name",
                    "type": "Char",
                    "required": True,
                    "string": "Session Name",
                },
                {
                    "name": "date",
                    "type": "Date",
                    "string": "Date",
                },
                {
                    "name": "attendee_count",
                    "type": "Integer",
                    "string": "Attendee Count",
                },
            ],
        },
    ],
}

# Expected files in the rendered module directory.
EXPECTED_FILES: tuple[str, ...] = (
    "__manifest__.py",
    "__init__.py",
    "models/__init__.py",
    "models/hr_training_course.py",
    "models/hr_training_session.py",
    "views/hr_training_course_views.xml",
    "views/hr_training_course_action.xml",
    "views/hr_training_session_views.xml",
    "views/hr_training_session_action.xml",
    "views/menu.xml",
    "security/security.xml",
    "security/ir.model.access.csv",
    "tests/__init__.py",
    "tests/test_hr_training_course.py",
    "tests/test_hr_training_session.py",
)


@pytest.fixture(scope="module")
def rendered_module(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Render the golden path spec once and return the module directory.

    This fixture is module-scoped so the spec is rendered once and shared
    across all three test functions. If rendering fails, all tests using
    this fixture are automatically skipped (fixture error).
    """
    base_dir = tmp_path_factory.mktemp("golden_path")
    render_module(GOLDEN_PATH_SPEC, get_template_dir(), base_dir)
    module_dir = base_dir / "hr_training"
    return module_dir


def test_golden_path_render(rendered_module: Path) -> None:
    """Render hr_training module and assert all expected files exist.

    This test does NOT require Docker -- it only validates the template
    rendering pipeline produces a complete module directory.
    """
    assert rendered_module.is_dir(), (
        f"Module directory does not exist: {rendered_module}"
    )

    missing = []
    for rel_path in EXPECTED_FILES:
        full_path = rendered_module / rel_path
        if not full_path.exists():
            missing.append(rel_path)

    assert not missing, (
        f"Missing {len(missing)} expected file(s) in rendered module:\n"
        + "\n".join(f"  - {m}" for m in missing)
    )


@skip_no_docker
def test_golden_path_docker_install(rendered_module: Path) -> None:
    """Docker-install the rendered hr_training module in Odoo 17.0.

    Unwraps Result[InstallResult] before checking InstallResult fields.
    Asserts that InstallResult.success is True and no ImportError appears
    in the installation log output. This validates that the generated module
    is syntactically correct and Odoo can load it.
    """
    result = docker_install_module(rendered_module)

    assert result.success, f"docker_install_module failed: {result.errors}"
    install = result.data

    assert install.success is True, (
        f"Module install failed: {install.error_message}\n"
        f"Log output (last 500 chars): {install.log_output[-500:]}"
    )
    assert "ImportError" not in install.log_output, (
        "ImportError found in install log -- generated module has broken imports:\n"
        f"{install.log_output[-500:]}"
    )


@skip_no_docker
def test_golden_path_docker_tests(rendered_module: Path) -> None:
    """Run the rendered module's own Odoo tests inside Docker.

    Unwraps Result[tuple[TestResult, ...]] before iterating TestResult fields.
    Asserts that at least one TestResult is returned, all tests pass,
    and all test names are non-empty (proving the tests actually ran).
    """
    result = docker_run_tests(rendered_module)

    assert result.success, f"docker_run_tests failed: {result.errors}"
    test_results = result.data

    assert len(test_results) > 0, "Expected at least 1 test result from docker_run_tests"

    failed = [r for r in test_results if not r.passed]
    assert not failed, (
        f"{len(failed)} test(s) failed:\n"
        + "\n".join(
            f"  - {r.test_name}: {r.error_message}" for r in failed
        )
    )

    empty_names = [r for r in test_results if not r.test_name]
    assert not empty_names, (
        f"{len(empty_names)} test result(s) have empty test names -- "
        "tests may not have actually executed"
    )
