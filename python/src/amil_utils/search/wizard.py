"""GitHub auth setup wizard for CLI commands.

Diagnoses the specific GitHub auth failure (gh not installed, not
authenticated, token invalid) and provides targeted remediation steps.
Triggered automatically on auth failure in build-index, search-modules,
and extend-module CLI commands.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthStatus:
    """Result of a GitHub authentication check.

    Attributes:
        gh_installed: Whether the gh CLI binary was found on PATH.
        gh_authenticated: Whether gh CLI reports an active session.
        token_source: Where the token was found: "env", "gh_cli", or None.
        guidance: Human-readable actionable message for the user.
    """

    gh_installed: bool
    gh_authenticated: bool
    token_source: str | None
    guidance: str


def check_github_auth() -> AuthStatus:
    """Diagnose the current GitHub authentication state.

    Check order:
    1. GITHUB_TOKEN environment variable (returns immediately if set).
    2. ``gh auth status`` subprocess call.

    Returns:
        AuthStatus with diagnostic fields populated.
    """
    # Fast path: env var set means token is available
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return AuthStatus(
            gh_installed=True,
            gh_authenticated=True,
            token_source="env",
            guidance="GitHub token found via GITHUB_TOKEN environment variable.",
        )

    # Shell out to gh CLI
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return AuthStatus(
            gh_installed=False,
            gh_authenticated=False,
            token_source=None,
            guidance=(
                "GitHub CLI (gh) is not installed.\n"
                "  Install: https://cli.github.com/\n"
                "  Then run: gh auth login"
            ),
        )
    except subprocess.TimeoutExpired:
        return AuthStatus(
            gh_installed=True,
            gh_authenticated=False,
            token_source=None,
            guidance=(
                "GitHub CLI timed out checking auth status.\n"
                "  Try running: gh auth status\n"
                "  Or set: export GITHUB_TOKEN=your_token"
            ),
        )

    if result.returncode != 0:
        return AuthStatus(
            gh_installed=True,
            gh_authenticated=False,
            token_source=None,
            guidance=(
                "GitHub CLI is installed but not authenticated.\n"
                "  Run: gh auth login\n"
                "  Or set: export GITHUB_TOKEN=your_token"
            ),
        )

    return AuthStatus(
        gh_installed=True,
        gh_authenticated=True,
        token_source="gh_cli",
        guidance="Authenticated via gh CLI.",
    )


def format_auth_guidance(status: AuthStatus) -> str:
    """Format an AuthStatus into a user-facing guidance message.

    Args:
        status: The AuthStatus from check_github_auth().

    Returns:
        Multi-line actionable string for display via click.echo().
    """
    if not status.gh_installed:
        return (
            "GitHub CLI (gh) is not installed.\n"
            "  Install: https://cli.github.com/\n"
            "  Then run: gh auth login"
        )

    if not status.gh_authenticated:
        return (
            "GitHub CLI is installed but not authenticated.\n"
            "  Run: gh auth login\n"
            "  Or set: export GITHUB_TOKEN=your_token"
        )

    return f"GitHub authentication OK ({status.token_source})."
