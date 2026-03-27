"""Tests for the controllers preprocessor."""

from __future__ import annotations

from typing import Any

import pytest

from amil_utils.preprocessors.controllers import _process_controllers


def _make_spec(
    models: list[dict[str, Any]] | None = None,
    module_name: str = "test_mod",
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal spec dict."""
    return {"module_name": module_name, "models": models or [], **kwargs}


def _make_model(
    name: str = "test.item",
    fields: list[dict[str, Any]] | None = None,
    api_endpoints: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal model dict."""
    model: dict[str, Any] = {
        "name": name,
        "fields": fields or [
            {"name": "name", "type": "Char"},
            {"name": "value", "type": "Integer"},
        ],
        **kwargs,
    }
    if api_endpoints is not None:
        model["api_endpoints"] = api_endpoints
    return model


class TestProcessControllers:
    """Tests for _process_controllers."""

    def test_happy_path_basic_endpoint(self):
        """Model with api_endpoints gets controller_routes and flags."""
        model = _make_model(
            api_endpoints=[{"name": "items", "methods": ["GET", "POST"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        assert result is not spec
        assert result["has_api_controllers"] is True
        rm = result["models"][0]
        assert rm["has_controllers"] is True
        assert len(rm["controller_routes"]) >= 1

    def test_route_path_default(self):
        """Default route path is /api/v1/{model_var}."""
        model = _make_model(
            name="inventory.item",
            api_endpoints=[{"methods": ["GET"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        routes = result["models"][0]["controller_routes"]
        list_route = routes[0]
        assert list_route["path"] == "/api/v1/inventory_item"

    def test_route_path_custom(self):
        """Custom path is used when specified."""
        model = _make_model(
            api_endpoints=[{"path": "/api/v2/custom", "methods": ["GET"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert route["path"] == "/api/v2/custom"

    def test_detail_route_auto_generated(self):
        """GET endpoints auto-generate a detail route."""
        model = _make_model(
            api_endpoints=[{"name": "items", "methods": ["GET", "POST"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        routes = result["models"][0]["controller_routes"]
        detail_routes = [r for r in routes if r.get("is_detail")]
        assert len(detail_routes) == 1
        detail = detail_routes[0]
        assert detail["name"] == "items_detail"
        assert detail["path"].endswith("/<int:record_id>")
        # POST should not be in detail route methods
        assert "POST" not in detail["methods"]
        assert "GET" in detail["methods"]

    def test_no_detail_route_flag(self):
        """no_detail:true suppresses detail route generation."""
        model = _make_model(
            api_endpoints=[{
                "name": "items",
                "methods": ["GET"],
                "no_detail": True,
            }],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        routes = result["models"][0]["controller_routes"]
        assert len(routes) == 1
        assert "is_detail" not in routes[0]

    def test_auth_default_user(self):
        """Default auth is 'user'."""
        model = _make_model(
            api_endpoints=[{"methods": ["GET"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert route["auth"] == "user"

    def test_auth_public(self):
        """Auth can be set to 'public'."""
        model = _make_model(
            api_endpoints=[{"methods": ["GET"], "auth": "public"}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert route["auth"] == "public"

    def test_invalid_auth_defaults_to_user(self):
        """Invalid auth value defaults to 'user'."""
        model = _make_model(
            api_endpoints=[{"methods": ["GET"], "auth": "invalid_auth"}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert route["auth"] == "user"

    def test_invalid_methods_filtered(self):
        """Invalid HTTP methods are filtered out."""
        model = _make_model(
            api_endpoints=[{"methods": ["GET", "INVALID", "POST"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert "GET" in route["methods"]
        assert "POST" in route["methods"]
        assert "INVALID" not in route["methods"]

    def test_csrf_default_based_on_auth(self):
        """CSRF defaults to True for non-public auth, True when auth != public."""
        model_user = _make_model(
            name="test.a",
            api_endpoints=[{"methods": ["GET"], "auth": "user"}],
        )
        model_public = _make_model(
            name="test.b",
            api_endpoints=[{"methods": ["GET"], "auth": "public"}],
        )
        spec = _make_spec(models=[model_user, model_public])

        result = _process_controllers(spec)

        route_user = result["models"][0]["controller_routes"][0]
        route_public = result["models"][1]["controller_routes"][0]
        assert route_user["csrf"] is True
        assert route_public["csrf"] is False

    def test_pagination_for_get(self):
        """GET endpoints include pagination config."""
        model = _make_model(
            api_endpoints=[{"methods": ["GET"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert "pagination" in route
        assert route["pagination"]["default_limit"] == 80
        assert route["pagination"]["max_limit"] == 500

    def test_pagination_custom_values(self):
        """Custom page_size and max_page_size are respected."""
        model = _make_model(
            api_endpoints=[{
                "methods": ["GET"],
                "page_size": 25,
                "max_page_size": 200,
            }],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert route["pagination"]["default_limit"] == 25
        assert route["pagination"]["max_limit"] == 200

    def test_no_pagination_without_get(self):
        """POST-only endpoints do not get pagination."""
        model = _make_model(
            api_endpoints=[{"methods": ["POST"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert "pagination" not in route

    def test_expose_fields_explicit(self):
        """Explicit fields list is used for expose_fields."""
        model = _make_model(
            api_endpoints=[{
                "methods": ["GET"],
                "fields": ["name", "value"],
            }],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert route["expose_fields"] == ["name", "value"]

    def test_expose_fields_auto_default(self):
        """Without explicit fields, non-internal non-computed fields are exposed."""
        fields = [
            {"name": "name", "type": "Char"},
            {"name": "internal_code", "type": "Char", "internal": True},
            {"name": "total", "type": "Float", "compute": "_compute_total"},
            {"name": "amount", "type": "Float"},
        ]
        model = _make_model(
            fields=fields,
            api_endpoints=[{"methods": ["GET"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert "name" in route["expose_fields"]
        assert "amount" in route["expose_fields"]
        assert "internal_code" not in route["expose_fields"]
        assert "total" not in route["expose_fields"]

    def test_domain_filter(self):
        """Endpoint domain filter is passed through."""
        model = _make_model(
            api_endpoints=[{
                "methods": ["GET"],
                "domain": "[('active', '=', True)]",
            }],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert route["domain"] == "[('active', '=', True)]"

    def test_response_type_default_json(self):
        """Default response_type is 'json'."""
        model = _make_model(
            api_endpoints=[{"methods": ["GET"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert route["response_type"] == "json"

    def test_response_type_custom(self):
        """Custom response_type is respected."""
        model = _make_model(
            api_endpoints=[{"methods": ["GET"], "response_type": "http"}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert route["response_type"] == "http"

    def test_multiple_endpoints(self):
        """Multiple endpoints on one model generate multiple routes."""
        model = _make_model(
            api_endpoints=[
                {"name": "list_items", "methods": ["GET"]},
                {"name": "create_item", "methods": ["POST"], "path": "/api/v1/items/new"},
            ],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        routes = result["models"][0]["controller_routes"]
        # list_items + detail + create_item = 3
        assert len(routes) == 3
        names = [r["name"] for r in routes]
        assert "list_items" in names
        assert "list_items_detail" in names
        assert "create_item" in names

    # --- Edge cases ---

    def test_empty_spec_no_models(self):
        """Empty models list returns spec unchanged."""
        spec = _make_spec(models=[])

        result = _process_controllers(spec)

        assert result is spec

    def test_model_without_endpoints(self):
        """Model without api_endpoints passes through unchanged."""
        model = _make_model()
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        assert result is spec

    def test_mixed_models(self):
        """Only models with api_endpoints get controller metadata."""
        m1 = _make_model(name="test.a")
        m2 = _make_model(
            name="test.b",
            api_endpoints=[{"methods": ["GET"]}],
        )
        spec = _make_spec(models=[m1, m2])

        result = _process_controllers(spec)

        assert "has_controllers" not in result["models"][0]
        assert result["models"][1]["has_controllers"] is True

    def test_immutability_input_not_mutated(self):
        """Input spec and model dicts are not mutated."""
        model = _make_model(
            api_endpoints=[{"methods": ["GET"]}],
        )
        spec = _make_spec(models=[model])
        original_keys = set(model.keys())

        _process_controllers(spec)

        assert set(model.keys()) == original_keys
        assert "has_controllers" not in model
        assert "controller_routes" not in model

    def test_model_var_derived_from_name(self):
        """model_var is the model name with dots replaced by underscores."""
        model = _make_model(
            name="inventory.stock.item",
            api_endpoints=[{"methods": ["GET"]}],
        )
        spec = _make_spec(models=[model])

        result = _process_controllers(spec)

        route = result["models"][0]["controller_routes"][0]
        assert route["model_var"] == "inventory_stock_item"
        assert route["model_name"] == "inventory.stock.item"
