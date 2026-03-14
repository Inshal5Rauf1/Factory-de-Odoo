"""Tests for auto_fix.py -- pylint and Docker auto-fix logic.

Tests cover:
- Pylint auto-fix for 5 fixable codes (W8113, W8111, C8116, W8150, C8107)
- Non-fixable code returns is_fixed=False
- Batch fix_pylint_violations returns (fixed_count, remaining)
- run_pylint_fix_loop enforces max 2 cycles
- Docker auto-fix pattern identification for 4 fixable patterns
- Escalation format grouping by file with line + suggestion
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from amil_utils.auto_fix import (
    DEFAULT_MAX_FIX_ITERATIONS,
    FIXABLE_DOCKER_PATTERNS,
    FIXABLE_PYLINT_CODES,
    _DOCKER_PATTERN_KEYWORDS,
    fix_missing_mail_thread,
    fix_pylint_violation,
    fix_pylint_violations,
    fix_unused_imports,
    format_escalation,
    identify_docker_fix,
    is_fixable_pylint,
    run_pylint_fix_loop,
)
from amil_utils.validation.types import Result, Violation


# ---------------------------------------------------------------------------
# Constants validation
# ---------------------------------------------------------------------------


class TestConstants:
    def test_fixable_pylint_codes_contains_exactly_six(self):
        assert len(FIXABLE_PYLINT_CODES) == 6
        assert FIXABLE_PYLINT_CODES == frozenset({"W8113", "W8111", "C8116", "W8150", "C8107", "W8161"})

    def test_fixable_docker_patterns_contains_exactly_five(self):
        assert len(FIXABLE_DOCKER_PATTERNS) == 5
        assert FIXABLE_DOCKER_PATTERNS == frozenset({
            "xml_parse_error", "missing_acl", "missing_import",
            "manifest_load_order", "missing_mail_thread",
        })

    def test_default_max_fix_iterations_is_five(self):
        assert DEFAULT_MAX_FIX_ITERATIONS == 5


# ---------------------------------------------------------------------------
# is_fixable_pylint
# ---------------------------------------------------------------------------


class TestIsFixablePylint:
    def test_fixable_code_w8113(self):
        v = Violation(file="models/m.py", line=10, column=0, rule_code="W8113",
                      symbol="redundant-string", severity="warning", message="redundant string=")
        assert is_fixable_pylint(v) is True

    def test_non_fixable_code(self):
        v = Violation(file="models/m.py", line=10, column=0, rule_code="E8103",
                      symbol="missing-description", severity="error", message="missing _description")
        assert is_fixable_pylint(v) is False


# ---------------------------------------------------------------------------
# fix_pylint_violation -- individual code fixes
# ---------------------------------------------------------------------------


class TestFixPylintViolationW8113:
    """W8113: redundant string= parameter on field."""

    def test_removes_string_param_double_quotes(self):
        src = textwrap.dedent('''\
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                name = fields.Char(string="Name", required=True)
        ''')
        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            model_file = mod / "models" / "test_model.py"
            model_file.parent.mkdir(parents=True)
            model_file.write_text(src, encoding="utf-8")

            v = Violation(file="models/test_model.py", line=5, column=0,
                          rule_code="W8113", symbol="redundant-string",
                          severity="warning", message='Redundant string= on field "name"')
            result = fix_pylint_violation(v, mod)
            assert result is True

            content = model_file.read_text(encoding="utf-8")
            assert 'string="Name"' not in content
            assert "required=True" in content

    def test_removes_string_param_single_quotes(self):
        src = textwrap.dedent("""\
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                name = fields.Char(string='Name', required=True)
        """)
        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            model_file = mod / "models" / "test_model.py"
            model_file.parent.mkdir(parents=True)
            model_file.write_text(src, encoding="utf-8")

            v = Violation(file="models/test_model.py", line=5, column=0,
                          rule_code="W8113", symbol="redundant-string",
                          severity="warning", message='Redundant string= on field "name"')
            result = fix_pylint_violation(v, mod)
            assert result is True

            content = model_file.read_text(encoding="utf-8")
            assert "string='Name'" not in content


class TestFixPylintViolationW8111:
    """W8111: renamed field parameter."""

    def test_renames_track_visibility_to_tracking(self):
        src = textwrap.dedent('''\
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                state = fields.Selection(track_visibility="onchange")
        ''')
        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            model_file = mod / "models" / "test_model.py"
            model_file.parent.mkdir(parents=True)
            model_file.write_text(src, encoding="utf-8")

            v = Violation(file="models/test_model.py", line=5, column=0,
                          rule_code="W8111", symbol="renamed-field-parameter",
                          severity="warning",
                          message='"track_visibility" has been renamed to "tracking"')
            result = fix_pylint_violation(v, mod)
            assert result is True

            content = model_file.read_text(encoding="utf-8")
            assert "track_visibility" not in content
            assert "tracking" in content


class TestFixPylintViolationC8116:
    """C8116: superfluous manifest key."""

    def test_removes_superfluous_key(self):
        src = textwrap.dedent("""\
            {
                "name": "Test Module",
                "version": "17.0.1.0.0",
                "description": "A test module",
                "depends": ["base"],
            }
        """)
        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            manifest = mod / "__manifest__.py"
            manifest.write_text(src, encoding="utf-8")

            v = Violation(file="__manifest__.py", line=4, column=0,
                          rule_code="C8116", symbol="manifest-deprecated-key",
                          severity="convention",
                          message='Deprecated key "description" in manifest file')
            result = fix_pylint_violation(v, mod)
            assert result is True

            content = manifest.read_text(encoding="utf-8")
            assert '"description"' not in content
            assert '"name"' in content
            assert '"depends"' in content


class TestFixPylintViolationW8150:
    """W8150: absolute import should be relative."""

    def test_converts_absolute_to_relative_import(self):
        src = textwrap.dedent("""\
            from odoo.addons.my_module import models
        """)
        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            py_file = mod / "models" / "test_model.py"
            py_file.parent.mkdir(parents=True)
            py_file.write_text(src, encoding="utf-8")

            v = Violation(file="models/test_model.py", line=1, column=0,
                          rule_code="W8150", symbol="odoo-addons-relative-import",
                          severity="warning",
                          message="Use relative import `from . import models`")
            result = fix_pylint_violation(v, mod)
            assert result is True

            content = py_file.read_text(encoding="utf-8")
            assert "from odoo.addons.my_module" not in content
            assert "from ." in content


class TestFixPylintViolationC8107:
    """C8107: missing required manifest key."""

    def test_adds_missing_license_key(self):
        src = textwrap.dedent("""\
            {
                "name": "Test Module",
                "version": "17.0.1.0.0",
                "depends": ["base"],
            }
        """)
        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            manifest = mod / "__manifest__.py"
            manifest.write_text(src, encoding="utf-8")

            v = Violation(file="__manifest__.py", line=1, column=0,
                          rule_code="C8107", symbol="manifest-required-key",
                          severity="convention",
                          message='Missing required key "license" in manifest file')
            result = fix_pylint_violation(v, mod)
            assert result is True

            content = manifest.read_text(encoding="utf-8")
            assert '"license"' in content


class TestFixPylintViolationNonFixable:
    """Non-fixable code returns False."""

    def test_non_fixable_returns_false(self):
        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            model_file = mod / "models" / "test_model.py"
            model_file.parent.mkdir(parents=True)
            model_file.write_text("# some code\n", encoding="utf-8")

            v = Violation(file="models/test_model.py", line=1, column=0,
                          rule_code="E8103", symbol="missing-description",
                          severity="error", message="Model _description missing")
            result = fix_pylint_violation(v, mod)
            assert result is False


# ---------------------------------------------------------------------------
# fix_pylint_violations -- batch processing
# ---------------------------------------------------------------------------


class TestFixPylintViolations:
    def test_processes_list_returns_counts(self):
        src = textwrap.dedent('''\
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                name = fields.Char(string="Name", required=True)
        ''')
        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            model_file = mod / "models" / "test_model.py"
            model_file.parent.mkdir(parents=True)
            model_file.write_text(src, encoding="utf-8")

            violations = (
                Violation(file="models/test_model.py", line=5, column=0,
                          rule_code="W8113", symbol="redundant-string",
                          severity="warning", message='Redundant string= on field "name"'),
                Violation(file="models/test_model.py", line=10, column=0,
                          rule_code="E8103", symbol="missing-description",
                          severity="error", message="Model _description missing"),
            )
            fixed_count, remaining = fix_pylint_violations(violations, mod)
            assert fixed_count == 1
            assert len(remaining) == 1
            assert remaining[0].rule_code == "E8103"


# ---------------------------------------------------------------------------
# run_pylint_fix_loop -- max 2 cycles
# ---------------------------------------------------------------------------


class TestRunPylintFixLoop:
    def test_max_default_cycles(self):
        """Should run at most DEFAULT_MAX_FIX_ITERATIONS (5) cycles."""
        cycle_count = 0
        fixable_v = Violation(
            file="models/m.py", line=5, column=0,
            rule_code="W8113", symbol="redundant-string",
            severity="warning", message='Redundant string= on field "name"',
        )
        non_fixable_v = Violation(
            file="models/m.py", line=10, column=0,
            rule_code="E8103", symbol="missing-description",
            severity="error", message="Model _description missing",
        )

        def mock_run_pylint(*args, **kwargs):
            nonlocal cycle_count
            cycle_count += 1
            # Re-create the file each cycle so the fix always has work to do
            model_file.write_text(
                'from odoo import fields, models\n\n'
                'class M(models.Model):\n'
                '    _name = "m"\n'
                '    name = fields.Char(string="Name")\n',
                encoding="utf-8",
            )
            # Always return both a fixable and non-fixable violation
            return Result.ok((fixable_v, non_fixable_v))

        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            model_file = mod / "models" / "m.py"
            model_file.parent.mkdir(parents=True)
            model_file.write_text(
                'from odoo import fields, models\n\n'
                'class M(models.Model):\n'
                '    _name = "m"\n'
                '    name = fields.Char(string="Name")\n',
                encoding="utf-8",
            )

            with patch("amil_utils.auto_fix.run_pylint_odoo", side_effect=mock_run_pylint):
                result = run_pylint_fix_loop(mod)

            assert result.success
            total_fixed, remaining = result.data
            assert cycle_count == 5
            assert total_fixed >= 1
            assert any(v.rule_code == "E8103" for v in remaining)

    def test_skips_cycle_2_when_no_fixable(self):
        """If cycle 1 produces 0 fixable violations, skip cycle 2."""
        cycle_count = 0
        non_fixable_v = Violation(
            file="models/m.py", line=10, column=0,
            rule_code="E8103", symbol="missing-description",
            severity="error", message="Model _description missing",
        )

        def mock_run_pylint(*args, **kwargs):
            nonlocal cycle_count
            cycle_count += 1
            return Result.ok((non_fixable_v,))

        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            with patch("amil_utils.auto_fix.run_pylint_odoo", side_effect=mock_run_pylint):
                result = run_pylint_fix_loop(mod)

            assert result.success
            total_fixed, remaining = result.data
            assert cycle_count == 1
            assert total_fixed == 0
            assert len(remaining) == 1


# ---------------------------------------------------------------------------
# identify_docker_fix
# ---------------------------------------------------------------------------


class TestIdentifyDockerFix:
    def test_xml_parse_error_identified(self):
        diagnosis = "[ERROR] An XML file has syntax errors. This can be a mismatched tag"
        result = identify_docker_fix(diagnosis)
        assert result == "xml_parse_error"

    def test_missing_acl_identified(self):
        diagnosis = "[ERROR] No access control list (ACL) entry exists for a model. ir.model.access"
        result = identify_docker_fix(diagnosis)
        assert result == "missing_acl"

    def test_missing_import_identified(self):
        diagnosis = "[ERROR] A Python module or Odoo addon could not be imported. No module named"
        result = identify_docker_fix(diagnosis)
        assert result == "missing_import"

    def test_manifest_load_order_identified(self):
        diagnosis = "[ERROR] A menu item or button references an action (ir.actions.act_window) that does not exist"
        result = identify_docker_fix(diagnosis)
        assert result == "manifest_load_order"

    def test_unknown_error_returns_none(self):
        diagnosis = "[ERROR] Some completely unknown error that does not match any pattern"
        result = identify_docker_fix(diagnosis)
        assert result is None


# ---------------------------------------------------------------------------
# format_escalation
# ---------------------------------------------------------------------------


class TestFormatEscalation:
    def test_groups_by_file_with_line_and_suggestion(self):
        violations = (
            Violation(file="models/sale_order.py", line=42, column=0,
                      rule_code="E8103", symbol="missing-description",
                      severity="error", message="Model _description missing",
                      suggestion='Add `_description = "Sales Order"` to the model class'),
            Violation(file="models/sale_order.py", line=10, column=0,
                      rule_code="C8101", symbol="manifest-missing-key",
                      severity="convention", message="Missing key in manifest"),
            Violation(file="__manifest__.py", line=1, column=0,
                      rule_code="C8101", symbol="manifest-missing-key",
                      severity="convention", message='Missing key "author" in manifest',
                      suggestion='Add `"author": "Your Name"` to __manifest__.py'),
        )
        result = format_escalation(violations)
        assert "Auto-fix exhausted" in result
        assert "models/sale_order.py" in result
        assert "__manifest__.py" in result
        assert ":42" in result
        assert ":10" in result
        assert "E8103" in result

    def test_empty_violations_returns_no_issues(self):
        result = format_escalation(())
        assert result == "No remaining issues."


# ---------------------------------------------------------------------------
# fix_missing_mail_thread -- AFIX-01
# ---------------------------------------------------------------------------


class TestFixMissingMailThread:
    """Detects chatter XML references and adds _inherit to model.py."""

    def _make_module(self, tmp_path: Path, model_content: str, xml_content: str) -> Path:
        """Helper: create a minimal module directory with models/ and views/."""
        module_dir = tmp_path / "test_module"
        (module_dir / "models").mkdir(parents=True)
        (module_dir / "views").mkdir(parents=True)
        (module_dir / "models" / "model.py").write_text(
            textwrap.dedent(model_content), encoding="utf-8"
        )
        (module_dir / "views" / "model_views.xml").write_text(
            textwrap.dedent(xml_content), encoding="utf-8"
        )
        return module_dir

    def test_adds_inherit_when_oe_chatter_present(self, tmp_path: Path):
        model_content = """\
            from odoo import fields, models

            class HrTraining(models.Model):
                _name = "hr.training"
                _description = "HR Training"

                name = fields.Char(string="Name", required=True)
        """
        xml_content = """\
            <odoo>
                <record id="view_hr_training_form" model="ir.ui.view">
                    <field name="arch" type="xml">
                        <form>
                            <sheet><group><field name="name"/></group></sheet>
                            <div class="oe_chatter">
                                <field name="message_follower_ids"/>
                                <field name="message_ids"/>
                            </div>
                        </form>
                    </field>
                </record>
            </odoo>
        """
        module_dir = self._make_module(tmp_path, model_content, xml_content)
        result = fix_missing_mail_thread(module_dir)
        assert result is True

        content = (module_dir / "models" / "model.py").read_text(encoding="utf-8")
        assert "_inherit = ['mail.thread', 'mail.activity.mixin']" in content

    def test_adds_inherit_when_chatter_tag_present(self, tmp_path: Path):
        model_content = """\
            from odoo import fields, models

            class HrTraining(models.Model):
                _name = "hr.training"
                _description = "HR Training"

                name = fields.Char(string="Name", required=True)
        """
        xml_content = """\
            <odoo>
                <record id="view_hr_training_form" model="ir.ui.view">
                    <field name="arch" type="xml">
                        <form>
                            <sheet><group><field name="name"/></group></sheet>
                            <chatter/>
                        </form>
                    </field>
                </record>
            </odoo>
        """
        module_dir = self._make_module(tmp_path, model_content, xml_content)
        result = fix_missing_mail_thread(module_dir)
        assert result is True

        content = (module_dir / "models" / "model.py").read_text(encoding="utf-8")
        assert "_inherit = ['mail.thread', 'mail.activity.mixin']" in content

    def test_adds_inherit_when_message_ids_present(self, tmp_path: Path):
        model_content = """\
            from odoo import fields, models

            class HrTraining(models.Model):
                _name = "hr.training"
                _description = "HR Training"

                name = fields.Char(string="Name", required=True)
        """
        xml_content = """\
            <odoo>
                <record id="view_hr_training_form" model="ir.ui.view">
                    <field name="arch" type="xml">
                        <form>
                            <sheet><group><field name="name"/></group></sheet>
                            <field name="message_ids"/>
                        </form>
                    </field>
                </record>
            </odoo>
        """
        module_dir = self._make_module(tmp_path, model_content, xml_content)
        result = fix_missing_mail_thread(module_dir)
        assert result is True

        content = (module_dir / "models" / "model.py").read_text(encoding="utf-8")
        assert "_inherit = ['mail.thread', 'mail.activity.mixin']" in content

    def test_no_change_when_inherit_already_present(self, tmp_path: Path):
        model_content = """\
            from odoo import fields, models

            class HrTraining(models.Model):
                _name = "hr.training"
                _inherit = ['mail.thread', 'mail.activity.mixin']
                _description = "HR Training"

                name = fields.Char(string="Name", required=True)
        """
        xml_content = """\
            <odoo>
                <record id="view_hr_training_form" model="ir.ui.view">
                    <field name="arch" type="xml">
                        <form>
                            <sheet><group><field name="name"/></group></sheet>
                            <div class="oe_chatter">
                                <field name="message_follower_ids"/>
                                <field name="message_ids"/>
                            </div>
                        </form>
                    </field>
                </record>
            </odoo>
        """
        module_dir = self._make_module(tmp_path, model_content, xml_content)
        result = fix_missing_mail_thread(module_dir)
        assert result is False

    def test_no_change_when_no_chatter_xml(self, tmp_path: Path):
        model_content = """\
            from odoo import fields, models

            class HrTraining(models.Model):
                _name = "hr.training"
                _description = "HR Training"

                name = fields.Char(string="Name", required=True)
        """
        xml_content = """\
            <odoo>
                <record id="view_hr_training_form" model="ir.ui.view">
                    <field name="arch" type="xml">
                        <form>
                            <sheet><group><field name="name"/></group></sheet>
                        </form>
                    </field>
                </record>
            </odoo>
        """
        module_dir = self._make_module(tmp_path, model_content, xml_content)
        result = fix_missing_mail_thread(module_dir)
        assert result is False

    def test_inherit_inserted_after_description(self, tmp_path: Path):
        model_content = """\
            from odoo import fields, models

            class HrTraining(models.Model):
                _name = "hr.training"
                _description = "HR Training"

                name = fields.Char(string="Name", required=True)
        """
        xml_content = """\
            <odoo>
                <record id="view_hr_training_form" model="ir.ui.view">
                    <field name="arch" type="xml">
                        <form>
                            <sheet><group><field name="name"/></group></sheet>
                            <div class="oe_chatter">
                                <field name="message_follower_ids"/>
                                <field name="message_ids"/>
                            </div>
                        </form>
                    </field>
                </record>
            </odoo>
        """
        module_dir = self._make_module(tmp_path, model_content, xml_content)
        fix_missing_mail_thread(module_dir)

        content = (module_dir / "models" / "model.py").read_text(encoding="utf-8")
        lines = content.split("\n")
        desc_idx = next(i for i, line in enumerate(lines) if "_description" in line)
        inherit_idx = next(i for i, line in enumerate(lines) if "_inherit" in line)
        assert inherit_idx == desc_idx + 1


# ---------------------------------------------------------------------------
# fix_unused_imports -- AFIX-02
# ---------------------------------------------------------------------------


class TestFixUnusedImports:
    """Detects and removes unused imports in generated Python files."""

    def test_removes_unused_validation_error(self, tmp_path: Path):
        src = textwrap.dedent("""\
            from odoo import fields, models
            from odoo.exceptions import ValidationError

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test Model"

                name = fields.Char(string="Name", required=True)
        """)
        py_file = tmp_path / "test_model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is True

        content = py_file.read_text(encoding="utf-8")
        assert "ValidationError" not in content

    def test_removes_unused_api(self, tmp_path: Path):
        src = textwrap.dedent("""\
            from odoo import api, fields, models

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test Model"

                name = fields.Char(string="Name", required=True)
        """)
        py_file = tmp_path / "test_model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is True

        content = py_file.read_text(encoding="utf-8")
        assert "api" not in content
        assert "from odoo import fields, models" in content

    def test_keeps_used_imports(self, tmp_path: Path):
        src = textwrap.dedent("""\
            from odoo import api, fields, models
            from odoo.exceptions import AccessError, ValidationError

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test Model"

                name = fields.Char(string="Name", required=True)

                @api.constrains("name")
                def _check_name(self):
                    for record in self:
                        if not record.name:
                            raise ValidationError("Name is required")
                        if not self.env.user.has_group("base.group_user"):
                            raise AccessError("Not allowed")
        """)
        py_file = tmp_path / "test_model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is False

    def test_removes_only_unused_from_multi_import(self, tmp_path: Path):
        src = textwrap.dedent("""\
            from odoo import fields, models
            from odoo.exceptions import AccessError, ValidationError

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test Model"

                name = fields.Char(string="Name", required=True)

                def check_access(self):
                    if not self.env.user.has_group("base.group_user"):
                        raise AccessError("Not allowed")
        """)
        py_file = tmp_path / "test_model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is True

        content = py_file.read_text(encoding="utf-8")
        assert "ValidationError" not in content
        assert "AccessError" in content

    def test_no_change_empty_file(self, tmp_path: Path):
        py_file = tmp_path / "empty.py"
        py_file.write_text("", encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is False


# ---------------------------------------------------------------------------
# Arbitrary unused import detection (full AST body scan)
# ---------------------------------------------------------------------------


class TestUnusedImportsArbitraryNames:
    """Full AST scan detects ANY unused import, not just whitelisted names."""

    def test_removes_arbitrary_unused_import(self, tmp_path: Path):
        """Import `fields` unused while `api` used -> fields removed, api kept."""
        src = textwrap.dedent("""\
            from odoo import fields, api

            class TestModel:
                @api.constrains("name")
                def _check(self):
                    pass
        """)
        py_file = tmp_path / "model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is True

        content = py_file.read_text(encoding="utf-8")
        assert "fields" not in content
        assert "api" in content

    def test_removes_unknown_unused_import(self, tmp_path: Path):
        """Import `Command` with no usage anywhere -> entire import line removed."""
        src = textwrap.dedent("""\
            from odoo import Command

            class TestModel:
                pass
        """)
        py_file = tmp_path / "model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is True

        content = py_file.read_text(encoding="utf-8")
        assert "Command" not in content
        assert "import" not in content

    def test_keeps_import_used_in_attribute_access(self, tmp_path: Path):
        """Import `fields` used as `fields.Char(...)` -> kept."""
        src = textwrap.dedent("""\
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                name = fields.Char(string="Name")
        """)
        py_file = tmp_path / "model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is False

    def test_removes_multiple_arbitrary_unused(self, tmp_path: Path):
        """Multiple unused from same import -> only used name kept."""
        src = textwrap.dedent("""\
            from odoo.exceptions import ValidationError, UserError, AccessError

            class TestModel:
                def check(self):
                    raise ValidationError("fail")
        """)
        py_file = tmp_path / "model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is True

        content = py_file.read_text(encoding="utf-8")
        assert "ValidationError" in content
        assert "UserError" not in content
        assert "AccessError" not in content


class TestUnusedImportsStarImport:
    """Star imports are never removed."""

    def test_preserves_star_import(self, tmp_path: Path):
        """from odoo import * is never removed even without explicit references."""
        src = textwrap.dedent("""\
            from odoo import *

            class TestModel:
                pass
        """)
        py_file = tmp_path / "model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is False

        content = py_file.read_text(encoding="utf-8")
        assert "from odoo import *" in content


class TestUnusedImportsAllExport:
    """Names in __all__ are treated as used."""

    def test_preserves_import_in_all(self, tmp_path: Path):
        """Import referenced only via __all__ -> kept."""
        src = textwrap.dedent("""\
            from odoo import api

            __all__ = ["api"]

            class TestModel:
                pass
        """)
        py_file = tmp_path / "model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is False

        content = py_file.read_text(encoding="utf-8")
        assert "from odoo import api" in content


class TestFormattingPreserved:
    """Comments and whitespace preserved after import removal."""

    def test_preserves_comments_between_imports(self, tmp_path: Path):
        """Comment lines between import blocks remain intact after removal."""
        src = textwrap.dedent("""\
            from odoo import fields, models
            # This is an important comment
            from odoo import Command

            class TestModel(models.Model):
                _name = "test.model"
                name = fields.Char(string="Name")
        """)
        py_file = tmp_path / "model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is True

        content = py_file.read_text(encoding="utf-8")
        assert "# This is an important comment" in content
        assert "Command" not in content

    def test_no_triple_blank_lines(self, tmp_path: Path):
        """After removing imports, no 3+ consecutive blank lines appear."""
        src = textwrap.dedent("""\
            from odoo import fields, models
            from odoo import Command

            class TestModel(models.Model):
                _name = "test.model"
                name = fields.Char(string="Name")
        """)
        py_file = tmp_path / "model.py"
        py_file.write_text(src, encoding="utf-8")

        result = fix_unused_imports(py_file)
        assert result is True

        content = py_file.read_text(encoding="utf-8")
        assert "\n\n\n" not in content


# ---------------------------------------------------------------------------
# Updated constants -- missing_mail_thread in Docker patterns
# ---------------------------------------------------------------------------


class TestUpdatedConstants:
    """Verify FIXABLE_DOCKER_PATTERNS updated to include missing_mail_thread."""

    def test_fixable_docker_patterns_contains_five(self):
        assert len(FIXABLE_DOCKER_PATTERNS) == 5
        assert "missing_mail_thread" in FIXABLE_DOCKER_PATTERNS

    def test_docker_pattern_keywords_has_mail_thread(self):
        assert "missing_mail_thread" in _DOCKER_PATTERN_KEYWORDS

    def test_identify_docker_fix_mail_thread(self):
        result = identify_docker_fix("missing mail.thread inheritance")
        assert result == "missing_mail_thread"

    def test_identify_docker_fix_oe_chatter(self):
        result = identify_docker_fix(
            "oe_chatter div found but model lacks mail.thread"
        )
        assert result == "missing_mail_thread"


# ---------------------------------------------------------------------------
# run_docker_fix_loop -- dispatches to fix functions
# ---------------------------------------------------------------------------


class TestRunDockerFixLoop:
    """Tests for run_docker_fix_loop dispatcher."""

    def test_mail_thread_error_calls_fix_and_returns_true(self, tmp_path: Path):
        """run_docker_fix_loop with mail.thread error text dispatches fix_missing_mail_thread."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        (module_dir / "models").mkdir(parents=True)
        (module_dir / "views").mkdir(parents=True)
        (module_dir / "models" / "model.py").write_text(textwrap.dedent("""\
            from odoo import fields, models

            class HrTraining(models.Model):
                _name = "hr.training"
                _description = "HR Training"

                name = fields.Char(string="Name", required=True)
        """), encoding="utf-8")
        (module_dir / "views" / "model_views.xml").write_text(textwrap.dedent("""\
            <odoo>
                <record id="view_form" model="ir.ui.view">
                    <field name="arch" type="xml">
                        <form>
                            <sheet><group><field name="name"/></group></sheet>
                            <div class="oe_chatter">
                                <field name="message_follower_ids"/>
                            </div>
                        </form>
                    </field>
                </record>
            </odoo>
        """), encoding="utf-8")

        error_text = "Error: model hr.training uses oe_chatter but lacks mail.thread inheritance"
        result = run_docker_fix_loop(module_dir, error_text)
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is True

        content = (module_dir / "models" / "model.py").read_text(encoding="utf-8")
        assert "mail.thread" in content

    def test_unused_import_error_returns_true(self, tmp_path: Path):
        """run_docker_fix_loop with unused import keywords dispatches fix."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        (module_dir / "models").mkdir(parents=True)
        model_file = module_dir / "models" / "model.py"
        model_file.write_text(textwrap.dedent("""\
            from odoo import api, fields, models
            from odoo.exceptions import ValidationError

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test"

                name = fields.Char(required=True)
        """), encoding="utf-8")

        error_text = "W0611: Unused import ValidationError (unused-import)"
        result = run_docker_fix_loop(module_dir, error_text)
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is True

    def test_unrecognized_error_returns_false(self, tmp_path: Path):
        """run_docker_fix_loop with unrecognized error returns False."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        module_dir.mkdir(parents=True)

        error_text = "Something completely unknown with no matching pattern"
        result = run_docker_fix_loop(module_dir, error_text)
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is False

    def test_empty_error_returns_false(self, tmp_path: Path):
        """run_docker_fix_loop with empty error text returns False."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        module_dir.mkdir(parents=True)

        result = run_docker_fix_loop(module_dir, "")
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is False


# ---------------------------------------------------------------------------
# run_pylint_fix_loop -- fix_unused_imports for W0611
# ---------------------------------------------------------------------------


class TestRunDockerFixLoopImport:
    """Verify run_docker_fix_loop is importable and callable."""

    def test_import_run_docker_fix_loop(self):
        from amil_utils.auto_fix import run_docker_fix_loop

        assert callable(run_docker_fix_loop)


class TestPylintFixLoopUnusedImports:
    """run_pylint_fix_loop calls fix_unused_imports when W0611 detected."""

    def test_pylint_loop_calls_fix_unused_imports_for_w0611(self):
        """When pylint reports W0611, fix_unused_imports should be invoked on that file."""
        w0611_v = Violation(
            file="models/m.py", line=2, column=0,
            rule_code="W0611", symbol="unused-import",
            severity="warning", message="Unused import ValidationError",
        )

        def mock_run_pylint(*args, **kwargs):
            return Result.ok((w0611_v,))

        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            model_file = mod / "models" / "m.py"
            model_file.parent.mkdir(parents=True)
            model_file.write_text(textwrap.dedent("""\
                from odoo import fields, models
                from odoo.exceptions import ValidationError

                class M(models.Model):
                    _name = "m"
                    _description = "M"

                    name = fields.Char(required=True)
            """), encoding="utf-8")

            with patch("amil_utils.auto_fix.run_pylint_odoo", side_effect=mock_run_pylint):
                result = run_pylint_fix_loop(mod)
                total_fixed, remaining = result.data

            content = model_file.read_text(encoding="utf-8")
            assert "ValidationError" not in content


# ---------------------------------------------------------------------------
# fix_xml_parse_error -- Docker fix for mismatched XML tags
# ---------------------------------------------------------------------------


class TestFixXmlParseError:
    """fix_xml_parse_error detects and fixes mismatched closing tags in XML."""

    def _make_module(self, tmp_path: Path, xml_content: str) -> Path:
        """Helper: create a module with views/model_views.xml."""
        module_dir = tmp_path / "test_module"
        (module_dir / "views").mkdir(parents=True)
        (module_dir / "views" / "model_views.xml").write_text(
            textwrap.dedent(xml_content), encoding="utf-8"
        )
        return module_dir

    def test_fixes_mismatched_closing_tag(self, tmp_path: Path):
        """Mismatched closing tag <fom> instead of <form> is detected and fixed."""
        from amil_utils.auto_fix import fix_xml_parse_error

        xml = """\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="view_form" model="ir.ui.view">
                    <field name="arch" type="xml">
                        <form>
                            <sheet><group><field name="name"/></group></sheet>
                        </fom>
                    </field>
                </record>
            </odoo>
        """
        module_dir = self._make_module(tmp_path, xml)
        error_output = (
            'lxml.etree.XMLSyntaxError: Opening and ending tag mismatch: '
            'form line 5 and fom, line 7, column 27 '
            f'(views/model_views.xml, line 7)'
        )
        result = fix_xml_parse_error(module_dir, error_output)
        assert result is True

        content = (module_dir / "views" / "model_views.xml").read_text(encoding="utf-8")
        assert "</fom>" not in content
        assert "</form>" in content

    def test_well_formed_xml_returns_false(self, tmp_path: Path):
        """Well-formed XML returns False (no change needed)."""
        from amil_utils.auto_fix import fix_xml_parse_error

        xml = """\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="view_form" model="ir.ui.view">
                    <field name="arch" type="xml">
                        <form>
                            <sheet><group><field name="name"/></group></sheet>
                        </form>
                    </field>
                </record>
            </odoo>
        """
        module_dir = self._make_module(tmp_path, xml)
        error_output = "Some error referencing views/model_views.xml"
        result = fix_xml_parse_error(module_dir, error_output)
        assert result is False


# ---------------------------------------------------------------------------
# fix_missing_acl -- Docker fix for missing ir.model.access.csv
# ---------------------------------------------------------------------------


class TestFixMissingAcl:
    """fix_missing_acl creates security/ir.model.access.csv for missing models."""

    def _make_module(self, tmp_path: Path, *, has_csv: bool = False, csv_content: str = "") -> Path:
        """Helper: create a module with models/ and optionally security/."""
        module_dir = tmp_path / "test_module"
        (module_dir / "models").mkdir(parents=True)
        (module_dir / "models" / "__init__.py").write_text(
            "from . import my_model\n", encoding="utf-8"
        )
        (module_dir / "models" / "my_model.py").write_text(textwrap.dedent("""\
            from odoo import fields, models

            class MyModel(models.Model):
                _name = "my.model"
                _description = "My Model"

                name = fields.Char(required=True)
        """), encoding="utf-8")
        (module_dir / "__manifest__.py").write_text(textwrap.dedent("""\
            {
                "name": "Test Module",
                "version": "17.0.1.0.0",
                "license": "LGPL-3",
                "depends": ["base"],
                "data": [],
            }
        """), encoding="utf-8")
        if has_csv:
            (module_dir / "security").mkdir(parents=True, exist_ok=True)
            (module_dir / "security" / "ir.model.access.csv").write_text(
                csv_content, encoding="utf-8"
            )
        return module_dir

    def test_creates_csv_when_missing(self, tmp_path: Path):
        """Creates security/ir.model.access.csv with access rule when missing."""
        from amil_utils.auto_fix import fix_missing_acl

        module_dir = self._make_module(tmp_path, has_csv=False)
        error_output = "No access rule defined for model my.model ir.model.access"
        result = fix_missing_acl(module_dir, error_output)
        assert result is True

        csv_path = module_dir / "security" / "ir.model.access.csv"
        assert csv_path.exists()
        content = csv_path.read_text(encoding="utf-8")
        assert "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink" in content
        assert "access_my_model" in content
        assert "model_my_model" in content

    def test_returns_false_when_csv_has_model(self, tmp_path: Path):
        """Returns False when ir.model.access.csv already has the model."""
        from amil_utils.auto_fix import fix_missing_acl

        csv_content = (
            "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"
            "access_my_model,access.my.model,model_my_model,base.group_user,1,1,1,0\n"
        )
        module_dir = self._make_module(tmp_path, has_csv=True, csv_content=csv_content)
        error_output = "No access rule for model my.model"
        result = fix_missing_acl(module_dir, error_output)
        assert result is False

    def test_manifest_updated_with_csv_path(self, tmp_path: Path):
        """Manifest data list is updated to include security/ir.model.access.csv."""
        from amil_utils.auto_fix import fix_missing_acl

        module_dir = self._make_module(tmp_path, has_csv=False)
        error_output = "No access rule for model ir.model.access"
        fix_missing_acl(module_dir, error_output)

        manifest_content = (module_dir / "__manifest__.py").read_text(encoding="utf-8")
        assert "security/ir.model.access.csv" in manifest_content


# ---------------------------------------------------------------------------
# fix_manifest_load_order -- Docker fix for action/menu ordering
# ---------------------------------------------------------------------------


class TestFixManifestLoadOrder:
    """fix_manifest_load_order reorders manifest data so actions precede menus."""

    def _make_module(self, tmp_path: Path, data_files: list[str]) -> Path:
        """Helper: create a module with __manifest__.py and view files."""
        module_dir = tmp_path / "test_module"
        (module_dir / "views").mkdir(parents=True)

        # Create action file (defines actions)
        (module_dir / "views" / "actions.xml").write_text(textwrap.dedent("""\
            <odoo>
                <record id="action_my_model" model="ir.actions.act_window">
                    <field name="name">My Model</field>
                    <field name="res_model">my.model</field>
                    <field name="view_mode">list,form</field>
                </record>
            </odoo>
        """), encoding="utf-8")

        # Create menu file (references actions)
        (module_dir / "views" / "menus.xml").write_text(textwrap.dedent("""\
            <odoo>
                <menuitem id="menu_my_model"
                          name="My Model"
                          action="action_my_model"
                          parent="base.menu_custom"/>
            </odoo>
        """), encoding="utf-8")

        manifest_data = repr(data_files)
        (module_dir / "__manifest__.py").write_text(textwrap.dedent(f"""\
            {{
                "name": "Test Module",
                "version": "17.0.1.0.0",
                "license": "LGPL-3",
                "depends": ["base"],
                "data": {manifest_data},
            }}
        """), encoding="utf-8")
        return module_dir

    def test_reorders_menus_after_actions(self, tmp_path: Path):
        """Menus listed before actions get reordered so actions come first."""
        from amil_utils.auto_fix import fix_manifest_load_order

        # menus.xml before actions.xml -- wrong order
        module_dir = self._make_module(tmp_path, ["views/menus.xml", "views/actions.xml"])
        error_output = "External ID not found: action_my_model ir.actions.act_window does not exist"
        result = fix_manifest_load_order(module_dir, error_output)
        assert result is True

        manifest_content = (module_dir / "__manifest__.py").read_text(encoding="utf-8")
        actions_pos = manifest_content.index("actions.xml")
        menus_pos = manifest_content.index("menus.xml")
        assert actions_pos < menus_pos

    def test_correct_order_returns_false(self, tmp_path: Path):
        """Already correct order returns False."""
        from amil_utils.auto_fix import fix_manifest_load_order

        # actions.xml before menus.xml -- correct order
        module_dir = self._make_module(tmp_path, ["views/actions.xml", "views/menus.xml"])
        error_output = "External ID not found for action"
        result = fix_manifest_load_order(module_dir, error_output)
        assert result is False


# ---------------------------------------------------------------------------
# run_docker_fix_loop -- dispatch to new fix functions
# ---------------------------------------------------------------------------


class TestRunDockerFixLoopNewDispatch:
    """run_docker_fix_loop dispatches to the 3 new Docker fix functions."""

    def test_dispatches_xml_parse_error(self, tmp_path: Path):
        """run_docker_fix_loop dispatches to fix_xml_parse_error for XML errors."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        (module_dir / "views").mkdir(parents=True)
        (module_dir / "views" / "model_views.xml").write_text(textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <odoo>
                <record id="view_form" model="ir.ui.view">
                    <field name="arch" type="xml">
                        <form>
                            <sheet><group><field name="name"/></group></sheet>
                        </fom>
                    </field>
                </record>
            </odoo>
        """), encoding="utf-8")

        error_text = (
            "lxml.etree.XMLSyntaxError: Opening and ending tag mismatch: "
            "form line 5 and fom, line 7 (views/model_views.xml, line 7)"
        )
        result = run_docker_fix_loop(module_dir, error_text)
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is True

    def test_dispatches_missing_acl(self, tmp_path: Path):
        """run_docker_fix_loop dispatches to fix_missing_acl for ACL errors."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        (module_dir / "models").mkdir(parents=True)
        (module_dir / "models" / "__init__.py").write_text("from . import sale\n", encoding="utf-8")
        (module_dir / "models" / "sale.py").write_text(textwrap.dedent("""\
            from odoo import fields, models

            class Sale(models.Model):
                _name = "test.sale"
                _description = "Test Sale"

                name = fields.Char(required=True)
        """), encoding="utf-8")
        (module_dir / "__manifest__.py").write_text(textwrap.dedent("""\
            {
                "name": "Test",
                "version": "17.0.1.0.0",
                "license": "LGPL-3",
                "depends": ["base"],
                "data": [],
            }
        """), encoding="utf-8")

        error_text = "No access rule defined for model test.sale. ir.model.access entry required."
        result = run_docker_fix_loop(module_dir, error_text)
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is True

    def test_dispatches_manifest_load_order(self, tmp_path: Path):
        """run_docker_fix_loop dispatches to fix_manifest_load_order for action reference errors."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        (module_dir / "views").mkdir(parents=True)
        (module_dir / "views" / "actions.xml").write_text(textwrap.dedent("""\
            <odoo>
                <record id="action_test" model="ir.actions.act_window">
                    <field name="name">Test</field>
                    <field name="res_model">test.model</field>
                </record>
            </odoo>
        """), encoding="utf-8")
        (module_dir / "views" / "menus.xml").write_text(textwrap.dedent("""\
            <odoo>
                <menuitem id="menu_test" action="action_test"/>
            </odoo>
        """), encoding="utf-8")
        (module_dir / "__manifest__.py").write_text(textwrap.dedent("""\
            {
                "name": "Test",
                "version": "17.0.1.0.0",
                "license": "LGPL-3",
                "depends": ["base"],
                "data": ["views/menus.xml", "views/actions.xml"],
            }
        """), encoding="utf-8")

        error_text = "External ID not found: action_test. ir.actions.act_window does not exist"
        result = run_docker_fix_loop(module_dir, error_text)
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is True


# ---------------------------------------------------------------------------
# Task 2: Configurable iteration caps
# ---------------------------------------------------------------------------


class TestDefaultMaxFixIterations:
    """DEFAULT_MAX_FIX_ITERATIONS replaces MAX_FIX_CYCLES."""

    def test_default_max_fix_iterations_equals_five(self):
        from amil_utils.auto_fix import DEFAULT_MAX_FIX_ITERATIONS

        assert DEFAULT_MAX_FIX_ITERATIONS == 5


class TestPylintFixLoopMaxIterations:
    """run_pylint_fix_loop accepts and honors max_iterations parameter."""

    def test_max_iterations_default_is_five(self):
        """Default max_iterations runs up to 5 cycles."""
        cycle_count = 0
        src = (
            'from odoo import fields, models\n\n'
            'class M(models.Model):\n'
            '    _name = "m"\n'
            '    name = fields.Char(string="Name")\n'
        )
        fixable_v = Violation(
            file="models/m.py", line=5, column=0,
            rule_code="W8113", symbol="redundant-string",
            severity="warning", message='Redundant string= on field "name"',
        )
        non_fixable_v = Violation(
            file="models/m.py", line=10, column=0,
            rule_code="E8103", symbol="missing-description",
            severity="error", message="Model _description missing",
        )

        def mock_run_pylint(*args, **kwargs):
            nonlocal cycle_count
            cycle_count += 1
            # Re-create file so fix always has work
            model_file.write_text(src, encoding="utf-8")
            return Result.ok((fixable_v, non_fixable_v))

        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            model_file = mod / "models" / "m.py"
            model_file.parent.mkdir(parents=True)
            model_file.write_text(src, encoding="utf-8")

            with patch("amil_utils.auto_fix.run_pylint_odoo", side_effect=mock_run_pylint):
                result = run_pylint_fix_loop(mod)
                total_fixed, remaining = result.data

            assert cycle_count == 5

    def test_max_iterations_one_runs_one_cycle(self):
        """max_iterations=1 runs exactly 1 cycle."""
        cycle_count = 0
        src = (
            'from odoo import fields, models\n\n'
            'class M(models.Model):\n'
            '    _name = "m"\n'
            '    name = fields.Char(string="Name")\n'
        )
        fixable_v = Violation(
            file="models/m.py", line=5, column=0,
            rule_code="W8113", symbol="redundant-string",
            severity="warning", message='Redundant string= on field "name"',
        )

        def mock_run_pylint(*args, **kwargs):
            nonlocal cycle_count
            cycle_count += 1
            model_file.write_text(src, encoding="utf-8")
            return Result.ok((fixable_v,))

        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            model_file = mod / "models" / "m.py"
            model_file.parent.mkdir(parents=True)
            model_file.write_text(src, encoding="utf-8")

            with patch("amil_utils.auto_fix.run_pylint_odoo", side_effect=mock_run_pylint):
                result = run_pylint_fix_loop(mod, max_iterations=1)
                total_fixed, remaining = result.data

            assert cycle_count == 1

    def test_max_iterations_five_explicit(self):
        """max_iterations=5 runs at most 5 cycles."""
        cycle_count = 0
        src = (
            'from odoo import fields, models\n\n'
            'class M(models.Model):\n'
            '    _name = "m"\n'
            '    name = fields.Char(string="Name")\n'
        )
        fixable_v = Violation(
            file="models/m.py", line=5, column=0,
            rule_code="W8113", symbol="redundant-string",
            severity="warning", message='Redundant string= on field "name"',
        )

        def mock_run_pylint(*args, **kwargs):
            nonlocal cycle_count
            cycle_count += 1
            model_file.write_text(src, encoding="utf-8")
            return Result.ok((fixable_v,))

        with tempfile.TemporaryDirectory() as d:
            mod = Path(d)
            model_file = mod / "models" / "m.py"
            model_file.parent.mkdir(parents=True)
            model_file.write_text(src, encoding="utf-8")

            with patch("amil_utils.auto_fix.run_pylint_odoo", side_effect=mock_run_pylint):
                result = run_pylint_fix_loop(mod, max_iterations=5)
                total_fixed, remaining = result.data

            assert cycle_count == 5


class TestDockerFixLoopIterations:
    """run_docker_fix_loop runs in a loop with iteration cap."""

    def test_loops_with_revalidate_fn(self, tmp_path: Path):
        """run_docker_fix_loop loops: fix -> revalidate -> fix again."""
        from amil_utils.auto_fix import run_docker_fix_loop

        call_count = 0
        module_dir = tmp_path / "test_module"
        (module_dir / "models").mkdir(parents=True)
        (module_dir / "models" / "__init__.py").write_text("from . import m\n", encoding="utf-8")
        (module_dir / "models" / "m.py").write_text(textwrap.dedent("""\
            from odoo import fields, models

            class M(models.Model):
                _name = "test.m"
                _description = "Test"
                name = fields.Char(required=True)
        """), encoding="utf-8")
        (module_dir / "__manifest__.py").write_text(textwrap.dedent("""\
            {
                "name": "Test",
                "version": "17.0.1.0.0",
                "license": "LGPL-3",
                "depends": ["base"],
                "data": [],
            }
        """), encoding="utf-8")

        def revalidate_fn():
            nonlocal call_count
            call_count += 1
            from amil_utils.validation.types import InstallResult
            # First revalidation: still has an error (different one this time)
            if call_count == 1:
                return Result.ok(InstallResult(success=False, log_output="", error_message="fixed now"))
            return Result.ok(InstallResult(success=True, log_output="", error_message=""))

        error_text = "No access rule for model test.m. ir.model.access required"
        result = run_docker_fix_loop(
            module_dir, error_text, max_iterations=5, revalidate_fn=revalidate_fn
        )
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is True

    def test_stops_when_no_fix_applied(self, tmp_path: Path):
        """run_docker_fix_loop stops when fix function returns False."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        module_dir.mkdir(parents=True)

        error_text = "Something completely unrecognized"
        result = run_docker_fix_loop(
            module_dir, error_text, max_iterations=5
        )
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is False

    def test_stops_when_tried_pattern_repeated(self, tmp_path: Path):
        """run_docker_fix_loop stops when same pattern is tried again (smart guard).

        With tried_patterns tracking, the loop no longer hits the iteration cap
        for repeated patterns — it breaks early when the pattern is skipped.
        """
        from amil_utils.auto_fix import run_docker_fix_loop

        revalidate_count = 0
        module_dir = tmp_path / "test_module"
        (module_dir / "models").mkdir(parents=True)
        (module_dir / "models" / "__init__.py").write_text("from . import m\n", encoding="utf-8")

        # Create a model that will always need ACL (fix is always "applied"
        # because we keep recreating the missing state)
        def make_model():
            (module_dir / "models" / "m.py").write_text(textwrap.dedent("""\
                from odoo import fields, models

                class M(models.Model):
                    _name = "test.m"
                    _description = "Test"
                    name = fields.Char(required=True)
            """), encoding="utf-8")
            (module_dir / "__manifest__.py").write_text(textwrap.dedent("""\
                {
                    "name": "Test",
                    "version": "17.0.1.0.0",
                    "license": "LGPL-3",
                    "depends": ["base"],
                    "data": [],
                }
            """), encoding="utf-8")
            # Remove existing CSV so fix is needed again
            csv = module_dir / "security" / "ir.model.access.csv"
            if csv.exists():
                csv.unlink()

        make_model()

        def revalidate_fn():
            nonlocal revalidate_count
            revalidate_count += 1
            # Always return error to force continued iterations
            make_model()  # Reset state so fix is needed again
            from amil_utils.validation.types import InstallResult
            return Result.ok(InstallResult(
                success=False,
                log_output="No access rule for model test.m. ir.model.access required",
                error_message="still broken",
            ))

        error_text = "No access rule for model test.m. ir.model.access required"
        result = run_docker_fix_loop(
            module_dir, error_text, max_iterations=5, revalidate_fn=revalidate_fn
        )
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is True
        # Smart guard: loop breaks after 2 iterations (fix + skip) not at cap
        assert revalidate_count == 1

    def test_iteration_cap_message_text(self, tmp_path: Path):
        """Cap message includes 'Iteration cap (N) reached'.

        Uses mocked dispatch returning different patterns each time to avoid
        smart guard dedup, ensuring the loop actually hits the cap.
        """
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()

        iteration_count = 0

        def revalidate_fn():
            nonlocal iteration_count
            iteration_count += 1
            from amil_utils.validation.types import InstallResult
            return Result.ok(InstallResult(
                success=False,
                log_output="some error remains",
                error_message="still broken",
            ))

        with patch('amil_utils.auto_fix._dispatch_docker_fix') as mock_dispatch:
            # Return a different pattern_id each time so smart guard doesn't skip
            mock_dispatch.side_effect = [
                (True, "pattern_a"),
                (True, "pattern_b"),
                (True, "pattern_c"),
            ]
            result = run_docker_fix_loop(
                module_dir, "some error", max_iterations=3, revalidate_fn=revalidate_fn
            )
        assert result.success
        any_fixed, remaining = result.data
        assert "Iteration cap (3) reached" in remaining
        assert "manual review" in remaining.lower()


# ---------------------------------------------------------------------------
# Multi-line test cases for AST-based fixers
# ---------------------------------------------------------------------------


class TestFixW8113MultiLine:
    """W8113: redundant string= removal on multi-line field definitions."""

    def test_removes_string_on_own_line(self, tmp_path: Path):
        """string="Name" on its own line in a multi-line field def is removed."""
        src = textwrap.dedent('''\
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                name = fields.Char(
                    string="Name",
                    required=True,
                )
        ''')
        mod = tmp_path / "mod"
        model_file = mod / "models" / "test_model.py"
        model_file.parent.mkdir(parents=True)
        model_file.write_text(src, encoding="utf-8")

        v = Violation(
            file="models/test_model.py", line=6, column=0,
            rule_code="W8113", symbol="redundant-string",
            severity="warning", message='Redundant string= on field "name"',
        )
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = model_file.read_text(encoding="utf-8")
        assert "string=" not in content
        assert "required=True" in content
        # No double blank lines left
        assert "\n\n\n" not in content

    def test_removes_string_as_last_kwarg(self, tmp_path: Path):
        """string="Name" as last keyword (no trailing comma) is removed, preceding comma cleaned."""
        src = textwrap.dedent('''\
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                name = fields.Char(
                    required=True,
                    string="Name"
                )
        ''')
        mod = tmp_path / "mod"
        model_file = mod / "models" / "test_model.py"
        model_file.parent.mkdir(parents=True)
        model_file.write_text(src, encoding="utf-8")

        v = Violation(
            file="models/test_model.py", line=7, column=0,
            rule_code="W8113", symbol="redundant-string",
            severity="warning", message='Redundant string= on field "name"',
        )
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = model_file.read_text(encoding="utf-8")
        assert "string=" not in content
        assert "required=True" in content
        # Closing paren should still be there
        assert ")" in content


class TestFixW8111MultiLine:
    """W8111: renamed parameter on multi-line field definitions."""

    def test_renames_param_on_own_line(self, tmp_path: Path):
        """track_visibility="always" on own line is renamed to tracking="always"."""
        src = textwrap.dedent('''\
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                state = fields.Selection(
                    selection=[("draft", "Draft")],
                    track_visibility="always",
                    required=True,
                )
        ''')
        mod = tmp_path / "mod"
        model_file = mod / "models" / "test_model.py"
        model_file.parent.mkdir(parents=True)
        model_file.write_text(src, encoding="utf-8")

        v = Violation(
            file="models/test_model.py", line=7, column=0,
            rule_code="W8111", symbol="renamed-field-parameter",
            severity="warning",
            message='"track_visibility" has been renamed to "tracking"',
        )
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = model_file.read_text(encoding="utf-8")
        assert "tracking=" in content
        assert "track_visibility" not in content
        assert "required=True" in content

    def test_removes_param_on_own_line(self, tmp_path: Path):
        """oldname="old_field" on own line is removed entirely (None mapping)."""
        src = textwrap.dedent('''\
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                name = fields.Char(
                    required=True,
                    oldname="old_field",
                    help="A field",
                )
        ''')
        mod = tmp_path / "mod"
        model_file = mod / "models" / "test_model.py"
        model_file.parent.mkdir(parents=True)
        model_file.write_text(src, encoding="utf-8")

        v = Violation(
            file="models/test_model.py", line=7, column=0,
            rule_code="W8111", symbol="renamed-field-parameter",
            severity="warning",
            message='"oldname" has been renamed to None',
        )
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = model_file.read_text(encoding="utf-8")
        assert "oldname" not in content
        assert "required=True" in content
        assert 'help="A field"' in content


class TestFixC8116MultiLineValue:
    """C8116: superfluous manifest key with multi-line values."""

    def test_removes_key_with_list_value(self, tmp_path: Path):
        """Manifest key with multi-line list value is fully removed."""
        src = textwrap.dedent('''\
            {
                "name": "Test",
                "data": [
                    "file1.xml",
                    "file2.xml",
                ],
                "license": "LGPL-3",
            }
        ''')
        mod = tmp_path / "mod"
        manifest = mod / "__manifest__.py"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(src, encoding="utf-8")

        v = Violation(
            file="__manifest__.py", line=3, column=0,
            rule_code="C8116", symbol="superfluous-manifest-key",
            severity="convention",
            message='Deprecated key "data" in manifest file',
        )
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = manifest.read_text(encoding="utf-8")
        assert '"data"' not in content
        assert "file1.xml" not in content
        assert "file2.xml" not in content
        assert '"license": "LGPL-3"' in content

    def test_removes_key_with_multiline_string(self, tmp_path: Path):
        """Manifest key with multi-line string value is fully removed."""
        # Use a triple-quoted string as the value
        src = '{\n    "name": "Test",\n    "description": "A very\\nlong\\nstring",\n    "license": "LGPL-3",\n}\n'
        mod = tmp_path / "mod"
        manifest = mod / "__manifest__.py"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(src, encoding="utf-8")

        v = Violation(
            file="__manifest__.py", line=3, column=0,
            rule_code="C8116", symbol="superfluous-manifest-key",
            severity="convention",
            message='Deprecated key "description" in manifest file',
        )
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = manifest.read_text(encoding="utf-8")
        assert '"description"' not in content
        assert '"license": "LGPL-3"' in content


# ---------------------------------------------------------------------------
# FIXABLE_DOCKER_PATTERNS — edge-case tests (Task #13)
# ---------------------------------------------------------------------------


class TestFixXmlParseErrorEdgeCases:
    """Edge cases for fix_xml_parse_error auto-fix path."""

    def test_heuristic_fallback_no_mismatch_pattern(self, tmp_path: Path):
        """When error output lacks explicit mismatch info, heuristic tag
        counting still fixes the orphaned closing tag."""
        from amil_utils.auto_fix import fix_xml_parse_error

        module_dir = tmp_path / "test_module"
        (module_dir / "views").mkdir(parents=True)
        # <grup> is a typo for <group> — the closing tag </grup> has no opener
        (module_dir / "views" / "v.xml").write_text(
            "<odoo><form><group><field name='x'/></grup></form></odoo>",
            encoding="utf-8",
        )
        # Error output without "Opening and ending tag mismatch" pattern
        error_output = "lxml.etree.XMLSyntaxError: views/v.xml parse error"
        result = fix_xml_parse_error(module_dir, error_output)
        assert result is True
        content = (module_dir / "views" / "v.xml").read_text(encoding="utf-8")
        assert "</grup>" not in content

    def test_no_xml_files_returns_false(self, tmp_path: Path):
        """Returns False when module has no views/ directory."""
        from amil_utils.auto_fix import fix_xml_parse_error

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        result = fix_xml_parse_error(module_dir, "some xml error")
        assert result is False

    def test_path_traversal_blocked(self, tmp_path: Path):
        """Path traversal in error output file reference is blocked (SEC-06)."""
        from amil_utils.auto_fix import fix_xml_parse_error

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        # Create a file outside the module
        outside = tmp_path / "secret.xml"
        outside.write_text("<bad>data</bad>", encoding="utf-8")

        error_output = f'File "{outside}" parse error'
        # Should not reach outside file — returns False
        result = fix_xml_parse_error(module_dir, error_output)
        assert result is False


class TestFixMissingAclEdgeCases:
    """Edge cases for fix_missing_acl auto-fix path."""

    def test_multiple_models_all_get_acl(self, tmp_path: Path):
        """When module defines multiple models, all get ACL entries."""
        from amil_utils.auto_fix import fix_missing_acl

        module_dir = tmp_path / "test_module"
        (module_dir / "models").mkdir(parents=True)
        (module_dir / "models" / "__init__.py").write_text(
            "from . import a, b\n", encoding="utf-8"
        )
        (module_dir / "models" / "a.py").write_text(
            'from odoo import models\n\nclass A(models.Model):\n'
            '    _name = "mod.a"\n    _description = "A"\n',
            encoding="utf-8",
        )
        (module_dir / "models" / "b.py").write_text(
            'from odoo import models\n\nclass B(models.Model):\n'
            '    _name = "mod.b"\n    _description = "B"\n',
            encoding="utf-8",
        )
        (module_dir / "__manifest__.py").write_text(
            '{\n    "name": "T",\n    "version": "17.0.1.0.0",\n'
            '    "license": "LGPL-3",\n    "depends": ["base"],\n    "data": [],\n}\n',
            encoding="utf-8",
        )

        result = fix_missing_acl(module_dir, "no access rule ir.model.access")
        assert result is True

        csv_content = (module_dir / "security" / "ir.model.access.csv").read_text(encoding="utf-8")
        assert "model_mod_a" in csv_content
        assert "model_mod_b" in csv_content

    def test_no_models_dir_returns_false(self, tmp_path: Path):
        """Returns False when module has no models/ directory."""
        from amil_utils.auto_fix import fix_missing_acl

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        result = fix_missing_acl(module_dir, "some error")
        assert result is False


class TestFixManifestLoadOrderEdgeCases:
    """Edge cases for fix_manifest_load_order auto-fix path."""

    def test_no_manifest_returns_false(self, tmp_path: Path):
        """Returns False when __manifest__.py is missing."""
        from amil_utils.auto_fix import fix_manifest_load_order

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        result = fix_manifest_load_order(module_dir, "some error")
        assert result is False

    def test_single_data_file_returns_false(self, tmp_path: Path):
        """Returns False when data list has only one file (nothing to reorder)."""
        from amil_utils.auto_fix import fix_manifest_load_order

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        (module_dir / "__manifest__.py").write_text(
            '{\n    "name": "T",\n    "data": ["views/form.xml"],\n}\n',
            encoding="utf-8",
        )
        result = fix_manifest_load_order(module_dir, "some error")
        assert result is False

    def test_preserves_non_action_files(self, tmp_path: Path):
        """Non-action/non-menu files (security, data) stay in their group."""
        from amil_utils.auto_fix import fix_manifest_load_order

        module_dir = tmp_path / "test_module"
        (module_dir / "views").mkdir(parents=True)
        (module_dir / "security").mkdir(parents=True)

        # Action definer
        (module_dir / "views" / "actions.xml").write_text(
            '<odoo><record model="ir.actions.act_window" id="act"><field name="name">A</field></record></odoo>',
            encoding="utf-8",
        )
        # Action referencer
        (module_dir / "views" / "menus.xml").write_text(
            '<odoo><menuitem id="m" action="act"/></odoo>',
            encoding="utf-8",
        )
        # Neither (security data)
        (module_dir / "security" / "rules.xml").write_text(
            '<odoo><record model="ir.rule" id="r"><field name="name">R</field></record></odoo>',
            encoding="utf-8",
        )

        # Wrong order: menus before actions, with security file mixed in
        (module_dir / "__manifest__.py").write_text(
            '{\n    "name": "T",\n    "data": ["views/menus.xml", "security/rules.xml", "views/actions.xml"],\n}\n',
            encoding="utf-8",
        )
        result = fix_manifest_load_order(module_dir, "act_window does not exist")
        assert result is True

        manifest = (module_dir / "__manifest__.py").read_text(encoding="utf-8")
        actions_pos = manifest.index("actions.xml")
        menus_pos = manifest.index("menus.xml")
        assert actions_pos < menus_pos


class TestMissingImportPatternDispatch:
    """missing_import is identified but has no fix function — dispatch returns False."""

    def test_missing_import_identified_but_not_fixable(self, tmp_path: Path):
        """Dispatch loop identifies missing_import but returns no-fix since there's
        no fix function registered for it."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()

        error_text = "ImportError: No module named 'some_missing_addon'"
        result = run_docker_fix_loop(module_dir, error_text)
        assert result.success
        any_fixed, remaining = result.data
        assert any_fixed is False

    def test_missing_import_identify_docker_fix(self):
        """identify_docker_fix returns 'missing_import' for ModuleNotFoundError."""
        diagnosis = "ModuleNotFoundError: No module named 'nonexistent'"
        result = identify_docker_fix(diagnosis)
        assert result == "missing_import"


class TestFixMissingMailThreadEdgeCases:
    """Edge cases for fix_missing_mail_thread."""

    def test_no_chatter_returns_false(self, tmp_path: Path):
        """Returns False when views/ has no chatter indicators."""
        module_dir = tmp_path / "test_module"
        (module_dir / "views").mkdir(parents=True)
        (module_dir / "models").mkdir(parents=True)
        (module_dir / "views" / "form.xml").write_text(
            "<odoo><form><field name='name'/></form></odoo>", encoding="utf-8"
        )
        (module_dir / "models" / "m.py").write_text(
            'from odoo import models\nclass M(models.Model):\n'
            '    _name = "test.m"\n    _description = "T"\n',
            encoding="utf-8",
        )
        result = fix_missing_mail_thread(module_dir)
        assert result is False

    def test_already_has_mail_thread_returns_false(self, tmp_path: Path):
        """Returns False when model already inherits mail.thread."""
        module_dir = tmp_path / "test_module"
        (module_dir / "views").mkdir(parents=True)
        (module_dir / "models").mkdir(parents=True)
        (module_dir / "views" / "form.xml").write_text(
            '<odoo><div class="oe_chatter"/></odoo>', encoding="utf-8"
        )
        (module_dir / "models" / "m.py").write_text(
            'from odoo import models\nclass M(models.Model):\n'
            '    _name = "test.m"\n    _description = "T"\n'
            "    _inherit = ['mail.thread']\n",
            encoding="utf-8",
        )
        result = fix_missing_mail_thread(module_dir)
        assert result is False


# ---------------------------------------------------------------------------
# Gap 8: Auto-Fix Smart Guard — tried_patterns tracking
# ---------------------------------------------------------------------------


class TestDispatchDockerFixReturnsTuple:
    """_dispatch_docker_fix returns (bool, str | None) tuples."""

    def test_dispatch_docker_fix_returns_tuple(self, tmp_path: Path):
        """Call with a known error pattern, assert result is a tuple."""
        from amil_utils.auto_fix import _dispatch_docker_fix

        module_dir = tmp_path / "test_module"
        (module_dir / "views").mkdir(parents=True)
        (module_dir / "models").mkdir(parents=True)
        # Create a model file with chatter in view but missing mail.thread
        (module_dir / "views" / "form.xml").write_text(
            '<odoo><div class="oe_chatter"/></odoo>', encoding="utf-8"
        )
        (module_dir / "models" / "m.py").write_text(
            'from odoo import models\nclass M(models.Model):\n'
            '    _name = "test.m"\n    _description = "T"\n',
            encoding="utf-8",
        )
        error_text = "mail.thread: AttributeError: type object 'M' has no attribute 'message_ids'"
        result = _dispatch_docker_fix(module_dir, error_text)
        assert isinstance(result, tuple)
        assert len(result) == 2
        fix_applied, pattern_id = result
        assert isinstance(fix_applied, bool)
        assert pattern_id == "missing_mail_thread"

    def test_dispatch_docker_fix_skips_tried_pattern(self, tmp_path: Path):
        """Pass tried_patterns={'missing_acl'}, feed error matching missing_acl, assert skipped."""
        from amil_utils.auto_fix import _dispatch_docker_fix

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        error_text = "Access Denied: ir.model.access for model 'test.model'"
        result = _dispatch_docker_fix(module_dir, error_text, tried_patterns={"missing_acl"})
        assert result == (False, "missing_acl")

    def test_dispatch_docker_fix_unused_import_exempt(self, tmp_path: Path):
        """Unused imports are exempt from tried_patterns dedup — cumulative fix."""
        from amil_utils.auto_fix import _dispatch_docker_fix

        module_dir = tmp_path / "test_module"
        (module_dir / "models").mkdir(parents=True)
        (module_dir / "models" / "__init__.py").write_text("from . import m\n", encoding="utf-8")
        (module_dir / "models" / "m.py").write_text(
            'from odoo import models, fields, api\n\n'
            'class M(models.Model):\n'
            '    _name = "test.m"\n'
            '    _description = "T"\n'
            '    name = fields.Char()\n',
            encoding="utf-8",
        )
        error_text = "unused-import: 'odoo.api' imported but unused"
        # Even with tried_patterns containing "unused_import", should still fix
        result = _dispatch_docker_fix(
            module_dir, error_text, tried_patterns={"unused_import"}
        )
        fix_applied, pattern_id = result
        assert fix_applied is True
        assert pattern_id == "unused_import"

    def test_dispatch_docker_fix_tried_patterns_none(self, tmp_path: Path):
        """tried_patterns=None means no filtering occurs (backward compat)."""
        from amil_utils.auto_fix import _dispatch_docker_fix

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        # Unrecognized error — no pattern matched
        result = _dispatch_docker_fix(module_dir, "some random error", tried_patterns=None)
        assert result == (False, None)

    def test_dispatch_docker_fix_empty_error(self, tmp_path: Path):
        """Empty error text returns (False, None)."""
        from amil_utils.auto_fix import _dispatch_docker_fix

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        result = _dispatch_docker_fix(module_dir, "")
        assert result == (False, None)


class TestRunDockerFixLoopTriedPatterns:
    """run_docker_fix_loop tracks tried_patterns to avoid retrying."""

    def test_run_docker_fix_loop_tracks_tried_patterns(self, tmp_path: Path):
        """Mock dispatch to succeed on first pattern, skip on second (same pattern).
        Assert loop breaks after 2 iterations instead of hitting cap."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()

        call_count = 0

        def mock_revalidate():
            """Return a failed Result so the loop tries again."""
            nonlocal call_count
            call_count += 1
            return Result.ok(type('InstallResult', (), {
                'success': False,
                'log_output': "Access Denied: ir.model.access for model 'test.m'",
                'error_message': '',
            })())

        with patch('amil_utils.auto_fix._dispatch_docker_fix') as mock_dispatch:
            # First call: fix applied, returns missing_acl pattern
            # Second call: same pattern in tried_patterns, returns skip
            mock_dispatch.side_effect = [
                (True, "missing_acl"),
                (False, "missing_acl"),
            ]
            result = run_docker_fix_loop(
                module_dir,
                "Access Denied: ir.model.access for model 'test.m'",
                max_iterations=5,
                revalidate_fn=mock_revalidate,
            )
            assert result.success
            any_fixed, _ = result.data
            assert any_fixed is True
            # Should have called dispatch exactly 2 times (not 5)
            assert mock_dispatch.call_count == 2

    def test_run_docker_fix_loop_breaks_early_when_all_tried(self, tmp_path: Path):
        """All patterns already tried — loop breaks on iteration 1."""
        from amil_utils.auto_fix import run_docker_fix_loop

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()

        with patch('amil_utils.auto_fix._dispatch_docker_fix') as mock_dispatch:
            # First call: no fix applied (pattern already tried externally)
            mock_dispatch.return_value = (False, None)
            result = run_docker_fix_loop(
                module_dir,
                "some error that doesn't match",
                max_iterations=5,
            )
            assert result.success
            any_fixed, _ = result.data
            assert any_fixed is False
            assert mock_dispatch.call_count == 1


# ---------------------------------------------------------------------------
# _fix_w8161_env_translate -- W8161 auto-fixer
# ---------------------------------------------------------------------------


class TestFixW8161EnvTranslate:
    """W8161: Replace _('msg') with self.env._('msg') inside method bodies."""

    def test_simple_translate_replacement(self, tmp_path: Path):
        """Single _('text') in a method -> self.env._('text')."""
        src = textwrap.dedent('''\
            from odoo import _, fields, models

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test"

                def action_confirm(self):
                    raise ValueError(_("Cannot confirm"))
        ''')
        mod = tmp_path / "test_module"
        (mod / "models").mkdir(parents=True)
        model_file = mod / "models" / "test_model.py"
        model_file.write_text(src, encoding="utf-8")

        v = Violation(file="models/test_model.py", line=8, column=0,
                      rule_code="W8161", symbol="translation-not-lazy",
                      severity="warning", message="_() used outside self.env")
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = model_file.read_text(encoding="utf-8")
        assert 'self.env._("Cannot confirm")' in content
        assert "from odoo import _" not in content or "from odoo import fields, models" in content

    def test_multiple_calls_in_one_method(self, tmp_path: Path):
        """Multiple _() calls in same method -> all replaced."""
        src = textwrap.dedent('''\
            from odoo import _, fields, models

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test"

                def action_confirm(self):
                    if not self.name:
                        raise ValueError(_("No name"))
                    self.message_post(body=_("Confirmed"))
        ''')
        mod = tmp_path / "test_module"
        (mod / "models").mkdir(parents=True)
        model_file = mod / "models" / "test_model.py"
        model_file.write_text(src, encoding="utf-8")

        v = Violation(file="models/test_model.py", line=9, column=0,
                      rule_code="W8161", symbol="translation-not-lazy",
                      severity="warning", message="_() used outside self.env")
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = model_file.read_text(encoding="utf-8")
        assert content.count("self.env._") == 2
        assert content.count('_("') == 2  # the self.env._(" occurrences

    def test_nested_function_no_double_replace(self, tmp_path: Path):
        """Nested function inside method -> _() replaced once, not doubled."""
        src = textwrap.dedent('''\
            from odoo import _, fields, models

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test"

                def action_compute(self):
                    def _helper():
                        return _("inner")
                    return _("outer")
        ''')
        mod = tmp_path / "test_module"
        (mod / "models").mkdir(parents=True)
        model_file = mod / "models" / "test_model.py"
        model_file.write_text(src, encoding="utf-8")

        v = Violation(file="models/test_model.py", line=9, column=0,
                      rule_code="W8161", symbol="translation-not-lazy",
                      severity="warning", message="_() used outside self.env")
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = model_file.read_text(encoding="utf-8")
        # Each _() should be replaced exactly once (not self.env.self.env._)
        assert "self.env.self.env._" not in content
        assert content.count("self.env._") == 2

    def test_class_level_call_untouched(self, tmp_path: Path):
        """_() at class level (e.g. _description = _('...')) is NOT replaced."""
        src = textwrap.dedent('''\
            from odoo import _, fields, models

            class TestModel(models.Model):
                _name = "test.model"
                _description = _("Test Model")

                name = fields.Char(required=True)
        ''')
        mod = tmp_path / "test_module"
        (mod / "models").mkdir(parents=True)
        model_file = mod / "models" / "test_model.py"
        model_file.write_text(src, encoding="utf-8")

        v = Violation(file="models/test_model.py", line=5, column=0,
                      rule_code="W8161", symbol="translation-not-lazy",
                      severity="warning", message="_() used outside self.env")
        result = fix_pylint_violation(v, mod)
        # Class-level _() is NOT inside a FunctionDef, so no changes
        assert result is False

    def test_removes_standalone_underscore_import(self, tmp_path: Path):
        """'from odoo import _' removed when sole import."""
        src = textwrap.dedent('''\
            from odoo import _
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test"

                def action_test(self):
                    return _("hello")
        ''')
        mod = tmp_path / "test_module"
        (mod / "models").mkdir(parents=True)
        model_file = mod / "models" / "test_model.py"
        model_file.write_text(src, encoding="utf-8")

        v = Violation(file="models/test_model.py", line=9, column=0,
                      rule_code="W8161", symbol="translation-not-lazy",
                      severity="warning", message="_() used outside self.env")
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = model_file.read_text(encoding="utf-8")
        assert "from odoo import _\n" not in content
        assert "from odoo import fields, models" in content

    def test_removes_underscore_from_multi_import(self, tmp_path: Path):
        """'from odoo import _, fields, models' -> 'from odoo import fields, models'."""
        src = textwrap.dedent('''\
            from odoo import _, fields, models

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test"

                def action_test(self):
                    return _("hello")
        ''')
        mod = tmp_path / "test_module"
        (mod / "models").mkdir(parents=True)
        model_file = mod / "models" / "test_model.py"
        model_file.write_text(src, encoding="utf-8")

        v = Violation(file="models/test_model.py", line=8, column=0,
                      rule_code="W8161", symbol="translation-not-lazy",
                      severity="warning", message="_() used outside self.env")
        result = fix_pylint_violation(v, mod)
        assert result is True

        content = model_file.read_text(encoding="utf-8")
        assert "from odoo import fields, models" in content
        assert "_, " not in content

    def test_syntax_error_returns_false(self, tmp_path: Path):
        """Malformed Python -> returns False gracefully."""
        src = "def broken(\n"
        mod = tmp_path / "test_module"
        (mod / "models").mkdir(parents=True)
        model_file = mod / "models" / "bad.py"
        model_file.write_text(src, encoding="utf-8")

        v = Violation(file="models/bad.py", line=1, column=0,
                      rule_code="W8161", symbol="translation-not-lazy",
                      severity="warning", message="_() used outside self.env")
        result = fix_pylint_violation(v, mod)
        assert result is False

    def test_no_calls_returns_false(self, tmp_path: Path):
        """File with no _() calls -> returns False."""
        src = textwrap.dedent('''\
            from odoo import fields, models

            class TestModel(models.Model):
                _name = "test.model"
                _description = "Test"

                def action_test(self):
                    return "hello"
        ''')
        mod = tmp_path / "test_module"
        (mod / "models").mkdir(parents=True)
        model_file = mod / "models" / "test_model.py"
        model_file.write_text(src, encoding="utf-8")

        v = Violation(file="models/test_model.py", line=8, column=0,
                      rule_code="W8161", symbol="translation-not-lazy",
                      severity="warning", message="_() used outside self.env")
        result = fix_pylint_violation(v, mod)
        assert result is False
