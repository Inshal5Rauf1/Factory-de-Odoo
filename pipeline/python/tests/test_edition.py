"""Tests for Enterprise edition detection and alternative lookup."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amil_utils.edition import (
    check_enterprise_dependencies,
    load_enterprise_registry,
)


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


def test_registry_loads():
    """load_enterprise_registry() returns dict with 'enterprise_modules' key
    containing 30+ entries."""
    registry = load_enterprise_registry()
    assert "enterprise_modules" in registry
    assert len(registry["enterprise_modules"]) >= 30


def test_known_modules_present():
    """Registry contains well-known Enterprise modules."""
    registry = load_enterprise_registry()
    modules = registry["enterprise_modules"]
    for name in ("helpdesk", "account_asset", "planning", "web_studio", "payroll"):
        assert name in modules, f"{name} missing from Enterprise registry"


def test_each_entry_has_required_keys():
    """Every entry in registry has display_name, category, description keys."""
    registry = load_enterprise_registry()
    for name, entry in registry["enterprise_modules"].items():
        for key in ("display_name", "category", "description"):
            assert key in entry, f"Entry '{name}' missing key '{key}'"


# ---------------------------------------------------------------------------
# Enterprise dependency checking
# ---------------------------------------------------------------------------


def test_enterprise_dep_flagged():
    """check_enterprise_dependencies(['base', 'helpdesk']) returns 1 warning
    for 'helpdesk'."""
    warnings = check_enterprise_dependencies(["base", "helpdesk"])
    assert len(warnings) == 1
    assert warnings[0]["module"] == "helpdesk"


def test_community_alternative():
    """Warning for 'helpdesk' includes alternative='helpdesk_mgmt',
    alternative_repo='OCA/helpdesk'."""
    warnings = check_enterprise_dependencies(["helpdesk"])
    assert len(warnings) == 1
    w = warnings[0]
    assert w["alternative"] == "helpdesk_mgmt"
    assert w["alternative_repo"] == "OCA/helpdesk"


def test_no_alternative():
    """Warning for 'web_studio' has alternative=None (no OCA equivalent)."""
    warnings = check_enterprise_dependencies(["web_studio"])
    assert len(warnings) == 1
    assert warnings[0]["alternative"] is None


def test_clean_deps_empty():
    """check_enterprise_dependencies(['base', 'mail', 'sale']) returns empty list."""
    warnings = check_enterprise_dependencies(["base", "mail", "sale"])
    assert warnings == []


def test_multiple_ee_deps():
    """check_enterprise_dependencies(['helpdesk', 'account_asset']) returns
    2 warnings."""
    warnings = check_enterprise_dependencies(["helpdesk", "account_asset"])
    assert len(warnings) == 2
    modules = {w["module"] for w in warnings}
    assert modules == {"helpdesk", "account_asset"}


def test_default_registry_path():
    """When registry_path is None, function uses bundled
    data/enterprise_modules.json."""
    # Should not raise -- uses default path internally
    warnings = check_enterprise_dependencies(["base"])
    assert isinstance(warnings, list)
