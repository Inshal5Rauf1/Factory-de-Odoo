"""Business logic for the search-related CLI commands.

Pure Python -- no Click dependency.  Returns structured data so callers
can decide how to display results.
"""

from __future__ import annotations

from typing import Any


def execute_build_index(
    *,
    token: str | None = None,
    db_path: str | None = None,
    update: bool = False,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    """Build or update the local ChromaDB index of OCA Odoo modules.

    Returns a result dict with keys:
        - count: int -- number of modules indexed
        - db_path: str -- resolved DB path
        - error: str | None -- error if token missing
        - needs_auth: bool -- True if authentication is needed
    """
    from amil_utils.search import build_oca_index, get_github_token
    from amil_utils.search.index import DEFAULT_DB_PATH

    result: dict[str, Any] = {
        "count": 0,
        "db_path": "",
        "error": None,
        "needs_auth": False,
    }

    if token is None:
        token = get_github_token()

    if not token:
        result["needs_auth"] = True
        result["error"] = "GitHub authentication required."
        return result

    resolved_path = db_path or str(DEFAULT_DB_PATH)
    result["db_path"] = resolved_path

    count = build_oca_index(
        token=token,
        db_path=resolved_path,
        incremental=update,
        progress_callback=progress_callback,
    )
    result["count"] = count
    return result


def execute_index_status(
    *,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Show the status of the local OCA module search index.

    Returns a result dict with keys:
        - exists: bool
        - module_count: int
        - last_built: str | None
        - db_path: str
        - size_bytes: int
        - status_object: IndexStatus -- the raw dataclass
    """
    from amil_utils.search import get_index_status

    status = get_index_status(db_path)
    return {
        "exists": status.exists,
        "module_count": status.module_count,
        "last_built": status.last_built,
        "db_path": status.db_path,
        "size_bytes": status.size_bytes,
        "status_object": status,
    }


def execute_search(
    query: str,
    *,
    db_path: str | None = None,
    limit: int = 5,
    github_fallback: bool = False,
    no_wizard: bool = False,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    """Semantically search for Odoo modules matching a natural language query.

    Returns a result dict with keys:
        - results: list -- search result objects
        - results_json: str | None -- JSON-formatted results
        - results_text: str | None -- text-formatted results
        - auto_built: bool -- True if index was auto-built
        - needs_auth: bool -- True if authentication is needed
        - error: str | None -- error message
    """
    from amil_utils.search import build_oca_index, get_github_token, get_index_status
    from amil_utils.search.index import DEFAULT_DB_PATH
    from amil_utils.search.query import (
        format_results_json,
        format_results_text,
        search_modules,
    )

    result: dict[str, Any] = {
        "results": [],
        "results_json": None,
        "results_text": None,
        "auto_built": False,
        "needs_auth": False,
        "error": None,
    }

    resolved_path = db_path or str(DEFAULT_DB_PATH)

    # Auto-build index on first use (Decision B)
    status = get_index_status(resolved_path)
    if not status.exists or status.module_count == 0:
        token = get_github_token()
        if not token:
            result["needs_auth"] = True
            result["error"] = "GitHub authentication required."
            return result

        build_oca_index(
            token=token,
            db_path=resolved_path,
            progress_callback=progress_callback,
        )
        result["auto_built"] = True

    # Run search
    try:
        results = search_modules(
            query,
            db_path=resolved_path,
            n_results=limit,
            github_fallback=github_fallback,
        )
    except ValueError as exc:
        result["error"] = f"Search error: {exc}"
        return result

    # Auto-fallback: if OCA returned 0 results and --github not set, retry with fallback
    if not results and not github_fallback:
        results = search_modules(
            query,
            db_path=resolved_path,
            n_results=limit,
            github_fallback=True,
        )

    result["results"] = results

    if results:
        result["results_json"] = format_results_json(results)
        result["results_text"] = format_results_text(results)

    return result
