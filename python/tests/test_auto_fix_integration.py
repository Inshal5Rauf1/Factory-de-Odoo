"""Integration tests for validate --auto-fix CLI flow.

Tests exercise the full auto-fix pipeline on a fixture module with
known violations: unused imports (W0611), redundant string= (W8113),
and missing mail.thread inheritance.

All tests use shutil.copytree to work on temporary copies so the
original fixture remains pristine. Tests run without Docker
(--pylint-only flag).

AFIX-02: Integration test for validate --auto-fix CLI command.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from click.testing import CliRunner

from amil_utils.auto_fix import fix_missing_mail_thread, fix_unused_imports
from amil_utils.cli import main
from amil_utils.validation.types import Result, Violation

# Path to the fixture module with known violations
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "auto_fix_module"

# Non-fixable violations that remain after auto-fix
_NON_FIXABLE = (
    Violation(
        file="__manifest__.py",
        line=1,
        column=0,
        rule_code="C8101",
        symbol="manifest-required-author",
        severity="convention",
        message="One of the following authors must be present in manifest: "
        "'Odoo Community Association (OCA)'",
    ),
    Violation(
        file="__manifest__.py",
        line=1,
        column=0,
        rule_code="C8112",
        symbol="missing-readme",
        severity="convention",
        message="Missing ./README.rst file.",
    ),
)


@pytest.fixture()
def temp_module(tmp_path: Path) -> Path:
    """Copy the fixture module to a temporary directory for isolation."""
    dest = tmp_path / "auto_fix_module"
    shutil.copytree(FIXTURE_DIR, dest)
    return dest


def _read_training_py(module_path: Path) -> str:
    """Read the models/training.py file content from a module."""
    return (module_path / "models" / "training.py").read_text(encoding="utf-8")


def _build_initial_violations() -> tuple[Violation, ...]:
    """Build violations matching the pristine fixture (before any fixes).

    Line numbers match the original fixture file layout:
      1: from odoo import api, fields, models
      2: from odoo.exceptions import ValidationError
      3: (empty)
      4: (empty)
      5: class HrTrainingAutoFixTest(models.Model):
      6:     _name = "hr.training.auto.fix.test"
      7:     _description = "Auto Fix Test Training"
      8: (empty)
      9:     name = fields.Char(string="Name", required=True)
    """
    return (
        Violation(
            file="models/training.py",
            line=1,
            column=0,
            rule_code="W0611",
            symbol="unused-import",
            severity="warning",
            message="Unused api imported from odoo",
        ),
        Violation(
            file="models/training.py",
            line=2,
            column=0,
            rule_code="W0611",
            symbol="unused-import",
            severity="warning",
            message="Unused ValidationError imported from odoo.exceptions",
        ),
        Violation(
            file="models/training.py",
            line=9,
            column=11,
            rule_code="W8113",
            symbol="attribute-string-redundant",
            severity="warning",
            message="The attribute string is redundant. "
            "String parameter equal to name of variable",
        ),
        *_NON_FIXABLE,
    )


def _build_post_import_fix_violations() -> tuple[Violation, ...]:
    """Build violations after unused imports are removed (second pylint cycle).

    After fix_unused_imports removes api from line 1 and removes the
    ValidationError import line entirely, the file layout shifts:
      1: from odoo import fields, models
      2: (empty)
      3: class HrTrainingAutoFixTest(models.Model):
      4:     _name = "hr.training.auto.fix.test"
      5:     _description = "Auto Fix Test Training"
      6: (empty)
      7:     name = fields.Char(string="Name", required=True)

    W8113 now appears at line 7 (shifted from line 9).
    """
    return (
        Violation(
            file="models/training.py",
            line=7,
            column=11,
            rule_code="W8113",
            symbol="attribute-string-redundant",
            severity="warning",
            message="The attribute string is redundant. "
            "String parameter equal to name of variable",
        ),
        *_NON_FIXABLE,
    )


def _make_multi_cycle_mock():
    """Create a mock for run_pylint_odoo that simulates realistic multi-cycle behavior.

    Cycle 1: returns all initial violations (W0611 x2, W8113, C8101, C8112)
    Cycle 2: returns violations with corrected line numbers after import fixes
    Cycle 3+: returns only non-fixable violations
    """
    call_count = 0

    def mock_run_pylint(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Result.ok(_build_initial_violations())
        if call_count == 2:
            return Result.ok(_build_post_import_fix_violations())
        return Result.ok(_NON_FIXABLE)

    return mock_run_pylint


class TestValidateAutoFixIntegration:
    """Integration tests for the validate --auto-fix --pylint-only CLI."""

    def test_auto_fix_resolves_unused_imports(self, temp_module: Path) -> None:
        """After auto-fix, unused api and ValidationError imports are removed."""
        runner = CliRunner()

        with patch(
            "amil_utils.auto_fix.run_pylint_odoo",
            side_effect=_make_multi_cycle_mock(),
        ):
            runner.invoke(
                main,
                ["validate", str(temp_module), "--auto-fix", "--pylint-only"],
            )

        content = _read_training_py(temp_module)

        # The 'from odoo import' line should not contain 'api'
        for line in content.split("\n"):
            if line.startswith("from odoo import"):
                assert "api" not in line, f"'api' still in import: {line}"

        # ValidationError import line should be removed entirely
        assert "ValidationError" not in content

    def test_auto_fix_resolves_redundant_string(self, temp_module: Path) -> None:
        """After auto-fix, redundant string="Name" is removed from the field."""
        runner = CliRunner()

        with patch(
            "amil_utils.auto_fix.run_pylint_odoo",
            side_effect=_make_multi_cycle_mock(),
        ):
            runner.invoke(
                main,
                ["validate", str(temp_module), "--auto-fix", "--pylint-only"],
            )

        content = _read_training_py(temp_module)
        assert 'string="Name"' not in content
        # Field should still be present with required=True
        assert "required=True" in content

    def test_auto_fix_reduces_violation_count(self, temp_module: Path) -> None:
        """After auto-fix, the CLI reports that violations were fixed."""
        initial_violations = _build_initial_violations()
        fixable_count = sum(
            1 for v in initial_violations if v.rule_code in ("W0611", "W8113")
        )
        assert fixable_count >= 3, "Fixture should have at least 3 fixable violations"

        runner = CliRunner()

        with patch(
            "amil_utils.auto_fix.run_pylint_odoo",
            side_effect=_make_multi_cycle_mock(),
        ):
            result = runner.invoke(
                main,
                ["validate", str(temp_module), "--auto-fix", "--pylint-only"],
            )

        # The CLI should report some fixes were applied
        assert "Auto-fix" in (result.output or "")

    def test_mail_thread_fix_adds_inherit(self, temp_module: Path) -> None:
        """Calling fix_missing_mail_thread directly adds _inherit to the model."""
        content_before = _read_training_py(temp_module)
        assert "mail.thread" not in content_before

        applied = fix_missing_mail_thread(temp_module)
        assert applied is True

        content_after = _read_training_py(temp_module)
        assert "_inherit = ['mail.thread', 'mail.activity.mixin']" in content_after

    def test_fixture_not_modified(self, temp_module: Path) -> None:
        """After running auto-fix on a copy, original fixture files are unchanged."""
        original_manifest = (FIXTURE_DIR / "__manifest__.py").read_text(encoding="utf-8")
        original_training = (FIXTURE_DIR / "models" / "training.py").read_text(
            encoding="utf-8"
        )

        runner = CliRunner()

        with patch(
            "amil_utils.auto_fix.run_pylint_odoo",
            side_effect=_make_multi_cycle_mock(),
        ):
            runner.invoke(
                main,
                ["validate", str(temp_module), "--auto-fix", "--pylint-only"],
            )

        # Verify originals are unchanged
        assert (FIXTURE_DIR / "__manifest__.py").read_text(
            encoding="utf-8"
        ) == original_manifest
        assert (FIXTURE_DIR / "models" / "training.py").read_text(
            encoding="utf-8"
        ) == original_training

    def test_fix_unused_imports_directly(self, temp_module: Path) -> None:
        """fix_unused_imports removes api and ValidationError when not used."""
        training_file = temp_module / "models" / "training.py"
        content_before = training_file.read_text(encoding="utf-8")

        assert "api" in content_before
        assert "ValidationError" in content_before

        applied = fix_unused_imports(training_file)
        assert applied is True

        content_after = training_file.read_text(encoding="utf-8")
        # api removed from 'from odoo import' line
        for line in content_after.split("\n"):
            if line.startswith("from odoo import"):
                assert "api" not in line
        # ValidationError import line removed
        assert "ValidationError" not in content_after
