"""Tests for iterative diff-to-stage mapping (affected.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amil_utils.iterative.affected import (
    AffectedStages,
    determine_affected_stages,
)
from amil_utils.spec_differ import SpecDiff, diff_specs


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _make_diff_with_field_added() -> SpecDiff:
    old = _load_fixture("spec_v1_iterative.json")
    new = _load_fixture("spec_v2_field_added.json")
    return diff_specs(old, new)


def _make_diff_with_model_added() -> SpecDiff:
    old = _load_fixture("spec_v1_iterative.json")
    new = _load_fixture("spec_v2_model_added.json")
    return diff_specs(old, new)


# ---------------------------------------------------------------------------
# AffectedStages dataclass tests
# ---------------------------------------------------------------------------


class TestAffectedStagesDataclass:
    """AffectedStages is a frozen dataclass."""

    def test_frozen(self) -> None:
        result = AffectedStages(stages=frozenset({"models"}), diff_summary={})
        with pytest.raises(AttributeError):
            result.stages = frozenset({"views"})  # type: ignore[misc]

    def test_fields(self) -> None:
        result = AffectedStages(stages=frozenset({"models", "views"}), diff_summary={"test": True})
        assert isinstance(result.stages, frozenset)
        assert isinstance(result.diff_summary, dict)


# ---------------------------------------------------------------------------
# Category-to-stage mapping tests
# ---------------------------------------------------------------------------


class TestFieldAddedStages:
    """FIELD_ADDED -> models, views, security, tests, stubs."""

    def test_field_added_stages(self) -> None:
        diff = _make_diff_with_field_added()
        result = determine_affected_stages(diff)
        assert isinstance(result, AffectedStages)
        # FIELD_ADDED includes security unconditionally for safety
        expected = frozenset({"models", "views", "security", "tests", "stubs"})
        assert result.stages == expected


class TestFieldRemovedStages:
    """FIELD_REMOVED -> models, views, security, tests, stubs."""

    def test_field_removed_stages(self) -> None:
        old = _load_fixture("spec_v2_field_added.json")
        new = _load_fixture("spec_v1_iterative.json")
        diff = diff_specs(old, new)
        result = determine_affected_stages(diff)
        expected = frozenset({"models", "views", "security", "tests", "stubs"})
        assert result.stages == expected


class TestFieldModifiedStages:
    """FIELD_MODIFIED -> models, views, stubs."""

    def test_field_modified_stages(self) -> None:
        old = _load_fixture("spec_v1_iterative.json")
        new = json.loads(json.dumps(old))
        # Modify field type: Float -> Integer (attribute change)
        new["models"][0]["fields"][1]["required"] = False  # 'amount' required changed
        diff = diff_specs(old, new)
        result = determine_affected_stages(diff)
        assert "models" in result.stages
        assert "views" in result.stages
        assert "stubs" in result.stages


class TestModelAddedStages:
    """MODEL_ADDED -> models, views, security, tests, manifest, stubs."""

    def test_model_added_stages(self) -> None:
        diff = _make_diff_with_model_added()
        result = determine_affected_stages(diff)
        expected = frozenset({"models", "views", "security", "tests", "manifest", "stubs"})
        assert result.stages == expected


class TestModelRemovedStages:
    """MODEL_REMOVED -> models, views, security, tests, manifest, stubs."""

    def test_model_removed_stages(self) -> None:
        old = _load_fixture("spec_v2_model_added.json")
        new = _load_fixture("spec_v1_iterative.json")
        diff = diff_specs(old, new)
        result = determine_affected_stages(diff)
        expected = frozenset({"models", "views", "security", "tests", "manifest", "stubs"})
        assert result.stages == expected


class TestMethodChangedStages:
    """METHOD_ADDED or METHOD_REMOVED -> stubs only."""

    def test_method_added_stages(self) -> None:
        old = _load_fixture("spec_v1_iterative.json")
        new = json.loads(json.dumps(old))
        # Add a computed field (which implies a method addition)
        new["models"][0]["fields"].append({
            "name": "total",
            "type": "Float",
            "compute": "_compute_total",
            "store": True,
            "string": "Total",
        })
        diff = diff_specs(old, new)
        result = determine_affected_stages(diff)
        # Compute field added = FIELD_ADDED (the method is implicit).
        # Since it's a field addition, we get field_added stages.
        assert "stubs" in result.stages


class TestSecurityChangedStages:
    """SECURITY_CHANGED -> security only."""

    def test_security_changed_stages(self) -> None:
        old = _load_fixture("spec_v1_iterative.json")
        new = json.loads(json.dumps(old))
        # Change security: add a role
        new["models"][0]["security"]["roles"].append("manager")
        new["models"][0]["security"]["acl"]["manager"] = {
            "create": True, "read": True, "write": True, "unlink": True,
        }
        diff = diff_specs(old, new)
        result = determine_affected_stages(diff)
        assert "security" in result.stages


class TestApprovalChangedStages:
    """APPROVAL_CHANGED -> models, views, security, stubs."""

    def test_approval_changed_stages(self) -> None:
        old = _load_fixture("spec_v1_iterative.json")
        new = json.loads(json.dumps(old))
        new["models"][0]["approval"] = {
            "levels": [
                {"name": "submitted", "role": "editor"},
                {"name": "approved", "role": "manager"},
            ],
        }
        diff = diff_specs(old, new)
        result = determine_affected_stages(diff)
        expected = frozenset({"models", "views", "security", "stubs"})
        assert result.stages == expected


class TestViewHintChangedStages:
    """VIEW_HINT_CHANGED -> views only."""

    def test_view_hint_changed_stages(self) -> None:
        old = _load_fixture("spec_v1_iterative.json")
        new = json.loads(json.dumps(old))
        new["models"][0]["view_hints"] = {"tree_fields": ["name", "amount"]}
        diff = diff_specs(old, new)
        # view_hints is not tracked by spec_differ, so we pass raw specs
        # for attribute-level detection
        result = determine_affected_stages(diff, old_spec=old, new_spec=new)
        assert "views" in result.stages


class TestMultipleCategoriesUnion:
    """Multiple diff categories union their stages."""

    def test_field_added_plus_security_changed(self) -> None:
        old = _load_fixture("spec_v1_iterative.json")
        new = _load_fixture("spec_v2_field_added.json")
        # Also change security in new
        new_copy = json.loads(json.dumps(new))
        new_copy["models"][0]["security"]["roles"].append("manager")
        new_copy["models"][0]["security"]["acl"]["manager"] = {
            "create": True, "read": True, "write": True, "unlink": True,
        }
        diff = diff_specs(old, new_copy)
        result = determine_affected_stages(diff)
        # FIELD_ADDED union SECURITY_CHANGED
        assert "models" in result.stages
        assert "views" in result.stages
        assert "security" in result.stages
        assert "tests" in result.stages
        assert "stubs" in result.stages


class TestEmptyDiff:
    """Empty diff returns empty stages."""

    def test_empty_changes(self) -> None:
        spec = _load_fixture("spec_v1_iterative.json")
        # Create a diff with no changes (same spec)
        diff = diff_specs(spec, spec)
        result = determine_affected_stages(diff)
        assert result.stages == frozenset()


class TestDiffSummaryPresent:
    """determine_affected_stages populates diff_summary."""

    def test_summary_has_content(self) -> None:
        diff = _make_diff_with_field_added()
        result = determine_affected_stages(diff)
        assert isinstance(result.diff_summary, dict)
        assert len(result.diff_summary) > 0
