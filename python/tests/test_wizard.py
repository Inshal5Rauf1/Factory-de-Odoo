"""Tests for the GitHub auth setup wizard."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from amil_utils.search.wizard import AuthStatus, check_github_auth, format_auth_guidance


class TestCheckGithubAuth:
    """Tests for check_github_auth() function."""

    @patch("amil_utils.search.wizard.subprocess.run")
    @patch.dict("os.environ", {}, clear=True)
    def test_gh_not_installed(self, mock_run: MagicMock) -> None:
        """When gh CLI is not installed, subprocess raises FileNotFoundError."""
        mock_run.side_effect = FileNotFoundError("No such file or directory: 'gh'")
        status = check_github_auth()
        assert status.gh_installed is False
        assert status.gh_authenticated is False
        assert status.token_source is None
        assert "https://cli.github.com/" in status.guidance

    @patch("amil_utils.search.wizard.subprocess.run")
    @patch.dict("os.environ", {}, clear=True)
    def test_gh_not_authenticated(self, mock_run: MagicMock) -> None:
        """When gh is installed but not authenticated, returncode != 0."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not logged in")
        status = check_github_auth()
        assert status.gh_installed is True
        assert status.gh_authenticated is False
        assert status.token_source is None
        assert "gh auth login" in status.guidance

    @patch("amil_utils.search.wizard.subprocess.run")
    @patch.dict("os.environ", {}, clear=True)
    def test_gh_authenticated(self, mock_run: MagicMock) -> None:
        """When gh auth status succeeds, token_source is 'gh_cli'."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Logged in", stderr="")
        status = check_github_auth()
        assert status.gh_installed is True
        assert status.gh_authenticated is True
        assert status.token_source == "gh_cli"
        assert "Authenticated" in status.guidance

    @patch("amil_utils.search.wizard.subprocess.run")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test123"}, clear=True)
    def test_env_token_takes_precedence(self, mock_run: MagicMock) -> None:
        """When GITHUB_TOKEN env var is set, subprocess is NOT called."""
        status = check_github_auth()
        assert status.token_source == "env"
        assert status.gh_installed is True
        assert status.gh_authenticated is True
        assert "GITHUB_TOKEN" in status.guidance
        mock_run.assert_not_called()

    @patch("amil_utils.search.wizard.subprocess.run")
    @patch.dict("os.environ", {}, clear=True)
    def test_timeout_handled(self, mock_run: MagicMock) -> None:
        """Subprocess timeout does not crash, returns reasonable AuthStatus."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["gh", "auth", "status"], timeout=10)
        status = check_github_auth()
        assert isinstance(status, AuthStatus)
        assert status.gh_installed is True
        # Auth unknown after timeout
        assert status.gh_authenticated is False


class TestFormatAuthGuidance:
    """Tests for format_auth_guidance() function."""

    def test_format_guidance_not_installed(self) -> None:
        """When gh is not installed, guidance contains install URL."""
        status = AuthStatus(
            gh_installed=False,
            gh_authenticated=False,
            token_source=None,
            guidance="gh not installed",
        )
        output = format_auth_guidance(status)
        assert "https://cli.github.com/" in output
        assert "not installed" in output.lower()

    def test_format_guidance_not_authenticated(self) -> None:
        """When gh is installed but not authenticated, guidance says 'gh auth login'."""
        status = AuthStatus(
            gh_installed=True,
            gh_authenticated=False,
            token_source=None,
            guidance="not authenticated",
        )
        output = format_auth_guidance(status)
        assert "gh auth login" in output

    def test_format_guidance_authenticated(self) -> None:
        """When authenticated, guidance says 'OK'."""
        status = AuthStatus(
            gh_installed=True,
            gh_authenticated=True,
            token_source="gh_cli",
            guidance="Authenticated via gh CLI.",
        )
        output = format_auth_guidance(status)
        assert "OK" in output
