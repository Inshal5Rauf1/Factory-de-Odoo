"""Decorator-based preprocessor registry with explicit ordering."""

from __future__ import annotations

from typing import Any, Callable

PreprocessorFn = Callable[[dict[str, Any]], dict[str, Any]]

_REGISTRY: list[tuple[int, str, PreprocessorFn]] = []


def register_preprocessor(*, order: int, name: str | None = None):
    """Register a spec-transforming preprocessor with explicit execution order.

    Decorated function MUST accept a spec dict and return a new spec dict.
    Use multiples of 10 for order to allow future insertion.

    Args:
        order: Execution priority (lower runs first).
        name: Human-readable name (defaults to function.__name__).
    """

    def decorator(fn: PreprocessorFn) -> PreprocessorFn:
        _REGISTRY.append((order, name or fn.__name__, fn))
        return fn

    return decorator


def get_registered_preprocessors() -> list[tuple[int, str, PreprocessorFn]]:
    """Return all registered preprocessors sorted by execution order."""
    return sorted(_REGISTRY, key=lambda entry: entry[0])


def clear_registry() -> None:
    """Clear registry. Only for testing."""
    _REGISTRY.clear()
