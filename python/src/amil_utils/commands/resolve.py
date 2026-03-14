"""Business logic for the ``resolve`` CLI command group.

Pure Python -- no Click dependency.  Returns structured data so callers
can decide how to display results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def execute_resolve_status(module_dir: str) -> dict[str, Any]:
    """Show pending conflict files.

    Returns a result dict with keys:
        - pending: list[str] -- relative paths of pending files
        - count: int -- number of pending files
    """
    from amil_utils.iterative.resolve import resolve_status

    pending = resolve_status(Path(module_dir))
    return {
        "pending": pending,
        "count": len(pending),
    }


def execute_resolve_accept_all(module_dir: str) -> dict[str, Any]:
    """Accept all pending conflict files (overwrite current with new).

    Returns a result dict with keys:
        - count: int -- number of files resolved
    """
    from amil_utils.iterative.resolve import resolve_accept_all

    count = resolve_accept_all(Path(module_dir))
    return {"count": count}


def execute_resolve_accept_new(module_dir: str, file_path: str) -> dict[str, Any]:
    """Accept the new version of a specific pending file.

    Returns a result dict with keys:
        - accepted: bool -- True if the file was found and accepted
        - file_path: str -- the file that was accepted
    """
    from amil_utils.iterative.resolve import resolve_accept_new

    accepted = resolve_accept_new(Path(module_dir), file_path)
    return {
        "accepted": accepted,
        "file_path": file_path,
    }


def execute_resolve_keep_mine(module_dir: str, file_path: str) -> dict[str, Any]:
    """Keep the current version of a specific file, discard pending.

    Returns a result dict with keys:
        - kept: bool -- True if the file was found and kept
        - file_path: str -- the file that was kept
    """
    from amil_utils.iterative.resolve import resolve_keep_mine

    kept = resolve_keep_mine(Path(module_dir), file_path)
    return {
        "kept": kept,
        "file_path": file_path,
    }
