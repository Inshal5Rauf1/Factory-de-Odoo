#!/usr/bin/env python3
"""Check for Amil updates — write result to cache.

Called by SessionStart hook — runs once per session.
Port of amil-check-update.js.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
CWD = Path.cwd()


def detect_config_dir(base_dir: Path) -> Path:
    """Detect runtime config directory (supports Claude, OpenCode, Gemini)."""
    env_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if env_dir and (Path(env_dir) / "amil" / "VERSION").exists():
        return Path(env_dir)
    for dirname in (".config/opencode", ".opencode", ".gemini", ".claude"):
        candidate = base_dir / dirname
        if (candidate / "amil" / "VERSION").exists():
            return candidate
    return Path(env_dir) if env_dir else base_dir / ".claude"


def main() -> None:
    global_config_dir = detect_config_dir(HOME)
    project_config_dir = detect_config_dir(CWD)
    cache_dir = global_config_dir / "cache"
    cache_file = cache_dir / "amil-update-check.json"

    project_version_file = project_config_dir / "amil" / "VERSION"
    global_version_file = global_config_dir / "amil" / "VERSION"

    cache_dir.mkdir(parents=True, exist_ok=True)

    # Read installed version
    installed = "0.0.0"
    for vf in (project_version_file, global_version_file):
        if vf.exists():
            installed = vf.read_text(encoding="utf-8").strip()
            break

    # Check latest from npm (unless skipped for testing)
    latest: str | None = None
    if not os.environ.get("AMIL_SKIP_NPM_CHECK"):
        try:
            latest = subprocess.run(
                ["npm", "view", "amil-cc", "version"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip() or None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    result = {
        "update_available": bool(latest and installed != latest),
        "installed": installed,
        "latest": latest or "unknown",
        "checked": int(time.time()),
    }

    cache_file.write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Silent fail — never break session start
        sys.exit(0)
