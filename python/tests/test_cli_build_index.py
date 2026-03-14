"""Tests for build-index and index-status CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from amil_utils.cli import main
from amil_utils.search.types import IndexStatus


class TestBuildIndexCommand:
    """build-index CLI command tests."""

    @patch("amil_utils.search.wizard.check_github_auth")
    @patch("amil_utils.search.get_github_token", return_value=None)
    def test_no_token_exits_code_1(self, mock_token: MagicMock, mock_wizard: MagicMock) -> None:
        from amil_utils.search.wizard import AuthStatus

        mock_wizard.return_value = AuthStatus(
            gh_installed=True,
            gh_authenticated=False,
            token_source=None,
            guidance="not authenticated",
        )
        runner = CliRunner()
        result = runner.invoke(main, ["build-index"])
        assert result.exit_code == 1
        assert "gh auth login" in result.output

    @patch("amil_utils.search.get_github_token", return_value=None)
    def test_no_token_no_wizard_exits_code_1(self, mock_token: MagicMock) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["build-index", "--no-wizard"])
        assert result.exit_code == 1
        assert "GitHub authentication required" in result.output
        assert "gh auth login" in result.output

    @patch("amil_utils.search.build_oca_index", return_value=42)
    @patch("amil_utils.search.get_github_token", return_value="test-token")
    def test_with_token_prints_success(self, mock_token: MagicMock, mock_build: MagicMock) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["build-index"])
        assert result.exit_code == 0
        assert "42" in result.output
        assert "Indexed" in result.output
        mock_build.assert_called_once()


class TestIndexStatusCommand:
    """index-status CLI command tests."""

    @patch(
        "amil_utils.search.get_index_status",
        return_value=IndexStatus(
            exists=True,
            module_count=150,
            last_built="2026-01-15T10:00:00Z",
            db_path="/tmp/test_db",
            size_bytes=1024,
        ),
    )
    def test_json_output(self, mock_status: MagicMock) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["index-status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["exists"] is True
        assert data["module_count"] == 150
        assert "db_path" in data

    @patch(
        "amil_utils.search.get_index_status",
        return_value=IndexStatus(
            exists=True,
            module_count=150,
            last_built="2026-01-15T10:00:00Z",
            db_path="/tmp/test_db",
            size_bytes=1024,
        ),
    )
    def test_human_readable_output(self, mock_status: MagicMock) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["index-status"])
        assert result.exit_code == 0
        assert "150" in result.output
        assert "/tmp/test_db" in result.output
