"""Frozen dataclasses for search index types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndexEntry:
    """A single module entry in the search index."""

    module_name: str
    display_name: str
    summary: str
    description: str
    depends: tuple[str, ...]
    category: str
    oca_repo: str
    github_url: str
    stars: int
    last_pushed: str


@dataclass(frozen=True)
class IndexStatus:
    """Status information about the local search index."""

    exists: bool
    module_count: int
    last_built: str | None
    db_path: str
    size_bytes: int
