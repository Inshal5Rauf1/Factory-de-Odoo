"""Tests for E23 portal ownership path validation.

Phase 62: Validates that portal page ownership paths terminate at res.users.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from amil_utils.validation.semantic import (
    ValidationIssue,
    _check_e23,
    semantic_validate,
)


# ---------------------------------------------------------------------------
# Helper: build spec dicts for targeted testing
# ---------------------------------------------------------------------------


def _make_spec(
    pages: list[dict[str, Any]],
    models: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a minimal spec dict with portal section and models."""
    return {
        "module_name": "test_module",
        "depends": ["base", "portal"],
        "models": models or [],
        "portal": {
            "pages": pages,
            "auth": "portal",
        },
    }


def _make_model(
    name: str, fields: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build a minimal model dict."""
    return {
        "name": name,
        "description": name,
        "fields": fields,
    }


def _make_field(
    name: str,
    field_type: str = "Char",
    comodel_name: str | None = None,
) -> dict[str, Any]:
    """Build a minimal field dict."""
    field: dict[str, Any] = {"name": name, "type": field_type}
    if comodel_name is not None:
        field["comodel_name"] = comodel_name
    return field


# ---------------------------------------------------------------------------
# E23: Direct ownership path (user_id -> res.users)
# ---------------------------------------------------------------------------


class TestE23DirectPath:
    """Tests for direct ownership paths (single hop)."""

    def test_valid_direct_user_id(self):
        """Direct user_id Many2one to res.users produces no errors."""
        models = [
            _make_model("test.model", [
                _make_field("user_id", "Many2one", "res.users"),
            ]),
        ]
        pages = [
            {
                "id": "test_page",
                "type": "detail",
                "model": "test.model",
                "route": "/my/test",
                "ownership": "user_id",
            },
        ]
        spec = _make_spec(pages, models)
        issues = _check_e23(Path("/tmp/fake"), spec=spec)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_invalid_direct_path_not_res_users(self):
        """Direct ownership field pointing to non-res.users model produces E23 error."""
        models = [
            _make_model("test.model", [
                _make_field("student_id", "Many2one", "uni.student"),
            ]),
        ]
        pages = [
            {
                "id": "test_page",
                "type": "detail",
                "model": "test.model",
                "route": "/my/test",
                "ownership": "student_id",
            },
        ]
        spec = _make_spec(pages, models)
        issues = _check_e23(Path("/tmp/fake"), spec=spec)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 1
        assert "E23" in errors[0].code
        assert "res.users" in errors[0].message


# ---------------------------------------------------------------------------
# E23: Multi-hop ownership path (student_id.user_id)
# ---------------------------------------------------------------------------


class TestE23MultiHopPath:
    """Tests for multi-hop ownership paths."""

    def test_valid_two_hop_path(self):
        """Two-hop path student_id.user_id traversing uni.student -> res.users is valid."""
        models = [
            _make_model("uni.enrollment", [
                _make_field("student_id", "Many2one", "uni.student"),
            ]),
            _make_model("uni.student", [
                _make_field("user_id", "Many2one", "res.users"),
            ]),
        ]
        pages = [
            {
                "id": "enrollments",
                "type": "list",
                "model": "uni.enrollment",
                "route": "/my/enrollments",
                "ownership": "student_id.user_id",
            },
        ]
        spec = _make_spec(pages, models)
        issues = _check_e23(Path("/tmp/fake"), spec=spec)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_two_hop_terminates_wrong_model(self):
        """Two-hop path terminating at wrong model produces E23 error."""
        models = [
            _make_model("uni.enrollment", [
                _make_field("student_id", "Many2one", "uni.student"),
            ]),
            _make_model("uni.student", [
                _make_field("department_id", "Many2one", "hr.department"),
            ]),
        ]
        pages = [
            {
                "id": "enrollments",
                "type": "list",
                "model": "uni.enrollment",
                "route": "/my/enrollments",
                "ownership": "student_id.department_id",
            },
        ]
        spec = _make_spec(pages, models)
        issues = _check_e23(Path("/tmp/fake"), spec=spec)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 1
        assert "res.users" in errors[0].message

    def test_intermediate_field_not_found(self):
        """Non-existent field in path produces E23 error."""
        models = [
            _make_model("uni.enrollment", [
                _make_field("course_id", "Many2one", "academic.course"),
            ]),
        ]
        pages = [
            {
                "id": "enrollments",
                "type": "list",
                "model": "uni.enrollment",
                "route": "/my/enrollments",
                "ownership": "student_id.user_id",
            },
        ]
        spec = _make_spec(pages, models)
        issues = _check_e23(Path("/tmp/fake"), spec=spec)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1
        assert any("student_id" in e.message and "not found" in e.message for e in errors)


# ---------------------------------------------------------------------------
# E23: Unresolvable model (warning)
# ---------------------------------------------------------------------------


class TestE23UnresolvableModel:
    """Tests for graceful handling when models can't be resolved."""

    def test_model_not_in_spec_emits_warning(self):
        """When page model isn't in spec or registry, emit warning not error."""
        pages = [
            {
                "id": "unknown",
                "type": "detail",
                "model": "unknown.model",
                "route": "/my/unknown",
                "ownership": "user_id",
            },
        ]
        spec = _make_spec(pages, models=[])
        issues = _check_e23(Path("/tmp/fake"), spec=spec)
        warnings = [i for i in issues if i.severity == "warning"]
        assert len(warnings) >= 1
        assert any("unknown.model" in w.message for w in warnings)


# ---------------------------------------------------------------------------
# E23: No portal section (no-op)
# ---------------------------------------------------------------------------


class TestE23NoPortal:
    """Tests that E23 is a no-op when no portal section exists."""

    def test_no_portal_key_returns_empty(self):
        """Spec without portal key returns no issues."""
        spec: dict[str, Any] = {
            "module_name": "test",
            "models": [],
        }
        issues = _check_e23(Path("/tmp/fake"), spec=spec)
        assert issues == []

    def test_none_spec_returns_empty(self):
        """None spec returns no issues."""
        issues = _check_e23(Path("/tmp/fake"), spec=None)
        assert issues == []


# ---------------------------------------------------------------------------
# E23: Integration with semantic_validate
# ---------------------------------------------------------------------------


class TestE23Integration:
    """Tests that E23 is called from semantic_validate()."""

    def test_semantic_validate_accepts_spec_param(self, tmp_path: Path):
        """semantic_validate() accepts optional spec parameter."""
        # Create a minimal module directory
        manifest = tmp_path / "__manifest__.py"
        manifest.write_text("{'name': 'test', 'depends': ['base']}")

        # Call with spec parameter -- should not raise
        result = semantic_validate(tmp_path, spec=None)
        assert result is not None

    def test_semantic_validate_runs_e23_with_spec(self, tmp_path: Path):
        """semantic_validate() runs E23 when spec has portal section with errors."""
        manifest = tmp_path / "__manifest__.py"
        manifest.write_text("{'name': 'test', 'depends': ['base', 'portal']}")

        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "__init__.py").write_text("")

        spec = _make_spec(
            pages=[
                {
                    "id": "test_page",
                    "type": "detail",
                    "model": "test.model",
                    "route": "/my/test",
                    "ownership": "bad_field",
                },
            ],
            models=[
                _make_model("test.model", [
                    _make_field("name", "Char"),
                ]),
            ],
        )

        result = semantic_validate(tmp_path, spec=spec)
        e23_issues = [e for e in result.errors if e.code == "E23"]
        assert len(e23_issues) >= 1
