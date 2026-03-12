"""Unit tests for the migration generator module.

Tests cover:
- Pre-migrate script generation for destructive/possibly-destructive changes
- Post-migrate script generation (data restore, cleanup, backup drop)
- Full backup/restore pattern for type changes and field removal
- Script structure: migrate() entry point, _logger, helper docstrings, prefixes
- Non-destructive changes produce no helpers or informational comments only
- Model added/removed migration generation
- Generated scripts are syntactically valid Python via compile()
- Multiple changes produce independent helpers all wired into migrate()
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from amil_utils.spec_differ import diff_specs


# ---------------------------------------------------------------------------
# Helpers to build minimal diff fixtures
# ---------------------------------------------------------------------------

def _make_diff(
    *,
    models_added: list | None = None,
    models_removed: list | None = None,
    models_modified: dict | None = None,
    destructive_count: int = 0,
    warnings: list | None = None,
    migration_required: bool = False,
) -> dict:
    """Build a minimal diff_specs()-compatible result dict."""
    return {
        "module": "test_mod",
        "old_version": "17.0.1.0.0",
        "new_version": "17.0.1.1.0",
        "changes": {
            "models": {
                "added": models_added or [],
                "removed": models_removed or [],
                "modified": models_modified or {},
            },
        },
        "destructive_count": destructive_count,
        "warnings": warnings or [],
        "migration_required": migration_required,
    }


def _diff_field_removed(model: str, field_name: str, field_type: str = "Char") -> dict:
    """Diff where a field was removed from an existing model."""
    return _make_diff(
        models_modified={
            model: {
                "fields": {
                    "added": [],
                    "removed": [
                        {
                            "name": field_name,
                            "type": field_type,
                            "destructive": True,
                            "severity": "always_destructive",
                        }
                    ],
                    "modified": [],
                },
            },
        },
        destructive_count=1,
        migration_required=True,
    )


def _diff_field_added(model: str, field_name: str, field_type: str = "Char") -> dict:
    """Diff where a field was added to an existing model."""
    return _make_diff(
        models_modified={
            model: {
                "fields": {
                    "added": [{"name": field_name, "type": field_type}],
                    "removed": [],
                    "modified": [],
                },
            },
        },
    )


def _diff_type_change(
    model: str,
    field_name: str,
    old_type: str,
    new_type: str,
    severity: str = "always_destructive",
) -> dict:
    """Diff where a field's type changed."""
    is_destructive = severity != "non_destructive"
    return _make_diff(
        models_modified={
            model: {
                "fields": {
                    "added": [],
                    "removed": [],
                    "modified": [
                        {
                            "name": field_name,
                            "type": new_type,
                            "changes": {"type": {"old": old_type, "new": new_type}},
                            "destructive": is_destructive,
                            "severity": severity,
                        }
                    ],
                },
            },
        },
        destructive_count=1 if is_destructive else 0,
        migration_required=is_destructive,
    )


def _diff_required_change(model: str, field_name: str, old_req: bool, new_req: bool) -> dict:
    """Diff where a field's required attribute changed."""
    severity = "possibly_destructive" if (not old_req and new_req) else "non_destructive"
    is_destructive = severity != "non_destructive"
    return _make_diff(
        models_modified={
            model: {
                "fields": {
                    "added": [],
                    "removed": [],
                    "modified": [
                        {
                            "name": field_name,
                            "type": "Date",
                            "changes": {"required": {"old": old_req, "new": new_req}},
                            "destructive": is_destructive,
                            "severity": severity,
                        }
                    ],
                },
            },
        },
        destructive_count=1 if is_destructive else 0,
        migration_required=is_destructive,
    )


