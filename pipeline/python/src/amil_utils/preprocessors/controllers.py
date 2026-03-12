"""HTTP controller / REST endpoint generation preprocessor.

FLAW-10: Generates controller metadata from spec's ``api_endpoints`` block.
Produces route definitions, auth requirements, and response format specs
that Terminal 4's controller templates consume.

Registered at order=105 (after webhook_patterns@100).

Pure function -- never mutates input spec.
"""

from __future__ import annotations

import logging
from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.renderer_utils import _to_python_var
from odoo_gen_utils.utils.copy import deep_copy_model

logger = logging.getLogger(__name__)

# Supported HTTP methods
_VALID_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})

# Supported auth types
_VALID_AUTH = frozenset({"user", "public", "none", "api_key"})


def _build_route_spec(
    endpoint: dict[str, Any],
    model: dict[str, Any],
    module_name: str,
) -> dict[str, Any]:
    """Build a single route specification from an endpoint config.

    Returns a route dict with path, methods, auth, response format, etc.
    """
    model_name = model["name"]
    model_var = _to_python_var(model_name)
    ep_name = endpoint.get("name", model_var)

    # Build route path
    base_path = endpoint.get("path", f"/api/v1/{model_var}")
    methods = endpoint.get("methods", ["GET"])
    auth = endpoint.get("auth", "user")

    # Validate
    invalid_methods = set(methods) - _VALID_METHODS
    if invalid_methods:
        logger.warning(
            "Endpoint '%s' on model '%s' has invalid methods %s — "
            "allowed: %s",
            ep_name, model_name, sorted(invalid_methods), sorted(_VALID_METHODS),
        )
        methods = [m for m in methods if m in _VALID_METHODS]

    if auth not in _VALID_AUTH:
        logger.warning(
            "Endpoint '%s' on model '%s' has invalid auth '%s' — "
            "defaulting to 'user'.",
            ep_name, model_name, auth,
        )
        auth = "user"

    route: dict[str, Any] = {
        "name": ep_name,
        "path": base_path,
        "methods": methods,
        "auth": auth,
        "model_name": model_name,
        "model_var": model_var,
        "csrf": endpoint.get("csrf", auth != "public"),
        "response_type": endpoint.get("response_type", "json"),
    }

    # Pagination config
    if "GET" in methods:
        route["pagination"] = {
            "default_limit": endpoint.get("page_size", 80),
            "max_limit": endpoint.get("max_page_size", 500),
        }

    # Field filtering (which fields to expose in API)
    expose_fields = endpoint.get("fields")
    if expose_fields:
        route["expose_fields"] = expose_fields
    else:
        # Default: expose non-internal, non-computed fields
        route["expose_fields"] = [
            f["name"] for f in model.get("fields", [])
            if not f.get("internal") and not f.get("compute")
        ]

    # Domain filter (extra domain for this endpoint)
    domain = endpoint.get("domain")
    if domain:
        route["domain"] = domain

    return route


def _build_detail_route(
    route: dict[str, Any],
) -> dict[str, Any]:
    """Build a detail route (single record) from a list route."""
    return {
        **route,
        "name": f"{route['name']}_detail",
        "path": f"{route['path']}/<int:record_id>",
        "methods": [m for m in route["methods"] if m != "POST"],
        "is_detail": True,
    }


@register_preprocessor(order=105, name="controllers")
def _process_controllers(spec: dict[str, Any]) -> dict[str, Any]:
    """Generate controller metadata from spec's ``api_endpoints``.

    For each model with an ``api_endpoints`` block:
    1. Builds route specifications (path, methods, auth, pagination)
    2. Generates detail routes for single-record access
    3. Sets ``has_controllers = True`` on model
    4. Sets ``controller_routes`` list on model
    5. Sets ``has_api_controllers = True`` on spec

    Returns a new spec dict. Pure function.
    """
    models = spec.get("models", [])
    module_name = spec.get("module_name", "module")

    has_any_controllers = False
    new_models = []

    for model in models:
        endpoints = model.get("api_endpoints")
        if not endpoints:
            new_models.append(model)
            continue

        has_any_controllers = True
        new_model = deep_copy_model(model)

        routes = []
        for endpoint in endpoints:
            route = _build_route_spec(endpoint, model, module_name)
            routes.append(route)

            # Auto-generate detail route for list endpoints
            if "GET" in route["methods"] and not endpoint.get("no_detail"):
                routes.append(_build_detail_route(route))

        new_model["has_controllers"] = True
        new_model["controller_routes"] = routes
        new_models.append(new_model)

    if not has_any_controllers:
        return spec

    return {
        **spec,
        "models": new_models,
        "has_api_controllers": True,
    }
