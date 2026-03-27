"""Enterprise edition detection and Community alternative lookup.

Provides functions to check whether Odoo module dependencies are
Enterprise-only and to suggest OCA Community alternatives when available.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_REGISTRY_PATH = Path(__file__).parent / "data" / "enterprise_modules.json"

# Module-level cache to avoid repeated file I/O
_registry_cache: dict[str, Any] | None = None
_registry_cache_path: Path | None = None


def load_enterprise_registry(
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Load the enterprise module registry from JSON.

    Args:
        registry_path: Path to the registry JSON file.
            Defaults to data/enterprise_modules.json bundled with this package.

    Returns:
        Dictionary with "enterprise_modules" key mapping technical names
        to module metadata including community alternatives.

    Raises:
        FileNotFoundError: If registry file does not exist.
        json.JSONDecodeError: If registry file contains invalid JSON.
    """
    global _registry_cache, _registry_cache_path  # noqa: PLW0603

    resolved = registry_path or _DEFAULT_REGISTRY_PATH

    if _registry_cache is not None and _registry_cache_path == resolved:
        return _registry_cache

    content = resolved.read_text(encoding="utf-8")
    registry = json.loads(content)
    _registry_cache = registry
    _registry_cache_path = resolved
    return registry


def check_enterprise_dependencies(
    depends: list[str],
    registry_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Check a dependency list against the Enterprise module registry.

    For each dependency that is Enterprise-only, returns a warning dict
    with the module name, display name, category, and OCA alternative
    information (if one exists).

    Args:
        depends: List of Odoo module technical names to check.
        registry_path: Path to the registry JSON file.
            Defaults to the bundled data/enterprise_modules.json.

    Returns:
        List of warning dicts. Each dict has keys:
        - module: technical name of the Enterprise dependency
        - display_name: human-readable name
        - category: module category
        - alternative: OCA module name or None
        - alternative_repo: OCA repository path or None
        - notes: additional context about the alternative or empty string

        Empty list means all dependencies are Community-safe.
    """
    registry = load_enterprise_registry(registry_path)
    enterprise_modules = registry.get("enterprise_modules", {})

    warnings: list[dict[str, Any]] = []
    for dep in depends:
        if dep in enterprise_modules:
            entry = enterprise_modules[dep]
            alt = entry.get("community_alternative") or {}
            warnings.append({
                "module": dep,
                "display_name": entry.get("display_name", dep),
                "category": entry.get("category", ""),
                "alternative": alt.get("oca_module") if alt else None,
                "alternative_repo": alt.get("oca_repo") if alt else None,
                "notes": alt.get("notes", "") if alt else "",
            })
    return warnings
