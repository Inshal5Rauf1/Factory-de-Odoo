"""Tests for pylint-odoo runner (pylint_runner.py).

Uses mocked subprocess to verify command construction and output parsing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from amil_utils.validation.pylint_runner import (
    parse_pylint_output,
    run_pylint_odoo,
)
from amil_utils.validation.types import Result, Violation


# Sample pylint JSON2 output (verified structure from research)
SAMPLE_JSON2 = json.dumps(
    {
        "messages": [
            {
                "type": "convention",
                "symbol": "manifest-required-author",
                "message": "Author is required in manifest",
                "messageId": "C8101",
                "confidence": "UNDEFINED",
                "module": "test_mod",
                "obj": "",
                "line": 5,
                "column": 4,
                "endLine": 5,
                "endColumn": 12,
                "path": "test_mod/__manifest__.py",
                "absolutePath": "/tmp/test_mod/__manifest__.py",
            },
            {
                "type": "warning",
                "symbol": "attribute-deprecated",
                "message": "Use of deprecated attribute 'attrs'",
                "messageId": "W8105",
                "confidence": "HIGH",
                "module": "test_mod",
                "obj": "",
                "line": 20,
                "column": 8,
                "endLine": 20,
                "endColumn": 30,
                "path": "test_mod/views/partner_view.xml",
                "absolutePath": "/tmp/test_mod/views/partner_view.xml",
            },
        ],
        "statistics": {
            "messageTypeCount": {
                "fatal": 0,
                "error": 0,
                "warning": 1,
                "refactor": 0,
                "convention": 1,
                "info": 0,
            },
            "modulesLinted": 1,
            "score": 5.0,
        },
    }
)


class TestParsePylintOutput:
    """Tests for parse_pylint_output function."""

    def test_parse_pylint_json2(self) -> None:
        """Parse valid JSON2 output into Violation objects."""
        violations = parse_pylint_output(SAMPLE_JSON2)
        assert len(violations) == 2

        v1 = violations[0]
        assert v1.file == "test_mod/__manifest__.py"
        assert v1.line == 5
        assert v1.column == 4
        assert v1.rule_code == "C8101"
        assert v1.symbol == "manifest-required-author"
        assert v1.severity == "convention"
        assert v1.message == "Author is required in manifest"

        v2 = violations[1]
        assert v2.file == "test_mod/views/partner_view.xml"
        assert v2.line == 20
        assert v2.severity == "warning"
        assert v2.symbol == "attribute-deprecated"

    def test_parse_pylint_empty(self) -> None:
        """Empty string returns empty tuple."""
        assert parse_pylint_output("") == ()

    def test_parse_pylint_no_messages(self) -> None:
        """JSON with empty messages list returns empty tuple."""
        result = parse_pylint_output(json.dumps({"messages": [], "statistics": {}}))
        assert result == ()

    def test_parse_pylint_invalid_json(self) -> None:
        """Invalid JSON returns empty tuple."""
        assert parse_pylint_output("not json {{{") == ()

    def test_parse_returns_tuple(self) -> None:
        """Result is a tuple (immutable), not a list."""
        violations = parse_pylint_output(SAMPLE_JSON2)
        assert isinstance(violations, tuple)


class TestRunPylintOdoo:
    """Tests for run_pylint_odoo function."""

    @patch("amil_utils.validation.pylint_runner.subprocess.run")
    def test_run_pylint_odoo_invocation(self, mock_run: MagicMock) -> None:
        """run_pylint_odoo calls subprocess.run with correct args and returns Result."""
        mock_run.return_value = MagicMock(stdout=SAMPLE_JSON2, stderr="")
        module_path = Path("/tmp/test_mod")

        result = run_pylint_odoo(module_path)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]

        # Verify required flags
        assert cmd[0] == sys.executable
        assert cmd[1] == "-m"
        assert cmd[2] == "pylint"
        assert "--load-plugins=pylint_odoo" in cmd
        assert "--output-format=json2" in cmd
        assert any("import-error" in arg for arg in cmd if arg.startswith("--disable="))
        assert str(module_path) in cmd

        # Verify Result wrapper
        assert isinstance(result, Result)
        assert result.success is True
        assert len(result.data) == 2

    @patch("amil_utils.validation.pylint_runner.subprocess.run")
    def test_run_pylint_odoo_with_pylintrc(self, mock_run: MagicMock) -> None:
        """When pylintrc_path is provided and exists, --rcfile is included."""
        mock_run.return_value = MagicMock(stdout=SAMPLE_JSON2, stderr="")

        with patch.object(Path, "exists", return_value=True):
            module_path = Path("/tmp/test_mod")
            pylintrc_path = Path("/tmp/test_mod/.pylintrc-odoo")

            run_pylint_odoo(module_path, pylintrc_path=pylintrc_path)

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert any(
                arg.startswith("--rcfile=") for arg in cmd
            ), f"--rcfile not found in command: {cmd}"

    @patch("amil_utils.validation.pylint_runner.subprocess.run")
    def test_run_pylint_odoo_timeout(self, mock_run: MagicMock) -> None:
        """subprocess.TimeoutExpired returns Result.fail with error message."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["pylint"], timeout=120)
        module_path = Path("/tmp/test_mod")

        result = run_pylint_odoo(module_path)
        assert isinstance(result, Result)
        assert result.success is False
        assert len(result.errors) > 0
        assert "timed out" in result.errors[0]

    @patch("amil_utils.validation.pylint_runner.subprocess.run")
    def test_run_pylint_odoo_subprocess_error(self, mock_run: MagicMock) -> None:
        """Other subprocess errors return Result.fail with error message."""
        mock_run.side_effect = OSError("Command not found")
        module_path = Path("/tmp/test_mod")

        result = run_pylint_odoo(module_path)
        assert isinstance(result, Result)
        assert result.success is False
        assert len(result.errors) > 0
        assert "failed" in result.errors[0].lower()

    @patch("amil_utils.validation.pylint_runner.subprocess.run")
    def test_run_pylint_odoo_empty_output(self, mock_run: MagicMock) -> None:
        """Empty stdout returns Result.ok with empty tuple."""
        mock_run.return_value = MagicMock(stdout="", stderr="")
        module_path = Path("/tmp/test_mod")

        result = run_pylint_odoo(module_path)
        assert isinstance(result, Result)
        assert result.success is True
        assert result.data == ()

    @patch("amil_utils.validation.pylint_runner.subprocess.run")
    def test_run_pylint_odoo_timeout_kwarg(self, mock_run: MagicMock) -> None:
        """timeout parameter is passed to subprocess.run."""
        mock_run.return_value = MagicMock(stdout="", stderr="")
        module_path = Path("/tmp/test_mod")

        run_pylint_odoo(module_path, timeout=60)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 60
