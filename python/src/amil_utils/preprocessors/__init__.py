"""Preprocessor package with auto-discovery."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any

from amil_utils.preprocessors._registry import (
    get_registered_preprocessors,
    register_preprocessor,
)

# Auto-discover all submodules (triggers @register_preprocessor decorators)
_pkg_path = str(Path(__file__).parent)
for _finder, _name, _ispkg in pkgutil.iter_modules([_pkg_path]):
    if not _name.startswith("_"):
        importlib.import_module(f"{__name__}.{_name}")


def _rediscover() -> None:
    """Re-import submodules to re-register preprocessors after a registry clear."""
    import sys

    for _finder2, _name2, _ispkg2 in pkgutil.iter_modules([_pkg_path]):
        if not _name2.startswith("_"):
            fqn = f"{__name__}.{_name2}"
            if fqn in sys.modules:
                importlib.reload(sys.modules[fqn])
            else:
                importlib.import_module(fqn)


def run_preprocessors(spec: dict[str, Any] | Any) -> dict[str, Any]:
    """Execute all registered preprocessors in order.

    Each preprocessor receives the spec dict and returns a new spec dict.
    This is the primary public API for the preprocessor pipeline.

    PIPE-01: Accepts either a raw dict or a Pydantic ModuleSpec object.
    If a ModuleSpec is passed, it is converted to dict once at this boundary.

    If the registry is empty (e.g. after clear_registry() in tests),
    submodules are re-imported to restore all registrations.
    """
    # PIPE-01: Convert ModuleSpec → dict at the preprocessor boundary
    if hasattr(spec, "model_dump"):
        spec = spec.model_dump(exclude_none=True)
    if not get_registered_preprocessors():
        _rediscover()
    for _order, _name, fn in get_registered_preprocessors():
        spec = fn(spec)
    return spec

