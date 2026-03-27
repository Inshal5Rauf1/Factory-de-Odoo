"""Tests for Python hook scripts (amil-check-update, amil-statusline, amil-context-monitor).

Each hook reads JSON from stdin and writes to stdout. Tests invoke
the scripts via subprocess to match real-world usage.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[3] / "hooks"


# ── Helpers ───────────────────────────────────────────────────────────

def _run_hook(script_name: str, stdin_data: dict | None = None,
              env_extra: dict | None = None, timeout: float = 10) -> subprocess.CompletedProcess:
    """Run a Python hook script with JSON on stdin."""
    script = _HOOKS_DIR / script_name
    env = {**os.environ, **(env_extra or {})}
    input_text = json.dumps(stdin_data) if stdin_data else ""
    return subprocess.run(
        [sys.executable, str(script)],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


# ── amil-check-update.py ─────────────────────────────────────────────


class TestCheckUpdate:
    """Tests for the SessionStart update checker hook."""

    def test_creates_cache_file(self, tmp_path: Path) -> None:
        """Hook should write a cache JSON file with version info."""
        # Create a fake VERSION file
        config_dir = tmp_path / ".claude"
        amil_dir = config_dir / "amil"
        amil_dir.mkdir(parents=True)
        (amil_dir / "VERSION").write_text("1.2.3\n")
        cache_dir = config_dir / "cache"
        cache_dir.mkdir()

        result = _run_hook(
            "amil-check-update.py",
            env_extra={
                "CLAUDE_CONFIG_DIR": str(config_dir),
                "AMIL_SKIP_NPM_CHECK": "1",  # Skip npm call in tests
            },
        )
        assert result.returncode == 0

        cache_file = cache_dir / "amil-update-check.json"
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["installed"] == "1.2.3"
        assert "checked" in data

    def test_missing_version_file(self, tmp_path: Path) -> None:
        """Hook should handle missing VERSION file gracefully."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        cache_dir = config_dir / "cache"
        cache_dir.mkdir()

        result = _run_hook(
            "amil-check-update.py",
            env_extra={
                "CLAUDE_CONFIG_DIR": str(config_dir),
                "AMIL_SKIP_NPM_CHECK": "1",
            },
        )
        assert result.returncode == 0

        cache_file = cache_dir / "amil-update-check.json"
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["installed"] == "0.0.0"


# ── amil-statusline.py ───────────────────────────────────────────────


class TestStatusline:
    """Tests for the StatusLine formatting hook."""

    def test_basic_output(self) -> None:
        """Hook should output formatted statusline text."""
        result = _run_hook("amil-statusline.py", {
            "model": {"display_name": "Claude Opus"},
            "workspace": {"current_dir": "/home/user/my-project"},
            "session_id": "test-session-001",
            "context_window": {"remaining_percentage": 80.0},
        })
        assert result.returncode == 0
        output = result.stdout
        # Should contain model name and directory basename
        assert "Claude Opus" in output
        assert "my-project" in output

    def test_context_bar_green(self) -> None:
        """Low usage should produce green context bar."""
        result = _run_hook("amil-statusline.py", {
            "model": {"display_name": "Claude"},
            "workspace": {"current_dir": "/tmp/test"},
            "context_window": {"remaining_percentage": 90.0},
        })
        assert result.returncode == 0
        # Green ANSI: \x1b[32m
        assert "\x1b[32m" in result.stdout

    def test_context_bar_critical(self) -> None:
        """High usage should produce red blinking context bar."""
        result = _run_hook("amil-statusline.py", {
            "model": {"display_name": "Claude"},
            "workspace": {"current_dir": "/tmp/test"},
            "context_window": {"remaining_percentage": 20.0},
        })
        assert result.returncode == 0
        # Red blinking ANSI: \x1b[5;31m
        assert "\x1b[5;31m" in result.stdout

    def test_writes_bridge_file(self, tmp_path: Path) -> None:
        """Hook should write bridge file for context-monitor."""
        session_id = f"test-bridge-{os.getpid()}"
        bridge_path = Path(os.environ.get("TMPDIR", "/tmp")) / f"claude-ctx-{session_id}.json"
        try:
            result = _run_hook("amil-statusline.py", {
                "model": {"display_name": "Claude"},
                "workspace": {"current_dir": "/tmp/test"},
                "session_id": session_id,
                "context_window": {"remaining_percentage": 50.0},
            })
            assert result.returncode == 0
            assert bridge_path.exists()
            data = json.loads(bridge_path.read_text())
            assert data["session_id"] == session_id
            assert "used_pct" in data
            assert "remaining_percentage" in data
        finally:
            bridge_path.unlink(missing_ok=True)

    def test_with_task_from_todos(self, tmp_path: Path) -> None:
        """Hook should show in-progress task from todos dir."""
        session_id = "test-todo-session"
        claude_dir = tmp_path / ".claude"
        todos_dir = claude_dir / "todos"
        todos_dir.mkdir(parents=True)

        todo_file = todos_dir / f"{session_id}-agent-main.json"
        todo_file.write_text(json.dumps([
            {"status": "completed", "activeForm": "Done task"},
            {"status": "in_progress", "activeForm": "Porting hooks to Python"},
        ]))

        result = _run_hook("amil-statusline.py", {
            "model": {"display_name": "Claude"},
            "workspace": {"current_dir": "/tmp/test"},
            "session_id": session_id,
            "context_window": {"remaining_percentage": 70.0},
        }, env_extra={"CLAUDE_CONFIG_DIR": str(claude_dir)})

        assert result.returncode == 0
        assert "Porting hooks to Python" in result.stdout

    def test_no_context_window(self) -> None:
        """Hook should handle missing context_window gracefully."""
        result = _run_hook("amil-statusline.py", {
            "model": {"display_name": "Claude"},
            "workspace": {"current_dir": "/tmp/test"},
        })
        assert result.returncode == 0
        assert "Claude" in result.stdout

    def test_update_notification(self, tmp_path: Path) -> None:
        """Hook should show update notification when available."""
        claude_dir = tmp_path / ".claude"
        cache_dir = claude_dir / "cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / "amil-update-check.json").write_text(json.dumps({
            "update_available": True,
            "installed": "1.0.0",
            "latest": "1.1.0",
        }))

        result = _run_hook("amil-statusline.py", {
            "model": {"display_name": "Claude"},
            "workspace": {"current_dir": "/tmp/test"},
        }, env_extra={"CLAUDE_CONFIG_DIR": str(claude_dir)})

        assert result.returncode == 0
        assert "/amil:update" in result.stdout

    def test_empty_stdin(self) -> None:
        """Hook should exit silently on empty stdin."""
        result = _run_hook("amil-statusline.py", stdin_data=None)
        assert result.returncode == 0


