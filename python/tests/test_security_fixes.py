"""Tests for security fixes across the pipeline."""
from __future__ import annotations

import pytest


class TestWhereClauseValidation:
    """S1: WHERE clause in composite index must be safe SQL predicates only."""

    def test_safe_where_clause_accepted(self):
        from amil_utils.preprocessors.performance import _validate_where_clause

        assert _validate_where_clause("active = True") is True
        assert _validate_where_clause("state != 'cancelled'") is True
        assert _validate_where_clause("amount > 0") is True
        assert _validate_where_clause("parent_id IS NOT NULL") is True
        assert _validate_where_clause("active = True AND state = 'confirmed'") is True

    def test_unsafe_where_clause_rejected(self):
        from amil_utils.preprocessors.performance import _validate_where_clause

        assert _validate_where_clause("1=1; DROP TABLE res_users; --") is False
        assert _validate_where_clause("active = True; DELETE FROM") is False
        assert _validate_where_clause("') OR 1=1 --") is False
        assert _validate_where_clause("active = True UNION SELECT * FROM") is False

    def test_empty_where_clause_accepted(self):
        from amil_utils.preprocessors.performance import _validate_where_clause

        assert _validate_where_clause("") is True
        assert _validate_where_clause(None) is True


class TestConstraintCodeValidation:
    """S2: check_body/check_expr must not contain dangerous Python constructs."""

    def test_safe_check_expr_accepted(self):
        from amil_utils.preprocessors.constraints import _validate_generated_code

        assert _validate_generated_code("rec.date_start and rec.date_end and rec.date_start > rec.date_end") is True
        assert _validate_generated_code("rec.amount > 0") is True

    def test_import_statement_rejected(self):
        from amil_utils.preprocessors.constraints import _validate_generated_code

        assert _validate_generated_code("import os; os.system('rm -rf /')") is False
        assert _validate_generated_code("__import__('os').system('ls')") is False

    def test_exec_eval_rejected(self):
        from amil_utils.preprocessors.constraints import _validate_generated_code

        assert _validate_generated_code("exec('print(1)')") is False
        assert _validate_generated_code("eval('1+1')") is False

    def test_subprocess_rejected(self):
        from amil_utils.preprocessors.constraints import _validate_generated_code

        assert _validate_generated_code("subprocess.run(['ls'])") is False
        assert _validate_generated_code("os.system('whoami')") is False

    def test_multiline_check_body_validated(self):
        from amil_utils.preprocessors.constraints import _validate_generated_code

        safe_body = (
            "for rec in self:\n"
            "    if rec.amount < 0:\n"
            "        raise ValidationError(_('Amount must be positive'))\n"
        )
        assert _validate_generated_code(safe_body) is True

        unsafe_body = (
            "import subprocess\n"
            "subprocess.run(['rm', '-rf', '/'])\n"
        )
        assert _validate_generated_code(unsafe_body) is False


class TestForkInputValidation:
    """S8: repo_name, branch, module_name must match safe patterns."""

    def test_safe_repo_name_accepted(self):
        from amil_utils.search.fork import _validate_clone_inputs

        _validate_clone_inputs("sale-workflow", "sale_order_type", "17.0")

    def test_traversal_repo_name_rejected(self):
        from amil_utils.search.fork import _validate_clone_inputs

        with pytest.raises(ValueError, match="repo_name"):
            _validate_clone_inputs("../../evil-repo", "module", "17.0")

    def test_unsafe_branch_rejected(self):
        from amil_utils.search.fork import _validate_clone_inputs

        with pytest.raises(ValueError, match="branch"):
            _validate_clone_inputs("sale-workflow", "module", "--upload-pack=evil")

    def test_unsafe_module_rejected(self):
        from amil_utils.search.fork import _validate_clone_inputs

        with pytest.raises(ValueError, match="module_name"):
            _validate_clone_inputs("sale-workflow", "../etc/passwd", "17.0")
