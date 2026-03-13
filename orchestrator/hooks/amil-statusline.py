#!/usr/bin/env python3
"""Claude Code Statusline — Amil Edition.

Shows: model | current task | directory | context usage.
Port of amil-statusline.js.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        return

    data = json.loads(raw)
    model_info = data.get("model") or {}
    model = model_info.get("display_name", "Claude") if isinstance(model_info, dict) else "Claude"
    workspace = data.get("workspace") or {}
    current_dir = workspace.get("current_dir", os.getcwd()) if isinstance(workspace, dict) else os.getcwd()
    session = data.get("session_id", "")
    ctx_window = data.get("context_window") or {}
    remaining = ctx_window.get("remaining_percentage") if isinstance(ctx_window, dict) else None

    # Context window display (shows USED percentage scaled to usable context)
    # Claude Code reserves ~16.5% for autocompact buffer, so usable context
    # is 83.5% of the total window. We normalize to show 100% at that point.
    AUTO_COMPACT_BUFFER_PCT = 16.5
    ctx = ""
    if remaining is not None:
        usable_remaining = max(0, ((remaining - AUTO_COMPACT_BUFFER_PCT) / (100 - AUTO_COMPACT_BUFFER_PCT)) * 100)
        used = max(0, min(100, round(100 - usable_remaining)))

        # Write context metrics to bridge file for the context-monitor hook
        if session:
            try:
                bridge_path = Path(tempfile.gettempdir()) / f"claude-ctx-{session}.json"
                bridge_data = json.dumps({
                    "session_id": session,
                    "remaining_percentage": remaining,
                    "used_pct": used,
                    "timestamp": int(time.time()),
                })
                bridge_path.write_text(bridge_data, encoding="utf-8")
            except OSError:
                pass  # Silent fail — bridge is best-effort

        # Build progress bar (10 segments)
        filled = used // 10
        bar = "\u2588" * filled + "\u2591" * (10 - filled)

        # Color based on usable context thresholds
        if used < 50:
            ctx = f" \x1b[32m{bar} {used}%\x1b[0m"
        elif used < 65:
            ctx = f" \x1b[33m{bar} {used}%\x1b[0m"
        elif used < 80:
            ctx = f" \x1b[38;5;208m{bar} {used}%\x1b[0m"
        else:
            ctx = f" \x1b[5;31m\U0001f480 {bar} {used}%\x1b[0m"

    # Current task from todos
    task = ""
    claude_dir = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    todos_dir = Path(claude_dir) / "todos"
    if session and todos_dir.exists():
        try:
            files = []
            for f in todos_dir.iterdir():
                if f.name.startswith(session) and "-agent-" in f.name and f.name.endswith(".json"):
                    files.append((f.name, f.stat().st_mtime))
            files.sort(key=lambda x: x[1], reverse=True)

            if files:
                todos = json.loads((todos_dir / files[0][0]).read_text(encoding="utf-8"))
                in_progress = next((t for t in todos if t.get("status") == "in_progress"), None)
                if in_progress:
                    task = in_progress.get("activeForm", "")
        except (OSError, json.JSONDecodeError):
            pass

    # Amil update available?
    amil_update = ""
    cache_file = Path(claude_dir) / "cache" / "amil-update-check.json"
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            if cache.get("update_available"):
                amil_update = "\x1b[33m\u2b06 /amil:update\x1b[0m \u2502 "
        except (OSError, json.JSONDecodeError):
            pass

    # Output
    dirname = Path(current_dir).name
    if task:
        sys.stdout.write(f"{amil_update}\x1b[2m{model}\x1b[0m \u2502 \x1b[1m{task}\x1b[0m \u2502 \x1b[2m{dirname}\x1b[0m{ctx}")
    else:
        sys.stdout.write(f"{amil_update}\x1b[2m{model}\x1b[0m \u2502 \x1b[2m{dirname}\x1b[0m{ctx}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Silent fail — don't break statusline
        pass