# ── amil-context-monitor.py ──────────────────────────────────────────


class TestContextMonitor:
    """Tests for the PostToolUse context warning hook."""

    def test_no_warning_when_healthy(self, tmp_path: Path) -> None:
        """No output when context usage is healthy."""
        session_id = f"test-healthy-{os.getpid()}"
        bridge_path = Path(os.environ.get("TMPDIR", "/tmp")) / f"claude-ctx-{session_id}.json"
        bridge_path.write_text(json.dumps({
            "session_id": session_id,
            "remaining_percentage": 60.0,
            "used_pct": 40,
            "timestamp": int(time.time()),
        }))
        try:
            result = _run_hook("amil-context-monitor.py", {
                "session_id": session_id,
            })
            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            bridge_path.unlink(missing_ok=True)

    def test_warning_when_low(self, tmp_path: Path) -> None:
        """Should emit WARNING when remaining <= 35%."""
        session_id = f"test-warn-{os.getpid()}"
        tmpdir = os.environ.get("TMPDIR", "/tmp")
        bridge_path = Path(tmpdir) / f"claude-ctx-{session_id}.json"
        warn_path = Path(tmpdir) / f"claude-ctx-{session_id}-warned.json"
        bridge_path.write_text(json.dumps({
            "session_id": session_id,
            "remaining_percentage": 33.0,
            "used_pct": 80,
            "timestamp": int(time.time()),
        }))
        try:
            result = _run_hook("amil-context-monitor.py", {
                "session_id": session_id,
            })
            assert result.returncode == 0
            output = json.loads(result.stdout)
            ctx = output["hookSpecificOutput"]["additionalContext"]
            assert "CONTEXT WARNING" in ctx
            assert "80%" in ctx
        finally:
            bridge_path.unlink(missing_ok=True)
            warn_path.unlink(missing_ok=True)

    def test_critical_when_very_low(self, tmp_path: Path) -> None:
        """Should emit CRITICAL when remaining <= 25%."""
        session_id = f"test-crit-{os.getpid()}"
        tmpdir = os.environ.get("TMPDIR", "/tmp")
        bridge_path = Path(tmpdir) / f"claude-ctx-{session_id}.json"
        warn_path = Path(tmpdir) / f"claude-ctx-{session_id}-warned.json"
        bridge_path.write_text(json.dumps({
            "session_id": session_id,
            "remaining_percentage": 20.0,
            "used_pct": 90,
            "timestamp": int(time.time()),
        }))
        try:
            result = _run_hook("amil-context-monitor.py", {
                "session_id": session_id,
            })
            assert result.returncode == 0
            output = json.loads(result.stdout)
            ctx = output["hookSpecificOutput"]["additionalContext"]
            assert "CONTEXT CRITICAL" in ctx
            assert "90%" in ctx
        finally:
            bridge_path.unlink(missing_ok=True)
            warn_path.unlink(missing_ok=True)

    def test_debounce(self, tmp_path: Path) -> None:
        """Should debounce after first warning (skip until DEBOUNCE_CALLS reached)."""
        session_id = f"test-debounce-{os.getpid()}"
        tmpdir = os.environ.get("TMPDIR", "/tmp")
        bridge_path = Path(tmpdir) / f"claude-ctx-{session_id}.json"
        warn_path = Path(tmpdir) / f"claude-ctx-{session_id}-warned.json"
        bridge_path.write_text(json.dumps({
            "session_id": session_id,
            "remaining_percentage": 33.0,
            "used_pct": 80,
            "timestamp": int(time.time()),
        }))
        try:
            # First call: should emit warning
            result1 = _run_hook("amil-context-monitor.py", {"session_id": session_id})
            assert "CONTEXT WARNING" in result1.stdout

            # Second call: should be debounced (empty output)
            result2 = _run_hook("amil-context-monitor.py", {"session_id": session_id})
            assert result2.stdout.strip() == ""
        finally:
            bridge_path.unlink(missing_ok=True)
            warn_path.unlink(missing_ok=True)

    def test_severity_escalation_bypasses_debounce(self, tmp_path: Path) -> None:
        """WARNING→CRITICAL should bypass debounce."""
        session_id = f"test-escalate-{os.getpid()}"
        tmpdir = os.environ.get("TMPDIR", "/tmp")
        bridge_path = Path(tmpdir) / f"claude-ctx-{session_id}.json"
        warn_path = Path(tmpdir) / f"claude-ctx-{session_id}-warned.json"

        # First: trigger WARNING
        bridge_path.write_text(json.dumps({
            "session_id": session_id,
            "remaining_percentage": 33.0,
            "used_pct": 80,
            "timestamp": int(time.time()),
        }))
        try:
            result1 = _run_hook("amil-context-monitor.py", {"session_id": session_id})
            assert "CONTEXT WARNING" in result1.stdout

            # Now escalate to CRITICAL (should bypass debounce)
            bridge_path.write_text(json.dumps({
                "session_id": session_id,
                "remaining_percentage": 20.0,
                "used_pct": 90,
                "timestamp": int(time.time()),
            }))
            result2 = _run_hook("amil-context-monitor.py", {"session_id": session_id})
            assert "CONTEXT CRITICAL" in result2.stdout
        finally:
            bridge_path.unlink(missing_ok=True)
            warn_path.unlink(missing_ok=True)

    def test_no_session_id(self) -> None:
        """Should exit silently without session_id."""
        result = _run_hook("amil-context-monitor.py", {})
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_no_bridge_file(self) -> None:
        """Should exit silently if bridge file doesn't exist."""
        result = _run_hook("amil-context-monitor.py", {
            "session_id": "nonexistent-session-xyz",
        })
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_stale_metrics_ignored(self, tmp_path: Path) -> None:
        """Should ignore metrics older than STALE_SECONDS."""
        session_id = f"test-stale-{os.getpid()}"
        tmpdir = os.environ.get("TMPDIR", "/tmp")
        bridge_path = Path(tmpdir) / f"claude-ctx-{session_id}.json"
        bridge_path.write_text(json.dumps({
            "session_id": session_id,
            "remaining_percentage": 20.0,
            "used_pct": 90,
            "timestamp": int(time.time()) - 120,  # 2 minutes old
        }))
        try:
            result = _run_hook("amil-context-monitor.py", {"session_id": session_id})
            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            bridge_path.unlink(missing_ok=True)

    def test_amil_active_message(self, tmp_path: Path) -> None:
        """When .planning/STATE.md exists, should include Amil-specific message."""
        session_id = f"test-amil-{os.getpid()}"
        tmpdir = os.environ.get("TMPDIR", "/tmp")
        bridge_path = Path(tmpdir) / f"claude-ctx-{session_id}.json"
        warn_path = Path(tmpdir) / f"claude-ctx-{session_id}-warned.json"

        # Create .planning/STATE.md in a temp cwd
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "STATE.md").write_text("# State\n")

        bridge_path.write_text(json.dumps({
            "session_id": session_id,
            "remaining_percentage": 33.0,
            "used_pct": 80,
            "timestamp": int(time.time()),
        }))
        try:
            result = _run_hook(
                "amil-context-monitor.py",
                {"session_id": session_id, "cwd": str(tmp_path)},
            )
            assert result.returncode == 0
            output = json.loads(result.stdout)
            ctx = output["hookSpecificOutput"]["additionalContext"]
            assert "CONTEXT WARNING" in ctx
            # Amil-specific message mentions informing user to prepare to pause
            assert "pause" in ctx.lower() or "plan steps" in ctx.lower()
        finally:
            bridge_path.unlink(missing_ok=True)
            warn_path.unlink(missing_ok=True)