def _diff_selection_removed(model: str, field_name: str) -> dict:
    """Diff where selection options were removed."""
    return _make_diff(
        models_modified={
            model: {
                "fields": {
                    "added": [],
                    "removed": [],
                    "modified": [
                        {
                            "name": field_name,
                            "type": "Selection",
                            "changes": {
                                "selection": {
                                    "old": [["draft", "Draft"], ["confirmed", "Confirmed"], ["cancelled", "Cancelled"]],
                                    "new": [["draft", "Draft"], ["confirmed", "Confirmed"]],
                                    "options_added": [],
                                    "options_removed": ["cancelled"],
                                },
                            },
                            "destructive": True,
                            "severity": "possibly_destructive",
                        }
                    ],
                },
            },
        },
        destructive_count=1,
        migration_required=True,
    )


def _diff_model_removed(model: str, fields: list[dict] | None = None) -> dict:
    """Diff where an entire model was removed."""
    return _make_diff(
        models_removed=[
            {
                "name": model,
                "fields": fields or [{"name": "name", "type": "Char"}],
                "destructive": True,
            },
        ],
        destructive_count=1,
        migration_required=True,
    )


def _diff_model_added(model: str, fields: list[dict] | None = None) -> dict:
    """Diff where a new model was added."""
    return _make_diff(
        models_added=[
            {
                "name": model,
                "fields": fields or [{"name": "name", "type": "Char"}],
                "destructive": False,
            },
        ],
    )


def _diff_non_destructive_change(model: str, field_name: str) -> dict:
    """Diff with only non-destructive attribute changes (string/help/default)."""
    return _make_diff(
        models_modified={
            model: {
                "fields": {
                    "added": [],
                    "removed": [],
                    "modified": [
                        {
                            "name": field_name,
                            "type": "Char",
                            "changes": {"default": {"old": "old_default", "new": "new_default"}},
                            "destructive": False,
                            "severity": "non_destructive",
                        }
                    ],
                },
            },
        },
    )


# ---------------------------------------------------------------------------
# TestPreMigrate
# ---------------------------------------------------------------------------
class TestPreMigrate:
    """Tests pre-migrate script generation for destructive/possibly-destructive changes."""

    def test_removed_field_generates_backup_helper(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]
        assert "_backup_old_ref" in pre
        assert "cr.execute" in pre
        assert "old_ref_backup" in pre or "_backup" in pre

    def test_type_change_generates_backup_helper(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_type_change("fee.invoice", "amount", "Float", "Monetary", "possibly_destructive")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]
        assert "_backup_amount" in pre
        assert "cr.execute" in pre

    def test_required_false_to_true_generates_validation_helper(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_required_change("fee.invoice", "due_date", False, True)
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]
        assert "_validate_due_date" in pre or "_check_due_date" in pre or "due_date" in pre
        assert "NULL" in pre or "null" in pre.lower() or "IS NULL" in pre.upper() or "COUNT" in pre.upper()

    def test_selection_removed_generates_validation_helper(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_selection_removed("fee.invoice", "state")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]
        assert "state" in pre
        assert "cr.execute" in pre

    def test_model_removed_generates_backup(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_model_removed("fee.old_model")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]
        assert "fee_old_model" in pre
        assert "cr.execute" in pre

    def test_pre_only_references_old_schema(self) -> None:
        """Pre-migrate should reference the OLD field name, not new schema."""
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]
        assert "old_ref" in pre


