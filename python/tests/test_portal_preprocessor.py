"""Tests for the portal preprocessor.

Phase 62: Verifies portal preprocessor at order=95 enriches spec with
has_portal, portal_pages, portal_auth, portal_page_models, and auto-adds
"portal" to depends.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from amil_utils.preprocessors._registry import (
    clear_registry,
    get_registered_preprocessors,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture() -> dict[str, Any]:
    """Load the portal test fixture."""
    fixture_path = FIXTURES_DIR / "portal_spec.json"
    with open(fixture_path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Portal preprocessor behavior tests
# ---------------------------------------------------------------------------


class TestPortalPreprocessor:
    """Tests for _process_portal preprocessor function."""

    def test_no_portal_key_returns_unchanged(self):
        """Preprocessor returns spec unchanged when no portal key."""
        from amil_utils.preprocessors.portal import _process_portal

        spec: dict[str, Any] = {
            "module_name": "test_module",
            "models": [],
            "depends": ["base"],
        }
        result = _process_portal(spec)
        assert result is spec  # Exact same object (no mutation)
        assert "has_portal" not in result

    def test_sets_has_portal_true(self):
        """Preprocessor sets has_portal=True when portal key exists."""
        from amil_utils.preprocessors.portal import _process_portal

        spec = _load_fixture()
        result = _process_portal(spec)
        assert result["has_portal"] is True

    def test_enriches_portal_pages(self):
        """Preprocessor creates portal_pages with enriched page metadata."""
        from amil_utils.preprocessors.portal import _process_portal

        spec = _load_fixture()
        result = _process_portal(spec)
        assert "portal_pages" in result
        assert len(result["portal_pages"]) == 4

        # Check enriched metadata on first page
        profile_page = result["portal_pages"][0]
        assert profile_page["id"] == "student_profile"
        assert "model_var" in profile_page
        assert "model_class" in profile_page

    def test_portal_auth_extracted(self):
        """Preprocessor extracts portal_auth from spec."""
        from amil_utils.preprocessors.portal import _process_portal

        spec = _load_fixture()
        result = _process_portal(spec)
        assert result["portal_auth"] == "portal"

    def test_portal_auth_default(self):
        """portal_auth defaults to 'portal' when not specified."""
        from amil_utils.preprocessors.portal import _process_portal

        spec: dict[str, Any] = {
            "module_name": "test",
            "models": [],
            "depends": ["base"],
            "portal": {
                "pages": [
                    {
                        "id": "test",
                        "type": "detail",
                        "model": "test.model",
                        "route": "/my/test",
                        "ownership": "user_id",
                    },
                ],
            },
        }
        result = _process_portal(spec)
        assert result["portal_auth"] == "portal"

    def test_auto_adds_portal_to_depends(self):
        """Preprocessor adds 'portal' to depends when not present."""
        from amil_utils.preprocessors.portal import _process_portal

        spec: dict[str, Any] = {
            "module_name": "test",
            "models": [],
            "depends": ["base"],
            "portal": {
                "pages": [
                    {
                        "id": "test",
                        "type": "detail",
                        "model": "test.model",
                        "route": "/my/test",
                        "ownership": "user_id",
                    },
                ],
            },
        }
        result = _process_portal(spec)
        assert "portal" in result["depends"]

    def test_no_duplicate_portal_depend(self):
        """Preprocessor does not duplicate 'portal' if already in depends."""
        from amil_utils.preprocessors.portal import _process_portal

        spec = _load_fixture()
        # Fixture already has "portal" in depends
        assert "portal" in spec["depends"]
        result = _process_portal(spec)
        portal_count = result["depends"].count("portal")
        assert portal_count == 1

    def test_does_not_mutate_original_depends(self):
        """Preprocessor creates a new depends list (immutability)."""
        from amil_utils.preprocessors.portal import _process_portal

        spec: dict[str, Any] = {
            "module_name": "test",
            "models": [],
            "depends": ["base"],
            "portal": {
                "pages": [
                    {
                        "id": "test",
                        "type": "detail",
                        "model": "test.model",
                        "route": "/my/test",
                        "ownership": "user_id",
                    },
                ],
            },
        }
        original_depends = spec["depends"]
        result = _process_portal(spec)
        # Original list should not be mutated
        assert "portal" not in original_depends
        assert "portal" in result["depends"]

    def test_computes_portal_page_models(self):
        """Preprocessor computes sorted unique model names from pages."""
        from amil_utils.preprocessors.portal import _process_portal

        spec = _load_fixture()
        result = _process_portal(spec)
        assert "portal_page_models" in result
        models = result["portal_page_models"]
        # Should be sorted and unique
        assert models == sorted(set(models))
        # Fixture has uni.student, uni.enrollment, fee.invoice, exam.result
        assert len(models) == 4
        assert "uni.student" in models
        assert "uni.enrollment" in models

    def test_enriched_page_has_model_var(self):
        """Enriched page has model_var derived from model name."""
        from amil_utils.preprocessors.portal import _process_portal

        spec = _load_fixture()
        result = _process_portal(spec)
        profile = result["portal_pages"][0]
        assert profile["model_var"] == "uni_student"

    def test_enriched_page_has_model_class(self):
        """Enriched page has model_class derived from model name."""
        from amil_utils.preprocessors.portal import _process_portal

        spec = _load_fixture()
        result = _process_portal(spec)
        profile = result["portal_pages"][0]
        assert profile["model_class"] == "UniStudent"

    def test_enriched_page_has_singular_plural(self):
        """Enriched page has singular_name and plural_name derived from route."""
        from amil_utils.preprocessors.portal import _process_portal

        spec = _load_fixture()
        result = _process_portal(spec)

        # /my/enrollments -> plural=enrollments, singular=enrollment
        enrollments_page = result["portal_pages"][1]
        assert enrollments_page["plural_name"] == "enrollments"
        assert enrollments_page["singular_name"] == "enrollment"

    def test_returns_new_dict_not_mutated_original(self):
        """Preprocessor returns a new dict, not the original spec."""
        from amil_utils.preprocessors.portal import _process_portal

        spec = _load_fixture()
        original = deepcopy(spec)
        result = _process_portal(spec)
        assert result is not spec
        # Original should be unchanged in structure (though extra='allow' in Pydantic may allow)
        assert "has_portal" not in original


# ---------------------------------------------------------------------------
# Registry integration tests (order=95)
# ---------------------------------------------------------------------------


class TestPortalPreprocessorRegistry:
    """Tests that portal preprocessor is registered at order=95."""

    @pytest.fixture(autouse=True)
    def _reload_registry(self):
        """Reload preprocessor modules to ensure portal is registered."""
        import importlib
        import sys

        clear_registry()

        submodule_names = [
            name for name in sorted(sys.modules)
            if name.startswith("amil_utils.preprocessors.")
            and not name.endswith("._registry")
        ]
        for name in submodule_names:
            importlib.reload(sys.modules[name])
        yield
        clear_registry()

    def test_portal_preprocessor_registered(self):
        """Portal preprocessor is in the registry."""
        entries = get_registered_preprocessors()
        names = [e[1] for e in entries]
        assert "portal" in names

    def test_portal_preprocessor_at_order_95(self):
        """Portal preprocessor runs at order=95."""
        entries = get_registered_preprocessors()
        portal_entry = next(e for e in entries if e[1] == "portal")
        assert portal_entry[0] == 95

    def test_portal_after_notifications_before_webhooks(self):
        """Portal (95) runs after notifications (90) and before webhooks (100)."""
        entries = get_registered_preprocessors()
        orders_by_name = {e[1]: e[0] for e in entries}
        assert orders_by_name.get("portal", 0) > orders_by_name.get("notification_patterns", 0)
        assert orders_by_name.get("portal", 0) < orders_by_name.get("webhook_patterns", 0)
