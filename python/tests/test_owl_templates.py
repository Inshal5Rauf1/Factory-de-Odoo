"""Tests for OWL component knowledge base and template variants."""

from __future__ import annotations

from pathlib import Path

import pytest

# Project root is 3 levels up from this test file: python/tests/test_owl_templates.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestOwlKnowledgeFile:
    """Verify the OWL knowledge base file exists and has required content."""

    def test_owl_knowledge_file_exists(self):
        kb = PROJECT_ROOT / "amil" / "knowledge" / "owl.md"
        assert kb.exists(), f"Knowledge file not found: {kb}"

    def test_owl_knowledge_has_wrong_correct_pairs(self):
        kb = PROJECT_ROOT / "amil" / "knowledge" / "owl.md"
        content = kb.read_text()
        assert "WRONG" in content, "Knowledge file must contain WRONG examples"
        assert "CORRECT" in content, "Knowledge file must contain CORRECT examples"

    def test_owl_knowledge_has_at_least_10_sections(self):
        kb = PROJECT_ROOT / "amil" / "knowledge" / "owl.md"
        content = kb.read_text()
        h3_headings = [line for line in content.splitlines() if line.startswith("### ")]
        assert len(h3_headings) >= 10, (
            f"Expected at least 10 ### headings, found {len(h3_headings)}"
        )

    def test_owl_knowledge_covers_lifecycle(self):
        kb = PROJECT_ROOT / "amil" / "knowledge" / "owl.md"
        content = kb.read_text()
        assert "onWillStart" in content
        assert "setup()" in content

    def test_owl_knowledge_covers_reactive_state(self):
        kb = PROJECT_ROOT / "amil" / "knowledge" / "owl.md"
        content = kb.read_text()
        assert "useState" in content

    def test_owl_knowledge_covers_rpc(self):
        kb = PROJECT_ROOT / "amil" / "knowledge" / "owl.md"
        content = kb.read_text()
        assert "useService" in content
        assert "rpc" in content

    def test_owl_knowledge_covers_registry(self):
        kb = PROJECT_ROOT / "amil" / "knowledge" / "owl.md"
        content = kb.read_text()
        assert "registry.category" in content

    def test_owl_knowledge_covers_patch(self):
        kb = PROJECT_ROOT / "amil" / "knowledge" / "owl.md"
        content = kb.read_text()
        assert "patch" in content.lower()
        assert "@web/core/utils/patch" in content

    def test_owl_knowledge_covers_registry_categories(self):
        kb = PROJECT_ROOT / "amil" / "knowledge" / "owl.md"
        content = kb.read_text()
        for category in ("fields", "actions", "views", "systray"):
            assert category in content, f"Missing registry category: {category}"


class TestStatButtonTemplate:
    """Verify the stat button OWL template."""

    def test_stat_button_template_exists(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_stat_button.js.j2"
        assert t.exists(), f"Template not found: {t}"

    def test_stat_button_has_use_service(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_stat_button.js.j2"
        content = t.read_text()
        assert "useService" in content

    def test_stat_button_has_search_count(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_stat_button.js.j2"
        content = t.read_text()
        assert "searchCount" in content

    def test_stat_button_has_jinja_variables(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_stat_button.js.j2"
        content = t.read_text()
        assert "{{ component_class }}" in content
        assert "{{ module_name }}" in content
        assert "{{ target_model }}" in content
        assert "{{ link_field }}" in content

    def test_stat_button_has_do_action(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_stat_button.js.j2"
        content = t.read_text()
        assert "doAction" in content

    def test_stat_button_has_odoo_module_header(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_stat_button.js.j2"
        content = t.read_text()
        assert "@odoo-module" in content


class TestDashboardCardTemplate:
    """Verify the dashboard card OWL template."""

    def test_dashboard_card_template_exists(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_dashboard_card.js.j2"
        assert t.exists(), f"Template not found: {t}"

    def test_dashboard_card_has_load_metrics(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_dashboard_card.js.j2"
        content = t.read_text()
        assert "loadMetrics" in content

    def test_dashboard_card_has_use_state(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_dashboard_card.js.j2"
        content = t.read_text()
        assert "useState" in content

    def test_dashboard_card_has_jinja_variables(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_dashboard_card.js.j2"
        content = t.read_text()
        assert "{{ component_class }}" in content
        assert "{{ module_name }}" in content

    def test_dashboard_card_has_rpc_service(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_dashboard_card.js.j2"
        content = t.read_text()
        assert "useService" in content
        assert "rpc" in content

    def test_dashboard_card_has_on_will_start(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_dashboard_card.js.j2"
        content = t.read_text()
        assert "onWillStart" in content


class TestActionButtonTemplate:
    """Verify the action button OWL template."""

    def test_action_button_template_exists(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_action_button.js.j2"
        assert t.exists(), f"Template not found: {t}"

    def test_action_button_has_orm_call(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_action_button.js.j2"
        content = t.read_text()
        assert "orm.call" in content

    def test_action_button_has_notification(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_action_button.js.j2"
        content = t.read_text()
        assert "notification" in content
        assert "success" in content
        assert "danger" in content

    def test_action_button_has_jinja_variables(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_action_button.js.j2"
        content = t.read_text()
        assert "{{ component_class }}" in content
        assert "{{ module_name }}" in content
        assert "{{ target_model }}" in content
        assert "{{ action_method }}" in content

    def test_action_button_has_error_handling(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_action_button.js.j2"
        content = t.read_text()
        assert "try" in content
        assert "catch" in content

    def test_action_button_has_odoo_module_header(self):
        t = PROJECT_ROOT / "python" / "src" / "amil_utils" / "templates" / "shared" / "owl_action_button.js.j2"
        content = t.read_text()
        assert "@odoo-module" in content
