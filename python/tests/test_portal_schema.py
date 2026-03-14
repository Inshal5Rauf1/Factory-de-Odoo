"""Tests for portal-related Pydantic schema models.

Phase 62: PortalActionSpec, PortalFilterSpec, PortalPageSpec, PortalSpec
validation tests, plus ModuleSpec.portal field integration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from amil_utils.spec_schema import (
    ModuleSpec,
    PortalActionSpec,
    PortalFilterSpec,
    PortalPageSpec,
    PortalSpec,
    validate_spec,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# PortalActionSpec tests
# ---------------------------------------------------------------------------


class TestPortalActionSpec:
    """Tests for PortalActionSpec Pydantic model."""

    def test_valid_action(self):
        """A valid portal action with all fields passes validation."""
        action = PortalActionSpec(
            name="download_challan",
            label="Download Challan",
            type="report",
            report_ref="uni_fee.report_fee_challan",
            states=["confirmed", "overdue"],
        )
        assert action.name == "download_challan"
        assert action.label == "Download Challan"
        assert action.type == "report"
        assert action.report_ref == "uni_fee.report_fee_challan"
        assert action.states == ["confirmed", "overdue"]

    def test_action_defaults(self):
        """Action with just name uses sensible defaults."""
        action = PortalActionSpec(name="do_something")
        assert action.label == ""
        assert action.type == "report"
        assert action.report_ref == ""
        assert action.states == []

    def test_action_extra_fields_allowed(self):
        """Extra fields are allowed due to ConfigDict(extra='allow')."""
        action = PortalActionSpec(name="test", custom_key="custom_value")
        assert action.custom_key == "custom_value"


# ---------------------------------------------------------------------------
# PortalFilterSpec tests
# ---------------------------------------------------------------------------


class TestPortalFilterSpec:
    """Tests for PortalFilterSpec Pydantic model."""

    def test_valid_filter(self):
        """A valid filter with field and label."""
        filt = PortalFilterSpec(field="term_id", label="Term")
        assert filt.field == "term_id"
        assert filt.label == "Term"

    def test_filter_default_label(self):
        """Filter defaults label to empty string."""
        filt = PortalFilterSpec(field="state")
        assert filt.label == ""


# ---------------------------------------------------------------------------
# PortalPageSpec tests
# ---------------------------------------------------------------------------


class TestPortalPageSpec:
    """Tests for PortalPageSpec Pydantic model."""

    def test_valid_detail_page(self):
        """A valid detail page passes validation."""
        page = PortalPageSpec(
            id="student_profile",
            type="detail",
            model="uni.student",
            route="/my/profile",
            title="My Profile",
            ownership="user_id",
        )
        assert page.id == "student_profile"
        assert page.type == "detail"
        assert page.model == "uni.student"
        assert page.ownership == "user_id"

    def test_valid_list_page(self):
        """A valid list page with optional fields passes validation."""
        page = PortalPageSpec(
            id="student_enrollments",
            type="list",
            model="uni.enrollment",
            route="/my/enrollments",
            title="My Enrollments",
            ownership="student_id.user_id",
            list_fields=["course_id", "term_id", "state"],
            detail_route="/my/enrollment/<int:enrollment_id>",
            detail_fields=["course_id", "term_id", "section"],
            filters=[PortalFilterSpec(field="term_id", label="Term")],
            default_sort="term_id desc",
        )
        assert page.type == "list"
        assert page.ownership == "student_id.user_id"
        assert len(page.list_fields) == 3
        assert len(page.filters) == 1
        assert page.default_sort == "term_id desc"

    def test_invalid_page_type_raises(self):
        """Page type not in {detail, list} raises ValidationError."""
        with pytest.raises(ValidationError, match="type"):
            PortalPageSpec(
                id="test",
                type="form",
                model="test.model",
                route="/my/test",
                ownership="user_id",
            )

    def test_missing_ownership_raises(self):
        """Missing ownership field raises ValidationError."""
        with pytest.raises(ValidationError, match="ownership"):
            PortalPageSpec(
                id="test",
                type="detail",
                model="test.model",
                route="/my/test",
            )

    def test_page_defaults(self):
        """Page uses sensible defaults for optional fields."""
        page = PortalPageSpec(
            id="test",
            type="detail",
            model="test.model",
            route="/my/test",
            ownership="user_id",
        )
        assert page.title == ""
        assert page.fields_visible == []
        assert page.fields_editable == []
        assert page.list_fields == []
        assert page.detail_route is None
        assert page.detail_fields == []
        assert page.detail_actions == []
        assert page.filters == []
        assert page.default_sort == "id desc"
        assert page.show_in_home is True
        assert page.home_icon == "fa fa-file"
        assert page.home_counter is False
        assert page.counter_domain is None

    def test_page_with_detail_actions(self):
        """Page with detail_actions list of PortalActionSpec objects."""
        page = PortalPageSpec(
            id="fees",
            type="list",
            model="fee.invoice",
            route="/my/fees",
            ownership="student_id.user_id",
            detail_actions=[
                PortalActionSpec(
                    name="download_challan",
                    label="Download Challan",
                    type="report",
                    report_ref="uni_fee.report_fee_challan",
                    states=["confirmed", "overdue"],
                ),
            ],
        )
        assert len(page.detail_actions) == 1
        assert page.detail_actions[0].name == "download_challan"


# ---------------------------------------------------------------------------
# PortalSpec tests
# ---------------------------------------------------------------------------


class TestPortalSpec:
    """Tests for PortalSpec Pydantic model."""

    def test_valid_portal_spec(self):
        """A valid portal spec with pages, auth, and menu_label."""
        pages = [
            PortalPageSpec(
                id="profile",
                type="detail",
                model="uni.student",
                route="/my/profile",
                ownership="user_id",
            ),
        ]
        portal = PortalSpec(pages=pages, auth="portal", menu_label="Student Portal")
        assert len(portal.pages) == 1
        assert portal.auth == "portal"
        assert portal.menu_label == "Student Portal"

    def test_portal_defaults(self):
        """Portal spec defaults auth to 'portal' and menu_label to 'Portal'."""
        pages = [
            PortalPageSpec(
                id="test",
                type="detail",
                model="test.model",
                route="/my/test",
                ownership="user_id",
            ),
        ]
        portal = PortalSpec(pages=pages)
        assert portal.auth == "portal"
        assert portal.menu_label == "Portal"

    def test_portal_empty_pages_allowed(self):
        """Portal spec with empty pages list is valid (schema-level)."""
        portal = PortalSpec(pages=[])
        assert portal.pages == []


# ---------------------------------------------------------------------------
# ModuleSpec.portal integration tests
# ---------------------------------------------------------------------------


class TestModuleSpecPortal:
    """Tests for ModuleSpec.portal field integration."""

    def test_portal_field_accepts_none(self):
        """ModuleSpec.portal defaults to None when not provided."""
        spec = ModuleSpec(module_name="test_module")
        assert spec.portal is None

    def test_portal_field_accepts_portal_spec(self):
        """ModuleSpec.portal accepts a PortalSpec object."""
        portal = PortalSpec(
            pages=[
                PortalPageSpec(
                    id="test",
                    type="detail",
                    model="test.model",
                    route="/my/test",
                    ownership="user_id",
                ),
            ],
        )
        spec = ModuleSpec(module_name="test_module", portal=portal)
        assert spec.portal is not None
        assert len(spec.portal.pages) == 1

    def test_portal_from_dict(self):
        """ModuleSpec.portal can be constructed from a raw dict."""
        raw = {
            "module_name": "test_module",
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
        spec = ModuleSpec(**raw)
        assert spec.portal is not None
        assert spec.portal.pages[0].id == "test"

    def test_validate_spec_with_portal_fixture(self):
        """validate_spec() accepts the portal test fixture."""
        fixture_path = FIXTURES_DIR / "portal_spec.json"
        with open(fixture_path) as f:
            raw = json.load(f)
        spec = validate_spec(raw)
        assert spec.portal is not None
        assert len(spec.portal.pages) == 4
        assert spec.portal.auth == "portal"
        assert spec.portal.menu_label == "Student Portal"

    def test_fixture_page_types_correct(self):
        """Fixture pages have correct types: 1 detail, 3 list."""
        fixture_path = FIXTURES_DIR / "portal_spec.json"
        with open(fixture_path) as f:
            raw = json.load(f)
        spec = validate_spec(raw)
        types = [p.type for p in spec.portal.pages]
        assert types.count("detail") == 1
        assert types.count("list") == 3

    def test_fixture_detail_actions(self):
        """Fixture fees page has download_challan action."""
        fixture_path = FIXTURES_DIR / "portal_spec.json"
        with open(fixture_path) as f:
            raw = json.load(f)
        spec = validate_spec(raw)
        fees_page = next(p for p in spec.portal.pages if p.id == "student_fees")
        assert len(fees_page.detail_actions) == 1
        assert fees_page.detail_actions[0].name == "download_challan"
