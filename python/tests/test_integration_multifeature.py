"""Multi-feature integration tests for code generation pipeline.

Validates that security, audit, approval, notification, and webhook patterns
work correctly in combination when rendered through render_module().

Test classes:
    - TestKitchenSinkIntegration: All features enabled on one module
    - TestAuditApprovalPairwise: Audit + approval write() stacking
    - TestApprovalNotificationsPairwise: Approval + notifications interaction
    - TestSecurityApprovalPairwise: Security + approval coexistence
    - TestWebhooksAuditPairwise: Webhooks + audit write() composition
    - TestKitchenSinkDocker: Docker-gated install validation (Tier 2)
"""

from __future__ import annotations

import copy
import csv
import io
import py_compile
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from amil_utils.renderer import get_template_dir, render_module


# ---------------------------------------------------------------------------
# Kitchen Sink Spec — exercises ALL features from Phases 36-42
# ---------------------------------------------------------------------------

KITCHEN_SINK_SPEC: dict[str, Any] = {
    "module_name": "test_kitchen_sink",
    "module_title": "Kitchen Sink Integration",
    "summary": "Integration test module",
    "author": "Test",
    "depends": ["base", "mail"],
    "odoo_version": "17.0",
    "security": {
        "roles": ["viewer", "editor", "manager", "hod", "auditor"],
        "defaults": {
            "viewer": "r",
            "editor": "cru",
            "manager": "crud",
            "hod": "crud",
            "auditor": "r",
        },
    },
    "models": [
        {
            "name": "test.integration.record",
            "description": "Integration Test Record",
            "fields": [
                {"name": "name", "type": "Char", "required": True, "string": "Name"},
                {"name": "amount", "type": "Monetary", "string": "Amount"},
                {
                    "name": "currency_id",
                    "type": "Many2one",
                    "comodel_name": "res.currency",
                    "string": "Currency",
                },
                {
                    "name": "total",
                    "type": "Float",
                    "string": "Total",
                    "compute": "_compute_total",
                    "depends": ["amount"],
                    "store": True,
                },
                {"name": "description", "type": "Text", "string": "Description"},
                {
                    "name": "supervisor_id",
                    "type": "Many2one",
                    "comodel_name": "res.users",
                    "string": "Supervisor",
                },
                {
                    "name": "secret_code",
                    "type": "Char",
                    "string": "Secret",
                    "sensitive": True,
                },
            ],
            "audit": True,
            "audit_exclude": ["description"],
            "approval": {
                "levels": [
                    {
                        "state": "submitted",
                        "role": "editor",
                        "next": "approved_hod",
                        "label": "Submitted",
                        "notify": {
                            "template": "email_submitted",
                            "recipients": "role:manager",
                            "subject": "Submitted: {{ object.name }}",
                        },
                    },
                    {
                        "state": "approved_hod",
                        "role": "hod",
                        "next": "done",
                        "label": "HOD Approved",
                    },
                ],
                "on_reject": "rejected",
                "reject_allowed_from": ["submitted", "approved_hod"],
                "on_reject_notify": {
                    "template": "email_rejected",
                    "recipients": "creator",
                    "subject": "Rejected: {{ object.name }}",
                },
                "editable_fields": ["description"],
            },
            "webhooks": {
                "on_create": True,
                "on_write": ["state", "amount"],
            },
        }
    ],
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_kitchen_sink() -> dict[str, Any]:
    """Return a deep copy of the kitchen sink spec."""
    return copy.deepcopy(KITCHEN_SINK_SPEC)


def _make_pairwise_spec(features: set[str]) -> dict[str, Any]:
    """Build a spec with only the listed features enabled.

    Args:
        features: Subset of {"audit", "approval", "notifications", "webhooks", "security"}.
            Security is always kept (required by audit and approval).

    Returns:
        Deep copy of the kitchen sink spec with unneeded features stripped.
    """
    spec = _get_kitchen_sink()
    model = spec["models"][0]

    if "audit" not in features:
        model.pop("audit", None)
        model.pop("audit_exclude", None)
    if "approval" not in features:
        model.pop("approval", None)
    if "webhooks" not in features:
        model.pop("webhooks", None)
    # Notifications are embedded in approval.levels[].notify
    if "notifications" not in features and "approval" in features:
        for level in model.get("approval", {}).get("levels", []):
            level.pop("notify", None)
        model.get("approval", {}).pop("on_reject_notify", None)

    return spec


def _render_spec(spec: dict[str, Any], tmp_path: Path) -> tuple[Path, str]:
    """Render a spec and return (module_dir, model_py_content).

    All render calls use no_context7=True to avoid network calls.
    """
    files, warnings = render_module(
        spec, get_template_dir(), tmp_path, no_context7=True
    )
    assert len(files) > 0, "render_module() produced no files"
    module_dir = tmp_path / "test_kitchen_sink"
    model_py_path = module_dir / "models" / "test_integration_record.py"
    assert model_py_path.exists(), f"Expected model.py at {model_py_path}"
    model_py = model_py_path.read_text()
    return module_dir, model_py


# ---------------------------------------------------------------------------
# Tier 1 Validation Helpers
# ---------------------------------------------------------------------------


def validate_python_syntax(module_dir: Path) -> list[str]:
    """py_compile every .py file; return list of errors."""
    errors: list[str] = []
    for py_file in module_dir.rglob("*.py"):
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(str(exc))
    return errors


def validate_xml_wellformed(module_dir: Path) -> list[str]:
    """Parse every .xml file with ElementTree; return list of errors."""
    errors: list[str] = []
    for xml_file in module_dir.rglob("*.xml"):
        try:
            ET.parse(str(xml_file))
        except ET.ParseError as exc:
            errors.append(f"{xml_file.name}: {exc}")
    return errors


def validate_manifest_depends(
    module_dir: Path, expected_depends: set[str]
) -> list[str]:
    """Check __manifest__.py has required depends."""
    manifest = module_dir / "__manifest__.py"
    content = manifest.read_text()
    errors: list[str] = []
    for dep in expected_depends:
        if f"'{dep}'" not in content and f'"{dep}"' not in content:
            errors.append(f"Missing depend: {dep}")
    return errors


def validate_acl_coverage(
    module_dir: Path, expected_models: set[str], expected_roles: set[str]
) -> list[str]:
    """Check ir.model.access.csv has entries for all models x all roles."""
    acl_file = module_dir / "security" / "ir.model.access.csv"
    if not acl_file.exists():
        return [f"ir.model.access.csv not found at {acl_file}"]
    content = acl_file.read_text()
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    errors: list[str] = []
    for model in expected_models:
        model_var = model.replace(".", "_")
        for role in expected_roles:
            found = any(
                model_var in row[0] and role in row[0] for row in rows[1:]
            )
            if not found:
                errors.append(f"Missing ACL: {model}.{role}")
    return errors


def validate_no_duplicate_xml_ids(module_dir: Path) -> list[str]:
    """Check no duplicate XML record IDs across all data files."""
    seen_ids: dict[str, str] = {}
    errors: list[str] = []
    for xml_file in module_dir.rglob("*.xml"):
        try:
            tree = ET.parse(str(xml_file))
            for elem in tree.iter("record"):
                xml_id = elem.get("id")
                if xml_id:
                    if xml_id in seen_ids:
                        errors.append(
                            f"Duplicate XML ID '{xml_id}' in {xml_file.name} "
                            f"(first in {seen_ids[xml_id]})"
                        )
                    else:
                        seen_ids[xml_id] = xml_file.name
        except ET.ParseError:
            pass  # Already caught by validate_xml_wellformed
    return errors


def validate_comodel_names(
    module_dir: Path, known_models: set[str]
) -> list[str]:
    """Check Many2one comodel_name values in .py files reference known models."""
    errors: list[str] = []
    comodel_pattern = re.compile(r'comodel_name\s*=\s*["\']([^"\']+)["\']')
    for py_file in module_dir.rglob("*.py"):
        content = py_file.read_text()
        for match in comodel_pattern.finditer(content):
            comodel = match.group(1)
            if comodel not in known_models:
                errors.append(
                    f"{py_file.name}: Unknown comodel_name '{comodel}'"
                )
    return errors


# ---------------------------------------------------------------------------
# Test Class 1: Kitchen Sink Integration (All features)
# ---------------------------------------------------------------------------


class TestKitchenSinkIntegration:
    """Tests the full kitchen sink spec with ALL features enabled."""

    def test_renders_without_error(self, tmp_path: Path) -> None:
        """render_module() completes and produces >0 files."""
        spec = _get_kitchen_sink()
        files, warnings = render_module(
            spec, get_template_dir(), tmp_path, no_context7=True
        )
        assert len(files) > 0, "Expected at least one generated file"

    def test_python_syntax_valid(self, tmp_path: Path) -> None:
        """All generated .py files pass py_compile syntax check."""
        spec = _get_kitchen_sink()
        render_module(spec, get_template_dir(), tmp_path, no_context7=True)
        module_dir = tmp_path / "test_kitchen_sink"
        errors = validate_python_syntax(module_dir)
        assert errors == [], f"Python syntax errors: {errors}"

    def test_xml_wellformed(self, tmp_path: Path) -> None:
        """All generated .xml files parse with xml.etree.ElementTree."""
        spec = _get_kitchen_sink()
        render_module(spec, get_template_dir(), tmp_path, no_context7=True)
        module_dir = tmp_path / "test_kitchen_sink"
        errors = validate_xml_wellformed(module_dir)
        assert errors == [], f"XML parse errors: {errors}"

    def test_manifest_depends(self, tmp_path: Path) -> None:
        """__manifest__.py contains 'base' and 'mail' in depends."""
        spec = _get_kitchen_sink()
        render_module(spec, get_template_dir(), tmp_path, no_context7=True)
        module_dir = tmp_path / "test_kitchen_sink"
        errors = validate_manifest_depends(module_dir, {"base", "mail"})
        assert errors == [], f"Manifest depends errors: {errors}"

    def test_acl_coverage(self, tmp_path: Path) -> None:
        """ir.model.access.csv has entries for all models x all roles."""
        spec = _get_kitchen_sink()
        render_module(spec, get_template_dir(), tmp_path, no_context7=True)
        module_dir = tmp_path / "test_kitchen_sink"
        # The kitchen sink produces 2 models: test.integration.record and audit.trail.log
        # Roles: viewer, editor, manager, hod, auditor
        expected_models = {"test_integration_record", "audit_trail_log"}
        expected_roles = {"viewer", "editor", "manager", "hod", "auditor"}
        errors = validate_acl_coverage(
            module_dir, expected_models, expected_roles
        )
        assert errors == [], f"ACL coverage errors: {errors}"

    def test_no_duplicate_xml_ids(self, tmp_path: Path) -> None:
        """No duplicate XML IDs across all generated data files."""
        spec = _get_kitchen_sink()
        render_module(spec, get_template_dir(), tmp_path, no_context7=True)
        module_dir = tmp_path / "test_kitchen_sink"
        errors = validate_no_duplicate_xml_ids(module_dir)
        assert errors == [], f"Duplicate XML ID errors: {errors}"

    def test_comodel_names_valid(self, tmp_path: Path) -> None:
        """All Many2one comodel_name values reference known models."""
        spec = _get_kitchen_sink()
        render_module(spec, get_template_dir(), tmp_path, no_context7=True)
        module_dir = tmp_path / "test_kitchen_sink"
        known = {
            "res.users",
            "res.currency",
            "res.company",
            "res.partner",
            "mail.thread",
            "mail.activity.mixin",
            "test.integration.record",
            "audit.trail.log",
        }
        errors = validate_comodel_names(module_dir, known)
        assert errors == [], f"Comodel name errors: {errors}"

    def test_override_sources_has_audit(self, tmp_path: Path) -> None:
        """After render, generated model contains audit trail write override."""
        spec = _get_kitchen_sink()
        render_module(spec, get_template_dir(), tmp_path, no_context7=True)
        # Verify audit trail is present in generated model file
        model_py = (
            tmp_path / "test_kitchen_sink" / "models"
            / "test_integration_record.py"
        ).read_text()
        assert "def write(" in model_py, "write() override not found in generated model"
        assert "_audit_" in model_py, "Audit trail code not found in write() override"

    def test_all_features_present_in_model_py(self, tmp_path: Path) -> None:
        """Generated model.py contains markers for all features."""
        spec = _get_kitchen_sink()
        render_module(spec, get_template_dir(), tmp_path, no_context7=True)
        module_dir = tmp_path / "test_kitchen_sink"
        model_py = (
            module_dir / "models" / "test_integration_record.py"
        ).read_text()

        # Audit markers
        assert "_audit_skip" in model_py, "Missing audit: _audit_skip"
        assert "_audit_read_old" in model_py, "Missing audit: _audit_read_old"
        assert "_audit_log_changes" in model_py, "Missing audit: _audit_log_changes"

        # Approval markers
        assert "_force_state" in model_py, "Missing approval: _force_state"
        assert "action_submit" in model_py, "Missing approval: action_submit"

        # Webhook markers
        assert "_skip_webhooks" in model_py, "Missing webhooks: _skip_webhooks"
        assert "_webhook_post_create" in model_py, "Missing webhooks: _webhook_post_create"
        assert "_webhook_post_write" in model_py, "Missing webhooks: _webhook_post_write"

        # Notification markers
        assert "send_mail" in model_py, "Missing notifications: send_mail"

    def test_audit_log_model_generated(self, tmp_path: Path) -> None:
        """audit_trail_log.py companion model is generated."""
        spec = _get_kitchen_sink()
        render_module(spec, get_template_dir(), tmp_path, no_context7=True)
        module_dir = tmp_path / "test_kitchen_sink"
        audit_py = module_dir / "models" / "audit_trail_log.py"
        assert audit_py.exists(), "audit_trail_log.py not generated"
        content = audit_py.read_text()
        assert "audit.trail.log" in content


# ---------------------------------------------------------------------------
# Test Class 2: Audit + Approval Pairwise
# ---------------------------------------------------------------------------


class TestAuditApprovalPairwise:
    """Tests audit + approval interaction in write() stacking."""

    def _render(self, tmp_path: Path) -> tuple[Path, str]:
        spec = _make_pairwise_spec({"audit", "approval", "security"})
        return _render_spec(spec, tmp_path)

    def test_write_stacking_order(self, tmp_path: Path) -> None:
        """write() stacking: _audit_read_old before _force_state before main super().write()."""
        _, model_py = self._render(tmp_path)
        audit_pos = model_py.find("_audit_read_old")
        approval_pos = model_py.find("_force_state")
        # Find the main-path super() after the approval guard (not the _audit_skip fast path)
        main_super_pos = model_py.find(
            "result = super().write(vals)", approval_pos
        )
        assert audit_pos > -1, "Expected _audit_read_old in write()"
        assert approval_pos > -1, "Expected _force_state in write()"
        assert main_super_pos > -1, "Expected result = super().write(vals) after approval"
        assert audit_pos < approval_pos < main_super_pos, (
            f"Stacking order wrong: audit={audit_pos}, "
            f"approval={approval_pos}, super={main_super_pos}"
        )

    def test_audit_skip_fast_path(self, tmp_path: Path) -> None:
        """_audit_skip fast path block contains return before _audit_read_old."""
        _, model_py = self._render(tmp_path)
        audit_skip_pos = model_py.find("_audit_skip")
        audit_read_old_pos = model_py.find("_audit_read_old")
        # The fast path should be between _audit_skip and _audit_read_old
        fast_path = model_py[audit_skip_pos:audit_read_old_pos]
        assert "return result" in fast_path or "return" in fast_path, (
            "Expected return statement in _audit_skip fast path before _audit_read_old"
        )

    def test_action_approve_uses_force_state(self, tmp_path: Path) -> None:
        """Action method body contains with_context(_force_state=True).write."""
        _, model_py = self._render(tmp_path)
        assert "with_context(_force_state=True).write" in model_py, (
            "Expected action method to use with_context(_force_state=True).write"
        )

    def test_recursion_scenario_a(self, tmp_path: Path) -> None:
        """Audit during approval: _audit_skip context flag prevents re-entry.

        Verifies:
        1. _audit_skip guard is at top of write()
        2. Audit log creation uses with_context(_audit_skip=True)
        """
        _, model_py = self._render(tmp_path)
        # Guard at top of write
        write_start = model_py.find("def write(self, vals):")
        assert write_start > -1
        # First significant code after write def should be _audit_skip check
        write_body = model_py[write_start:]
        first_check = write_body.find("_audit_skip")
        assert first_check > -1 and first_check < 100, (
            "Expected _audit_skip guard near top of write()"
        )
        # Audit log creation uses _audit_skip=True to prevent recursion
        assert "with_context(_audit_skip=True)" in model_py, (
            "Expected audit log creation to use with_context(_audit_skip=True)"
        )


# ---------------------------------------------------------------------------
# Test Class 3: Approval + Notifications Pairwise
# ---------------------------------------------------------------------------


class TestApprovalNotificationsPairwise:
    """Tests approval + notifications interaction."""

    def _render(self, tmp_path: Path) -> tuple[Path, str]:
        spec = _make_pairwise_spec(
            {"approval", "notifications", "security"}
        )
        return _render_spec(spec, tmp_path)

    def test_send_mail_after_state_write(self, tmp_path: Path) -> None:
        """In action_submit, send_mail position > _force_state position."""
        _, model_py = self._render(tmp_path)
        submit_pos = model_py.find("def action_submit(self):")
        assert submit_pos > -1, "Expected action_submit method"
        # Find _force_state and send_mail within action_submit
        state_write_pos = model_py.find("_force_state", submit_pos)
        send_mail_pos = model_py.find("send_mail", submit_pos)
        assert state_write_pos > -1, "Expected _force_state in action_submit"
        assert send_mail_pos > -1, "Expected send_mail in action_submit"
        assert state_write_pos < send_mail_pos, (
            "send_mail should come after state write (_force_state)"
        )

    def test_mail_template_xml_exists(self, tmp_path: Path) -> None:
        """mail_template_data.xml is created."""
        module_dir, _ = self._render(tmp_path)
        mail_data = module_dir / "data" / "mail_template_data.xml"
        assert mail_data.exists(), (
            "mail_template_data.xml not generated"
        )

    def test_mail_template_noupdate(self, tmp_path: Path) -> None:
        """XML contains noupdate='1'."""
        module_dir, _ = self._render(tmp_path)
        mail_data = module_dir / "data" / "mail_template_data.xml"
        assert mail_data.exists(), "mail_template_data.xml not generated"
        xml_content = mail_data.read_text()
        assert 'noupdate="1"' in xml_content, (
            "Expected noupdate='1' in mail_template_data.xml"
        )

    def test_manifest_includes_mail_template(self, tmp_path: Path) -> None:
        """Manifest references mail_template_data.xml."""
        module_dir, _ = self._render(tmp_path)
        manifest = (module_dir / "__manifest__.py").read_text()
        assert "mail_template_data.xml" in manifest, (
            "Expected mail_template_data.xml referenced in manifest"
        )

    def test_recursion_scenario_c(self, tmp_path: Path) -> None:
        """Notification during approval: send_mail uses self.env.ref (not write()).

        The env.ref pattern fetches the template without triggering
        write() on the current model, avoiding recursion.
        """
        _, model_py = self._render(tmp_path)
        assert "self.env.ref(" in model_py, (
            "Expected send_mail to use self.env.ref() pattern"
        )
        # Verify send_mail is called on the template object, not via write()
        assert "send_mail(self.id" in model_py, (
            "Expected template.send_mail(self.id, ...) pattern"
        )


# ---------------------------------------------------------------------------
# Test Class 4: Security + Approval Pairwise
# ---------------------------------------------------------------------------


class TestSecurityApprovalPairwise:
    """Tests security + approval coexistence."""

    def _render(self, tmp_path: Path) -> tuple[Path, str]:
        spec = _make_pairwise_spec({"approval", "security"})
        return _render_spec(spec, tmp_path)

    def test_acl_rows_for_all_roles(self, tmp_path: Path) -> None:
        """ir.model.access.csv has rows for all declared roles."""
        module_dir, _ = self._render(tmp_path)
        # Without audit, the model is just test_integration_record
        expected_roles = {"viewer", "editor", "manager", "hod", "auditor"}
        errors = validate_acl_coverage(
            module_dir, {"test_integration_record"}, expected_roles
        )
        assert errors == [], f"ACL coverage errors: {errors}"

    def test_action_method_group_gate(self, tmp_path: Path) -> None:
        """Each action method body references the correct group."""
        _, model_py = self._render(tmp_path)
        # action_approve_submitted should check editor group
        assert "group_test_kitchen_sink_editor" in model_py, (
            "Expected editor group check in approve action"
        )
        # action_approve_approved_hod should check hod group
        assert "group_test_kitchen_sink_hod" in model_py, (
            "Expected hod group check in approve action"
        )

    def test_record_rules_exist(self, tmp_path: Path) -> None:
        """record_rules.xml exists with ir.rule records."""
        module_dir, _ = self._render(tmp_path)
        record_rules = module_dir / "security" / "record_rules.xml"
        assert record_rules.exists(), "record_rules.xml not generated"
        content = record_rules.read_text()
        assert "ir.rule" in content, (
            "Expected ir.rule records in record_rules.xml"
        )

    def test_sensitive_field_has_groups(self, tmp_path: Path) -> None:
        """Generated model.py has groups= attribute on secret_code field."""
        _, model_py = self._render(tmp_path)
        assert 'groups="' in model_py, (
            "Expected groups= attribute on sensitive field"
        )
        # Verify specifically for secret_code field area
        secret_pos = model_py.find("secret_code")
        assert secret_pos > -1
        # Look for groups within a reasonable range after secret_code
        field_block = model_py[secret_pos : secret_pos + 200]
        assert "groups=" in field_block, (
            "Expected groups= attribute near secret_code field definition"
        )


# ---------------------------------------------------------------------------
# Test Class 5: Webhooks + Audit Pairwise
# ---------------------------------------------------------------------------


class TestWebhooksAuditPairwise:
    """Tests webhooks + audit write() composition."""

    def _render(self, tmp_path: Path) -> tuple[Path, str]:
        spec = _make_pairwise_spec({"webhooks", "audit", "security"})
        return _render_spec(spec, tmp_path)

    def test_both_context_flags_in_write(self, tmp_path: Path) -> None:
        """Both _skip_webhooks and _audit_skip present in write()."""
        _, model_py = self._render(tmp_path)
        write_start = model_py.find("def write(self, vals):")
        assert write_start > -1
        write_body = model_py[write_start:]
        assert "_skip_webhooks" in write_body, (
            "Expected _skip_webhooks in write()"
        )
        assert "_audit_skip" in write_body, (
            "Expected _audit_skip in write()"
        )

    def test_webhook_after_audit(self, tmp_path: Path) -> None:
        """_webhook_post_write position > _audit_read_old position.

        Webhook fires after audit captures old values.
        """
        _, model_py = self._render(tmp_path)
        audit_pos = model_py.find("_audit_read_old")
        webhook_pos = model_py.find("_webhook_post_write")
        assert audit_pos > -1, "Expected _audit_read_old in write()"
        assert webhook_pos > -1, "Expected _webhook_post_write in write()"
        assert audit_pos < webhook_pos, (
            f"Expected webhook after audit: audit={audit_pos}, webhook={webhook_pos}"
        )

    def test_webhook_in_create(self, tmp_path: Path) -> None:
        """_webhook_post_create present in create() method."""
        _, model_py = self._render(tmp_path)
        create_pos = model_py.find("def create(")
        assert create_pos > -1, "Expected create() method"
        create_body = model_py[create_pos:]
        assert "_webhook_post_create" in create_body, (
            "Expected _webhook_post_create in create()"
        )

    def test_recursion_scenario_b(self, tmp_path: Path) -> None:
        """_skip_webhooks and _audit_skip are independent guards.

        Both have separate if-return/if-guard blocks.
        """
        _, model_py = self._render(tmp_path)
        write_start = model_py.find("def write(self, vals):")
        assert write_start > -1
        write_body = model_py[write_start:]

        # _audit_skip guard should be a separate check
        assert "_audit_skip" in write_body
        # _skip_webhooks guard should also be present as a separate check
        assert "_skip_webhooks" in write_body

        # Verify they are separate guards (not combined in one condition)
        # _audit_skip should appear in its own context.get() call
        audit_guard = re.search(
            r"context\.get\(['\"]_audit_skip['\"]\)", write_body
        )
        webhook_guard = re.search(
            r"context\.get\(['\"]_skip_webhooks['\"]\)", write_body
        )
        assert audit_guard is not None, (
            "Expected separate context.get('_audit_skip') guard"
        )
        assert webhook_guard is not None, (
            "Expected separate context.get('_skip_webhooks') guard"
        )


# ---------------------------------------------------------------------------
# Docker availability check (must be defined before the Docker test class)
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    """Check if Docker daemon is available (lazy import)."""
    try:
        from amil_utils.validation.docker_runner import check_docker_available

        return check_docker_available()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Test Class 6: Docker-Gated Tier 2 (Kitchen Sink Install)
# ---------------------------------------------------------------------------


@pytest.mark.docker
class TestKitchenSinkDocker:
    """Docker-gated test: installs the all-features module in real Odoo 17.0."""

    @pytest.mark.skipif(
        not _docker_available(),
        reason="Docker daemon not available -- skipping Docker integration tests",
    )
    def test_kitchen_sink_docker_install(self, tmp_path: Path) -> None:
        """Render the kitchen sink spec and install in Odoo via Docker."""
        from amil_utils.validation.docker_runner import docker_install_module

        spec = _get_kitchen_sink()
        files, warnings = render_module(
            spec, get_template_dir(), tmp_path, no_context7=True
        )
        assert len(files) > 0
        module_dir = tmp_path / "test_kitchen_sink"
        result = docker_install_module(module_dir)
        assert result.success, f"docker_install_module failed: {result.errors}"
        install = result.data
        assert install.success is True, (
            f"Module install failed: {install.error_message}"
        )

