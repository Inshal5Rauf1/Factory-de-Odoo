"""Semantic search query module for OCA/GitHub Odoo module search.

Encodes user queries, searches ChromaDB for similar modules, formats
ranked results, and falls back to GitHub `gh search repos` when OCA
results are empty and github_fallback is enabled.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from dataclasses import dataclass

try:
    import chromadb
except ImportError:  # pragma: no cover
    chromadb = None  # type: ignore[assignment]

from odoo_gen_utils.search.index import DEFAULT_DB_PATH


@dataclass(frozen=True)
class SearchResult:
    """A single search result from semantic module search."""

    module_id: str
    module_name: str
    repo_name: str
    org: str
    summary: str
    category: str
    depends: tuple[str, ...]
    url: str
    relevance_score: float
    document_text: str


def _cosine_distance_to_similarity(distance: float) -> float:
    """Convert ChromaDB cosine distance to 0.0-1.0 similarity score.

    ChromaDB cosine distance ranges from 0.0 (identical) to 2.0 (opposite).
    This converts to a similarity score: 1.0 (identical) to 0.0 (opposite).

    Args:
        distance: Cosine distance from ChromaDB (0.0 to 2.0).

    Returns:
        Similarity score (0.0 to 1.0).
    """
    return 1.0 - (distance / 2.0)


def _parse_depends(depends_str: str) -> tuple[str, ...]:
    """Parse a comma-separated depends string into a tuple.

    Args:
        depends_str: Comma-separated string of module names.

    Returns:
        Tuple of stripped module name strings.
    """
    if not depends_str:
        return ()
    return tuple(d.strip() for d in depends_str.split(",") if d.strip())


def _build_search_result(
    entry_id: str,
    metadata: dict,
    document: str,
    distance: float,
) -> SearchResult:
    """Build a SearchResult from ChromaDB query result components.

    Args:
        entry_id: ChromaDB document ID (e.g., "oca/sale-workflow/sale_order_type").
        metadata: Metadata dict from ChromaDB.
        document: Document text from ChromaDB.
        distance: Cosine distance from ChromaDB.

    Returns:
        Populated SearchResult instance.
    """
    return SearchResult(
        module_id=entry_id,
        module_name=metadata.get("module_name", ""),
        repo_name=metadata.get("oca_repo", ""),
        org=metadata.get("org", "OCA"),
        summary=metadata.get("summary", ""),
        category=metadata.get("category", ""),
        depends=_parse_depends(metadata.get("depends", "")),
        url=metadata.get("url", ""),
        relevance_score=_cosine_distance_to_similarity(distance),
        document_text=document,
    )


def _github_search_fallback(query: str, n_results: int) -> tuple[SearchResult, ...]:
    """Search GitHub repos via `gh search repos` as fallback.

    Called when OCA results are empty and github_fallback is enabled.

    Args:
        query: Search query string.
        n_results: Maximum number of results to return.

    Returns:
        Tuple of SearchResult objects with org="GitHub".
    """
    try:
        result = subprocess.run(
            ["gh", "search", "repos", query, "--json", "name,description,url,stargazerCount"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return ()

        repos = json.loads(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return ()

    results = []
    for repo in repos[:n_results]:
        name = repo.get("name", "")
        description = repo.get("description", "") or ""
        url = repo.get("url", "")

        sr = SearchResult(
            module_id=f"github/{name}",
            module_name=name,
            repo_name=name,
            org="GitHub",
            summary=description,
            category="",
            depends=(),
            url=url,
            relevance_score=0.5,
            document_text=description,
        )
        results.append(sr)

    return tuple(results)


def search_modules(
    query: str,
    db_path: str | None = None,
    n_results: int = 5,
    github_fallback: bool = False,
) -> tuple[SearchResult, ...]:
    """Search for Odoo modules matching a natural language query.

    Queries the local ChromaDB index for semantically similar modules.
    Results are sorted by relevance_score (highest first).

    Args:
        query: Natural language search query.
        db_path: Path to ChromaDB storage directory. Defaults to DEFAULT_DB_PATH.
        n_results: Maximum number of results (default: 5 per Decision A).
        github_fallback: If True, falls back to ``gh search repos`` when
            OCA results are empty (SRCH-01).

    Returns:
        Tuple of SearchResult objects sorted by relevance_score descending.

    Raises:
        ValueError: If query is empty or whitespace-only.
        ValueError: If the ChromaDB collection does not exist.
    """
    if not query or not query.strip():
        msg = "Query must not be empty"
        raise ValueError(msg)

    resolved_path = db_path or str(DEFAULT_DB_PATH)

    client = chromadb.PersistentClient(path=resolved_path)

    # get_collection raises ValueError if collection doesn't exist
    collection = client.get_collection(name="odoo_modules")

    query_result = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    ids = query_result["ids"][0] if query_result["ids"] else []
    documents = query_result["documents"][0] if query_result["documents"] else []
    metadatas = query_result["metadatas"][0] if query_result["metadatas"] else []
    distances = query_result["distances"][0] if query_result["distances"] else []

    # Build search results from ChromaDB response
    results = []
    for entry_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        sr = _build_search_result(entry_id, metadata, document, distance)
        results.append(sr)

    # If no OCA results and GitHub fallback enabled, try gh search repos
    if not results and github_fallback:
        return _github_search_fallback(query, n_results)

    # Sort by relevance_score descending
    results.sort(key=lambda r: r.relevance_score, reverse=True)

    return tuple(results)


def format_results_text(results: tuple[SearchResult, ...]) -> str:
    """Format search results as human-readable text.

    Each result shows: rank, score percentage, module name, org/repo badge,
    summary, and URL.

    Args:
        results: Tuple of SearchResult objects.

    Returns:
        Formatted text string.
    """
    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, 1):
        score_pct = f"{r.relevance_score * 100:.0f}%"
        badge = "OCA" if r.org == "OCA" else "GitHub"
        lines.append(f"{i}. [{score_pct}] {r.module_name} ({r.org}/{r.repo_name}) [{badge}]")
        lines.append(f"   {r.summary}")
        lines.append(f"   {r.url}")
        lines.append("")

    return "\n".join(lines)


def format_results_json(results: tuple[SearchResult, ...]) -> str:
    """Format search results as a JSON array.

    Converts each SearchResult to a dict with all fields. Tuple fields
    (depends) are converted to lists for JSON compatibility.

    Args:
        results: Tuple of SearchResult objects.

    Returns:
        JSON string of the results array.
    """
    result_dicts = []
    for r in results:
        d = dataclasses.asdict(r)
        # Convert tuple to list for JSON serialization
        d["depends"] = list(r.depends)
        result_dicts.append(d)

    return json.dumps(result_dicts, indent=2)
