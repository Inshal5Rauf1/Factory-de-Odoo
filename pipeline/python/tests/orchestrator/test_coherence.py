"""Tests for orchestrator coherence module."""
from __future__ import annotations

from amil_utils.orchestrator.coherence import (
    BASE_ODOO_MODELS,
    check_computed_depends,
    check_duplicate_models,
    check_many2one_targets,
    check_security_groups,
    run_all_checks,
)


EMPTY_REGISTRY = {"models": {}}


class TestCheckMany2oneTargets:
    def test_passes_with_known_targets(self) -> None:
        spec = {"models": [{"name": "test.model", "fields": [
            {"name": "partner_id", "type": "Many2one", "comodel_name": "res.partner"},
        ]}]}
        result = check_many2one_targets(spec, EMPTY_REGISTRY)
        assert result["status"] == "pass"

    def test_fails_with_unknown_target(self) -> None:
        spec = {"models": [{"name": "test.model", "fields": [
            {"name": "custom_id", "type": "Many2one", "comodel_name": "nonexistent.model"},
        ]}]}
        result = check_many2one_targets(spec, EMPTY_REGISTRY)
        assert result["status"] == "fail"
        assert len(result["violations"]) == 1

    def test_resolves_from_registry(self) -> None:
        spec = {"models": [{"name": "test.model", "fields": [
            {"name": "custom_id", "type": "Many2one", "comodel_name": "custom.model"},
        ]}]}
        registry = {"models": {"custom.model": {"module": "custom_mod"}}}
        result = check_many2one_targets(spec, registry)
        assert result["status"] == "pass"

    def test_resolves_from_same_spec(self) -> None:
        spec = {"models": [
            {"name": "a.model", "fields": [
                {"name": "b_id", "type": "Many2one", "comodel_name": "b.model"},
            ]},
            {"name": "b.model", "fields": []},
        ]}
        result = check_many2one_targets(spec, EMPTY_REGISTRY)
        assert result["status"] == "pass"

    def test_ignores_non_relational_fields(self) -> None:
        spec = {"models": [{"name": "test.model", "fields": [
            {"name": "name", "type": "Char", "comodel_name": "nonexistent.model"},
        ]}]}
        result = check_many2one_targets(spec, EMPTY_REGISTRY)
        assert result["status"] == "pass"


class TestCheckDuplicateModels:
    def test_passes_when_no_duplicates(self) -> None:
        spec = {"models": [{"name": "new.model", "fields": []}]}
        result = check_duplicate_models(spec, EMPTY_REGISTRY)
        assert result["status"] == "pass"

    def test_fails_on_cross_module_duplicate(self) -> None:
        spec = {"models": [{"name": "hr.employee", "module": "my_mod", "fields": []}]}
        registry = {"models": {"hr.employee": {"module": "hr_base"}}}
        result = check_duplicate_models(spec, registry)
        assert result["status"] == "fail"
        assert result["violations"][0]["registry_module"] == "hr_base"

    def test_allows_same_module_update(self) -> None:
        spec = {"models": [{"name": "hr.employee", "module": "hr_base", "fields": []}]}
        registry = {"models": {"hr.employee": {"module": "hr_base"}}}
        result = check_duplicate_models(spec, registry)
        assert result["status"] == "pass"


class TestCheckComputedDepends:
    def test_passes_with_valid_depends(self) -> None:
        spec = {"models": [{"name": "test.model", "fields": [
            {"name": "amount", "type": "Float"},
            {"name": "total", "type": "Float", "compute": "_compute_total",
             "depends": ["amount"]},
        ]}]}
        result = check_computed_depends(spec, EMPTY_REGISTRY)
        assert result["status"] == "pass"

    def test_fails_with_missing_depends(self) -> None:
        spec = {"models": [{"name": "test.model", "fields": [
            {"name": "total", "type": "Float", "compute": "_compute_total",
             "depends": ["nonexistent_field"]},
        ]}]}
        result = check_computed_depends(spec, EMPTY_REGISTRY)
        assert result["status"] == "fail"

    def test_dot_notation_validates_first_segment(self) -> None:
        spec = {"models": [{"name": "test.model", "fields": [
            {"name": "partner_id", "type": "Many2one"},
            {"name": "partner_name", "type": "Char", "compute": "_compute",
             "depends": ["partner_id.name"]},
        ]}]}
        result = check_computed_depends(spec, EMPTY_REGISTRY)
        assert result["status"] == "pass"


class TestCheckSecurityGroups:
    def test_passes_when_consistent(self) -> None:
        spec = {"security": {
            "roles": ["manager", "user"],
            "acl": {"manager": {"crud": "1111"}, "user": {"crud": "1100"}},
            "defaults": {},
        }}
        result = check_security_groups(spec, EMPTY_REGISTRY)
        assert result["status"] == "pass"

    def test_fails_on_acl_without_role(self) -> None:
        spec = {"security": {
            "roles": ["manager"],
            "acl": {"manager": {}, "ghost": {}},
        }}
        result = check_security_groups(spec, EMPTY_REGISTRY)
        assert result["status"] == "fail"
        assert any(v["role"] == "ghost" for v in result["violations"])

    def test_warns_role_without_acl(self) -> None:
        spec = {"security": {
            "roles": ["manager", "user"],
            "acl": {"manager": {}},
        }}
        result = check_security_groups(spec, EMPTY_REGISTRY)
        assert result["status"] == "fail"
        assert any(v["role"] == "user" for v in result["violations"])

    def test_passes_with_no_security(self) -> None:
        result = check_security_groups({}, EMPTY_REGISTRY)
        assert result["status"] == "pass"


class TestRunAllChecks:
    def test_all_pass(self) -> None:
        spec = {"models": [{"name": "test.model", "fields": []}]}
        result = run_all_checks(spec, EMPTY_REGISTRY)
        assert result["status"] == "pass"
        assert len(result["checks"]) == 4

    def test_one_failure_fails_overall(self) -> None:
        spec = {"models": [{"name": "test.model", "fields": [
            {"name": "x", "type": "Many2one", "comodel_name": "bad.model"},
        ]}]}
        result = run_all_checks(spec, EMPTY_REGISTRY)
        assert result["status"] == "fail"


class TestBaseOdooModels:
    def test_contains_common_models(self) -> None:
        assert "res.partner" in BASE_ODOO_MODELS
        assert "res.users" in BASE_ODOO_MODELS
        assert "mail.thread" in BASE_ODOO_MODELS