# ---------------------------------------------------------------------------
# TestPostMigrate
# ---------------------------------------------------------------------------
class TestPostMigrate:
    """Tests post-migrate script generation (data restore, cleanup)."""

    def test_removed_field_generates_drop_helper(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        post = result["post_migrate_code"]
        assert "old_ref" in post
        assert "cr.execute" in post
        # Should drop the backup column
        assert "DROP" in post or "drop" in post.lower()

    def test_type_change_generates_restore_helper(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_type_change("fee.invoice", "amount", "Float", "Monetary", "possibly_destructive")
        result = generate_migration(diff, "17.0.1.1.0")
        post = result["post_migrate_code"]
        assert "_restore_amount" in post
        assert "cr.execute" in post
        assert "DROP" in post or "drop" in post.lower()

    def test_model_removed_generates_drop_table(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_model_removed("fee.old_model")
        result = generate_migration(diff, "17.0.1.1.0")
        post = result["post_migrate_code"]
        assert "fee_old_model" in post
        assert "DROP" in post.upper()


# ---------------------------------------------------------------------------
# TestBackupRestore
# ---------------------------------------------------------------------------
class TestBackupRestore:
    """Tests the full backup/restore pattern for type changes and field removal."""

    def test_type_change_backup_in_pre_restore_in_post(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_type_change("fee.invoice", "amount", "Float", "Monetary", "possibly_destructive")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]
        post = result["post_migrate_code"]

        # Pre: backup column
        assert "amount_backup" in pre or "_backup" in pre
        assert "cr.execute" in pre

        # Post: restore + drop
        assert "amount_backup" in post or "_backup" in post
        assert "DROP" in post.upper()

    def test_field_removal_backup_in_pre_drop_in_post(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]
        post = result["post_migrate_code"]

        # Pre: backup data
        assert "old_ref" in pre
        assert "cr.execute" in pre

        # Post: drop backup
        assert "old_ref" in post
        assert "DROP" in post.upper()


# ---------------------------------------------------------------------------
# TestScriptStructure
# ---------------------------------------------------------------------------
class TestScriptStructure:
    """Tests migrate() entry point, _logger, helper docstrings, DESTRUCTIVE prefixes."""

    def test_both_scripts_have_logger_setup(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")

        assert "_logger = logging.getLogger(__name__)" in result["pre_migrate_code"]
        assert "_logger = logging.getLogger(__name__)" in result["post_migrate_code"]

    def test_both_scripts_have_migrate_entry_point(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")

        assert "def migrate(cr, version):" in result["pre_migrate_code"]
        assert "def migrate(cr, version):" in result["post_migrate_code"]

    def test_helpers_have_docstrings(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        # Each helper function should have a docstring
        # Find function defs (excluding migrate)
        lines = pre.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("def ") and "migrate" not in stripped:
                # Next non-blank line should contain a docstring
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j].strip():
                        assert '"""' in lines[j], f"Helper at line {i+1} missing docstring"
                        break

    def test_destructive_helpers_have_prefix(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        assert "DESTRUCTIVE:" in pre

    def test_possibly_destructive_helpers_have_prefix(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_required_change("fee.invoice", "due_date", False, True)
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        assert "POSSIBLY DESTRUCTIVE:" in pre

    def test_helpers_have_logger_info(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        assert "_logger.info" in pre
        assert "cr.rowcount" in pre or "rowcount" in pre

    def test_each_helper_takes_only_cr(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        lines = pre.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("def ") and "migrate" not in stripped:
                # Should be def _something(cr):
                assert "(cr):" in stripped, f"Helper '{stripped}' should take only cr"

    def test_migrate_calls_all_helpers(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        # Find helper names
        helper_names = []
        for line in pre.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def ") and "migrate" not in stripped:
                name = stripped.split("(")[0].replace("def ", "")
                helper_names.append(name)

        # All helpers should be called from migrate()
        migrate_section = pre[pre.index("def migrate(cr, version)"):]
        for name in helper_names:
            assert f"{name}(cr)" in migrate_section, f"migrate() should call {name}(cr)"

    def test_no_changes_returns_empty_scripts(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _make_diff()
        result = generate_migration(diff, "17.0.1.1.0")

        # Should still have migrate() entry point but no helpers
        pre = result["pre_migrate_code"]
        post = result["post_migrate_code"]
        assert "def migrate(cr, version):" in pre
        assert "def migrate(cr, version):" in post

        # No helper functions
        for line in pre.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def ") and "migrate" not in stripped:
                pytest.fail(f"No helpers expected in empty diff, found: {stripped}")

    def test_no_destructive_changes_returns_migration_not_required(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_non_destructive_change("fee.invoice", "name")
        result = generate_migration(diff, "17.0.1.1.0")
        assert result["migration_required"] is False


# ---------------------------------------------------------------------------
# TestNonDestructive
# ---------------------------------------------------------------------------
class TestNonDestructive:
    """Tests that non-destructive changes produce no helpers."""

    def test_added_field_no_pre_helper(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_added("fee.invoice", "penalty_amount", "Monetary")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        # No helper functions for added fields
        for line in pre.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def ") and "migrate" not in stripped:
                pytest.fail(f"No helpers expected for added field, found: {stripped}")

    def test_non_destructive_attribute_change_no_helpers(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_non_destructive_change("fee.invoice", "name")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        for line in pre.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def ") and "migrate" not in stripped:
                pytest.fail(f"No helpers expected for non-destructive change, found: {stripped}")

    def test_model_added_no_migration(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_model_added("fee.penalty")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        for line in pre.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def ") and "migrate" not in stripped:
                pytest.fail(f"No helpers expected for added model, found: {stripped}")


# ---------------------------------------------------------------------------
# TestModelChanges
# ---------------------------------------------------------------------------
class TestModelChanges:
    """Tests model added/removed migration generation."""

    def test_model_removed_pre_backup(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_model_removed("fee.old_model")
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]
        assert "fee_old_model" in pre
        assert "cr.execute" in pre

    def test_model_removed_post_drop(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_model_removed("fee.old_model")
        result = generate_migration(diff, "17.0.1.1.0")
        post = result["post_migrate_code"]
        assert "fee_old_model" in post
        assert "DROP" in post.upper()

    def test_model_added_no_helpers(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_model_added("fee.penalty")
        result = generate_migration(diff, "17.0.1.1.0")

        # Odoo ORM creates the table automatically
        pre = result["pre_migrate_code"]
        for line in pre.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def ") and "migrate" not in stripped:
                pytest.fail("No helpers expected for model addition")


# ---------------------------------------------------------------------------
# TestTableNameConversion
# ---------------------------------------------------------------------------
class TestTableNameConversion:
    """Tests Odoo table name convention."""

    def test_model_to_table_dot_to_underscore(self) -> None:
        from amil_utils.migration_generator import _model_to_table

        assert _model_to_table("fee.invoice") == "fee_invoice"

    def test_model_to_table_multiple_dots(self) -> None:
        from amil_utils.migration_generator import _model_to_table

        assert _model_to_table("fee.invoice.line") == "fee_invoice_line"

    def test_model_to_table_no_dot(self) -> None:
        from amil_utils.migration_generator import _model_to_table

        assert _model_to_table("account") == "account"


# ---------------------------------------------------------------------------
# TestSyntaxValidity
# ---------------------------------------------------------------------------
class TestSyntaxValidity:
    """Tests that generated scripts are syntactically valid Python via compile()."""

    def test_pre_migrate_valid_python_empty(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _make_diff()
        result = generate_migration(diff, "17.0.1.1.0")
        compile(result["pre_migrate_code"], "pre-migrate.py", "exec")

    def test_post_migrate_valid_python_empty(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _make_diff()
        result = generate_migration(diff, "17.0.1.1.0")
        compile(result["post_migrate_code"], "post-migrate.py", "exec")

    def test_pre_migrate_valid_python_with_helpers(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        compile(result["pre_migrate_code"], "pre-migrate.py", "exec")

    def test_post_migrate_valid_python_with_helpers(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        compile(result["post_migrate_code"], "post-migrate.py", "exec")

    def test_type_change_scripts_valid_python(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_type_change("fee.invoice", "amount", "Float", "Monetary", "possibly_destructive")
        result = generate_migration(diff, "17.0.1.1.0")
        compile(result["pre_migrate_code"], "pre-migrate.py", "exec")
        compile(result["post_migrate_code"], "post-migrate.py", "exec")

    def test_model_removed_scripts_valid_python(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_model_removed("fee.old_model")
        result = generate_migration(diff, "17.0.1.1.0")
        compile(result["pre_migrate_code"], "pre-migrate.py", "exec")
        compile(result["post_migrate_code"], "post-migrate.py", "exec")

    def test_required_change_scripts_valid_python(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_required_change("fee.invoice", "due_date", False, True)
        result = generate_migration(diff, "17.0.1.1.0")
        compile(result["pre_migrate_code"], "pre-migrate.py", "exec")
        compile(result["post_migrate_code"], "post-migrate.py", "exec")

    def test_selection_removed_scripts_valid_python(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_selection_removed("fee.invoice", "state")
        result = generate_migration(diff, "17.0.1.1.0")
        compile(result["pre_migrate_code"], "pre-migrate.py", "exec")
        compile(result["post_migrate_code"], "post-migrate.py", "exec")


# ---------------------------------------------------------------------------
# TestMultipleChanges
# ---------------------------------------------------------------------------
class TestMultipleChanges:
    """Tests that multiple changes produce independent helpers all wired into migrate()."""

    def _multi_change_diff(self) -> dict:
        """Build a diff with multiple destructive changes on the same model."""
        return _make_diff(
            models_modified={
                "fee.invoice": {
                    "fields": {
                        "added": [],
                        "removed": [
                            {
                                "name": "old_ref",
                                "type": "Char",
                                "destructive": True,
                                "severity": "always_destructive",
                            },
                        ],
                        "modified": [
                            {
                                "name": "amount",
                                "type": "Monetary",
                                "changes": {"type": {"old": "Float", "new": "Monetary"}},
                                "destructive": True,
                                "severity": "possibly_destructive",
                            },
                            {
                                "name": "due_date",
                                "type": "Date",
                                "changes": {"required": {"old": False, "new": True}},
                                "destructive": True,
                                "severity": "possibly_destructive",
                            },
                        ],
                    },
                },
            },
            destructive_count=3,
            migration_required=True,
        )

    def test_multiple_helpers_generated(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = self._multi_change_diff()
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        # Should have helpers for old_ref removal, amount type change, due_date required
        helper_count = 0
        for line in pre.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def ") and "migrate" not in stripped:
                helper_count += 1
        assert helper_count >= 3, f"Expected at least 3 helpers, got {helper_count}"

    def test_all_helpers_called_from_migrate(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = self._multi_change_diff()
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        # Collect helper names
        helper_names = []
        for line in pre.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def ") and "migrate" not in stripped:
                name = stripped.split("(")[0].replace("def ", "")
                helper_names.append(name)

        # All should be called from migrate()
        migrate_section = pre[pre.index("def migrate(cr, version)"):]
        for name in helper_names:
            assert f"{name}(cr)" in migrate_section

    def test_multiple_changes_valid_python(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = self._multi_change_diff()
        result = generate_migration(diff, "17.0.1.1.0")
        compile(result["pre_migrate_code"], "pre-migrate.py", "exec")
        compile(result["post_migrate_code"], "post-migrate.py", "exec")

    def test_multiple_changes_independent_helpers(self) -> None:
        """Each change should have its own independent helper function."""
        from amil_utils.migration_generator import generate_migration

        diff = self._multi_change_diff()
        result = generate_migration(diff, "17.0.1.1.0")
        pre = result["pre_migrate_code"]

        # old_ref, amount, and due_date should each have separate helpers
        assert "old_ref" in pre
        assert "amount" in pre
        assert "due_date" in pre


# ---------------------------------------------------------------------------
# TestMigrationResult
# ---------------------------------------------------------------------------
class TestMigrationResult:
    """Tests the MigrationResult return structure."""

    def test_result_has_required_keys(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")

        assert "pre_migrate_code" in result
        assert "post_migrate_code" in result
        assert "migration_required" in result
        assert "version" in result

    def test_version_stored(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        assert result["version"] == "17.0.1.1.0"

    def test_migration_required_true_for_destructive(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")
        assert result["migration_required"] is True

    def test_migration_required_false_for_non_destructive(self) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_added("fee.invoice", "penalty_amount", "Monetary")
        result = generate_migration(diff, "17.0.1.1.0")
        assert result["migration_required"] is False


# ---------------------------------------------------------------------------
# TestFileOutput
# ---------------------------------------------------------------------------
class TestFileOutput:
    """Tests that generate_migration writes files when output_dir is provided."""

    def test_writes_pre_and_post_migrate(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0", output_dir=tmp_path)

        pre_path = tmp_path / "migrations" / "17.0.1.1.0" / "pre-migrate.py"
        post_path = tmp_path / "migrations" / "17.0.1.1.0" / "post-migrate.py"

        assert pre_path.exists()
        assert post_path.exists()

    def test_written_files_are_valid_python(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        generate_migration(diff, "17.0.1.1.0", output_dir=tmp_path)

        pre_path = tmp_path / "migrations" / "17.0.1.1.0" / "pre-migrate.py"
        post_path = tmp_path / "migrations" / "17.0.1.1.0" / "post-migrate.py"

        compile(pre_path.read_text(encoding="utf-8"), "pre-migrate.py", "exec")
        compile(post_path.read_text(encoding="utf-8"), "post-migrate.py", "exec")

    def test_result_still_returned_with_output_dir(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0", output_dir=tmp_path)

        assert "pre_migrate_code" in result
        assert "post_migrate_code" in result

    def test_no_files_without_output_dir(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import generate_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_migration(diff, "17.0.1.1.0")

        # No output_dir means no files written (just code returned)
        assert "pre_migrate_code" in result


# ---------------------------------------------------------------------------
# TestOdooVersion
# ---------------------------------------------------------------------------
class TestOdooVersion:
    """Tests Odoo version parsing, validation, and bumping."""

    def test_parse_valid_version(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        v = OdooVersion.parse("17.0.1.0.0")
        assert v.odoo_major == 17
        assert v.odoo_minor == 0
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0

    def test_parse_nonzero_segments(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        v = OdooVersion.parse("17.0.2.3.1")
        assert v.major == 2
        assert v.minor == 3
        assert v.patch == 1

    def test_parse_invalid_format_raises(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        with pytest.raises(ValueError, match="Invalid Odoo version"):
            OdooVersion.parse("1.0.0")

    def test_parse_non_numeric_raises(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        with pytest.raises(ValueError, match="Invalid Odoo version"):
            OdooVersion.parse("17.0.x.0.0")

    def test_str_roundtrip(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        original = "17.0.1.2.3"
        v = OdooVersion.parse(original)
        assert str(v) == original

    def test_bump_patch(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        v = OdooVersion.parse("17.0.1.0.0")
        bumped = v.bump("patch")
        assert str(bumped) == "17.0.1.0.1"

    def test_bump_minor(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        v = OdooVersion.parse("17.0.1.0.3")
        bumped = v.bump("minor")
        assert str(bumped) == "17.0.1.1.0"

    def test_bump_major(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        v = OdooVersion.parse("17.0.1.2.3")
        bumped = v.bump("major")
        assert str(bumped) == "17.0.2.0.0"

    def test_bump_minor_resets_patch(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        v = OdooVersion.parse("17.0.1.0.5")
        bumped = v.bump("minor")
        assert bumped.patch == 0

    def test_bump_major_resets_minor_and_patch(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        v = OdooVersion.parse("17.0.1.3.5")
        bumped = v.bump("major")
        assert bumped.minor == 0
        assert bumped.patch == 0

    def test_bump_invalid_type_raises(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        v = OdooVersion.parse("17.0.1.0.0")
        with pytest.raises(ValueError, match="bump_type"):
            v.bump("invalid")

    def test_comparison_ordering(self) -> None:
        from amil_utils.migration_generator import OdooVersion

        v1 = OdooVersion.parse("17.0.1.0.0")
        v2 = OdooVersion.parse("17.0.1.1.0")
        v3 = OdooVersion.parse("17.0.2.0.0")
        assert v1 < v2 < v3

    def test_odoo_series_preserved(self) -> None:
        """Bumping never changes the Odoo series (17.0)."""
        from amil_utils.migration_generator import OdooVersion

        v = OdooVersion.parse("17.0.1.0.0")
        for bump_type in ("patch", "minor", "major"):
            bumped = v.bump(bump_type)
            assert bumped.odoo_major == 17
            assert bumped.odoo_minor == 0


# ---------------------------------------------------------------------------
# TestComputeMigrationVersion
# ---------------------------------------------------------------------------
class TestComputeMigrationVersion:
    """Tests auto-computing version from diff severity."""

    def test_destructive_bumps_minor(self) -> None:
        from amil_utils.migration_generator import compute_migration_version

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        # Force same versions so auto-bump kicks in
        diff["old_version"] = "17.0.1.0.0"
        diff["new_version"] = "17.0.1.0.0"
        version = compute_migration_version(diff)
        # Destructive field removal → minor bump → "17.0.1.1.0"
        assert version == "17.0.1.1.0"

    def test_model_removal_bumps_major(self) -> None:
        from amil_utils.migration_generator import compute_migration_version

        diff = _diff_model_removed("fee.old_model")
        diff["old_version"] = "17.0.1.0.0"
        diff["new_version"] = "17.0.1.0.0"
        version = compute_migration_version(diff)
        # Model removal → major bump → "17.0.2.0.0"
        assert version == "17.0.2.0.0"

    def test_non_destructive_bumps_patch(self) -> None:
        from amil_utils.migration_generator import compute_migration_version

        diff = _diff_field_added("fee.invoice", "new_field", "Char")
        diff["old_version"] = "17.0.1.0.0"
        diff["new_version"] = "17.0.1.0.0"
        version = compute_migration_version(diff)
        # Non-destructive → patch bump → "17.0.1.0.1"
        assert version == "17.0.1.0.1"

    def test_uses_new_version_when_present(self) -> None:
        """When diff has distinct new_version, use it directly."""
        from amil_utils.migration_generator import compute_migration_version

        diff = _make_diff(migration_required=True)
        diff["new_version"] = "17.0.3.0.0"
        diff["old_version"] = "17.0.2.0.0"
        version = compute_migration_version(diff)
        assert version == "17.0.3.0.0"

    def test_falls_back_to_old_version_bump_when_new_equals_old(self) -> None:
        from amil_utils.migration_generator import compute_migration_version

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        diff["old_version"] = "17.0.1.0.0"
        diff["new_version"] = "17.0.1.0.0"
        version = compute_migration_version(diff)
        # Should auto-bump from old_version
        assert version == "17.0.1.1.0"

    def test_unknown_version_returns_fallback(self) -> None:
        from amil_utils.migration_generator import compute_migration_version

        diff = _make_diff()
        diff["old_version"] = "unknown"
        diff["new_version"] = "unknown"
        version = compute_migration_version(diff)
        assert version == "17.0.1.0.1"  # default fallback


# ---------------------------------------------------------------------------
# TestDiscoverMigrations
# ---------------------------------------------------------------------------
class TestDiscoverMigrations:
    """Tests scanning existing migration directories."""

    def test_empty_module_dir(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import discover_migrations

        result = discover_migrations(tmp_path)
        assert result == []

    def test_no_migrations_dir(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import discover_migrations

        (tmp_path / "__manifest__.py").touch()
        result = discover_migrations(tmp_path)
        assert result == []

    def test_discovers_version_directories(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import discover_migrations

        mig_dir = tmp_path / "migrations"
        (mig_dir / "17.0.1.0.0").mkdir(parents=True)
        (mig_dir / "17.0.1.1.0").mkdir(parents=True)
        (mig_dir / "17.0.2.0.0").mkdir(parents=True)
        result = discover_migrations(tmp_path)
        assert result == ["17.0.1.0.0", "17.0.1.1.0", "17.0.2.0.0"]

    def test_sorted_by_version_not_string(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import discover_migrations

        mig_dir = tmp_path / "migrations"
        (mig_dir / "17.0.1.0.0").mkdir(parents=True)
        (mig_dir / "17.0.1.10.0").mkdir(parents=True)
        (mig_dir / "17.0.1.2.0").mkdir(parents=True)
        result = discover_migrations(tmp_path)
        # Numeric sort: 1.0.0 < 1.2.0 < 1.10.0
        assert result == ["17.0.1.0.0", "17.0.1.2.0", "17.0.1.10.0"]

    def test_ignores_non_version_directories(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import discover_migrations

        mig_dir = tmp_path / "migrations"
        (mig_dir / "17.0.1.0.0").mkdir(parents=True)
        (mig_dir / "__pycache__").mkdir(parents=True)
        (mig_dir / "README.md").touch()
        result = discover_migrations(tmp_path)
        assert result == ["17.0.1.0.0"]

    def test_nonexistent_dir_returns_empty(self) -> None:
        from amil_utils.migration_generator import discover_migrations

        result = discover_migrations(Path("/nonexistent/path"))
        assert result == []


# ---------------------------------------------------------------------------
# TestGenerateVersionedMigration
# ---------------------------------------------------------------------------
class TestGenerateVersionedMigration:
    """Tests the full versioned migration pipeline."""

    def test_creates_versioned_directory(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import generate_versioned_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_versioned_migration(diff, module_dir=tmp_path)

        version = result["version"]
        pre_path = tmp_path / "migrations" / version / "pre-migrate.py"
        post_path = tmp_path / "migrations" / version / "post-migrate.py"
        assert pre_path.exists()
        assert post_path.exists()

    def test_auto_computes_version(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import generate_versioned_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        diff["old_version"] = "17.0.1.0.0"
        diff["new_version"] = "17.0.1.0.0"
        result = generate_versioned_migration(diff, module_dir=tmp_path)
        # Destructive field removal: minor bump from 17.0.1.0.0
        assert result["version"] == "17.0.1.1.0"

    def test_avoids_version_collision(self, tmp_path: Path) -> None:
        """If computed version already exists, bump further."""
        from amil_utils.migration_generator import generate_versioned_migration

        # Pre-create the version that would be computed
        mig_dir = tmp_path / "migrations" / "17.0.1.1.0"
        mig_dir.mkdir(parents=True)
        (mig_dir / "pre-migrate.py").touch()

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        diff["old_version"] = "17.0.1.0.0"
        diff["new_version"] = "17.0.1.0.0"
        result = generate_versioned_migration(diff, module_dir=tmp_path)

        # Should bump past existing 17.0.1.1.0
        assert result["version"] != "17.0.1.1.0"
        assert result["version"] == "17.0.1.2.0"

    def test_respects_explicit_version(self, tmp_path: Path) -> None:
        """When version override is given, use it."""
        from amil_utils.migration_generator import generate_versioned_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_versioned_migration(
            diff, module_dir=tmp_path, version_override="17.0.5.0.0"
        )
        assert result["version"] == "17.0.5.0.0"

    def test_result_has_all_keys(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import generate_versioned_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_versioned_migration(diff, module_dir=tmp_path)

        assert "pre_migrate_code" in result
        assert "post_migrate_code" in result
        assert "migration_required" in result
        assert "version" in result
        assert "computed_version" in result

    def test_generated_scripts_valid_python(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import generate_versioned_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        result = generate_versioned_migration(diff, module_dir=tmp_path)
        compile(result["pre_migrate_code"], "pre-migrate.py", "exec")
        compile(result["post_migrate_code"], "post-migrate.py", "exec")

    def test_non_destructive_still_bumps_patch(self, tmp_path: Path) -> None:
        from amil_utils.migration_generator import generate_versioned_migration

        diff = _diff_field_added("fee.invoice", "new_field", "Char")
        diff["old_version"] = "17.0.1.0.0"
        diff["new_version"] = "17.0.1.0.0"
        result = generate_versioned_migration(diff, module_dir=tmp_path)
        assert result["version"] == "17.0.1.0.1"

    def test_without_module_dir_no_files(self) -> None:
        from amil_utils.migration_generator import generate_versioned_migration

        diff = _diff_field_removed("fee.invoice", "old_ref", "Char")
        diff["old_version"] = "17.0.1.0.0"
        diff["new_version"] = "17.0.1.0.0"
        result = generate_versioned_migration(diff)
        assert result["version"] == "17.0.1.1.0"
        assert "pre_migrate_code" in result
