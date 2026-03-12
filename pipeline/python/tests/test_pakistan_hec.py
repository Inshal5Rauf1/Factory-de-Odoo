"""Tests for Pakistan/HEC localization preprocessor.

Phase 49: CNIC, phone, NTN/STRN, HEC academic fields, PKR currency injection.
"""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(
    models: list[dict[str, Any]] | None = None,
    localization: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal spec for pakistan_hec preprocessor testing."""
    spec: dict[str, Any] = {
        "module_name": "test_module",
        "depends": ["base"],
        "models": models or [],
        **kwargs,
    }
    if localization is not None:
        spec["localization"] = localization
    return spec


def _make_model(
    name: str = "test.model",
    fields: list[dict[str, Any]] | None = None,
    pk_fields: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal model dict for testing."""
    model: dict[str, Any] = {
        "name": name,
        "description": name.replace(".", " ").title(),
        "fields": fields or [
            {"name": "name", "type": "Char", "required": True},
        ],
        **kwargs,
    }
    if pk_fields is not None:
        model["pk_fields"] = pk_fields
    return model


def _get_field(model: dict[str, Any], field_name: str) -> dict[str, Any] | None:
    """Find a field by name in model's fields list."""
    for f in model.get("fields", []):
        if f.get("name") == field_name:
            return f
    return None


def _get_sql_constraint(
    model: dict[str, Any], constraint_name: str
) -> dict[str, Any] | None:
    """Find an SQL constraint by name in model's sql_constraints list."""
    for c in model.get("sql_constraints", []):
        if c.get("name") == constraint_name:
            return c
    return None


def _get_complex_constraint(
    model: dict[str, Any], constraint_name: str
) -> dict[str, Any] | None:
    """Find a complex_constraint entry by name."""
    for c in model.get("complex_constraints", []):
        if c.get("name") == constraint_name:
            return c
    return None


def _process(spec: dict[str, Any]) -> dict[str, Any]:
    """Run the pakistan_hec preprocessor on a spec."""
    from amil_utils.preprocessors.pakistan_hec import _process_pakistan_hec

    return _process_pakistan_hec(spec)


# ===========================================================================
# TestPreprocessorRegistration
# ===========================================================================


class TestPreprocessorRegistration:
    """Registration at order=25, no-op for non-pk specs, no injection for empty pk_fields."""

    def test_registered_at_order_25(self):
        """pakistan_hec is registered at order=25 in the preprocessor registry."""
        from amil_utils.preprocessors._registry import (
            clear_registry,
            get_registered_preprocessors,
        )
        import importlib
        import amil_utils.preprocessors.pakistan_hec as mod

        clear_registry()
        importlib.reload(mod)
        entries = get_registered_preprocessors()
        pk_entries = [(o, n) for o, n, _fn in entries if n == "pakistan_hec"]
        assert len(pk_entries) == 1, f"Expected 1 pakistan_hec entry, got {pk_entries}"
        assert pk_entries[0][0] == 25
        clear_registry()

    def test_noop_for_non_pk_spec(self):
        """Spec without localization='pk' is returned unchanged."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["cnic"])],
            localization="us",
        )
        result = _process(spec)
        assert result is spec  # Same object -- early return

    def test_noop_for_missing_localization(self):
        """Spec without localization key is returned unchanged."""
        spec = _make_spec(models=[_make_model(pk_fields=["cnic"])])
        result = _process(spec)
        assert result is spec

    def test_no_injection_for_empty_pk_fields(self):
        """Model with localization=pk but no pk_fields gets nothing injected."""
        spec = _make_spec(
            models=[_make_model()],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        # Only the original "name" field should exist
        assert len(model["fields"]) == 1
        assert model["fields"][0]["name"] == "name"

    def test_no_injection_for_model_without_pk_fields_key(self):
        """Model without pk_fields key at all gets nothing injected."""
        spec = _make_spec(
            models=[_make_model()],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        assert len(model["fields"]) == 1


# ===========================================================================
# TestCnicInjection
# ===========================================================================


class TestCnicInjection:
    """CNIC field, SQL constraint, complex_constraint with check_body."""

    def test_cnic_field_added(self):
        """CNIC field is added with correct attributes."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["cnic"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        field = _get_field(model, "cnic")
        assert field is not None, "CNIC field not found"
        assert field["type"] == "Char"
        assert field["size"] == 15
        assert field["copy"] is False
        assert field["tracking"] is True
        assert field["string"] == "CNIC"
        assert "help" in field

    def test_cnic_sql_constraint_with_model_prefix(self):
        """SQL constraint name is prefixed with model variable name."""
        spec = _make_spec(
            models=[_make_model(name="university.student", pk_fields=["cnic"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        constraint = _get_sql_constraint(model, "university_student_cnic_unique")
        assert constraint is not None, (
            f"Expected 'university_student_cnic_unique', "
            f"got {[c.get('name') for c in model.get('sql_constraints', [])]}"
        )
        assert "UNIQUE(cnic)" in constraint["definition"]
        assert "CNIC must be unique" in constraint["message"]

    def test_cnic_complex_constraint(self):
        """Complex constraint entry with check_body for CNIC validation."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["cnic"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        cc = _get_complex_constraint(model, "cnic")
        assert cc is not None, "CNIC complex_constraint not found"
        assert cc["type"] == "pk_cnic"
        assert cc["fields"] == ["cnic"]
        # check_body should contain normalization and validation logic
        body = cc["check_body"]
        assert "re.sub" in body, "check_body should normalize with re.sub"
        assert "13" in body, "check_body should validate 13 digits"
        assert "XXXXX-XXXXXXX-X" in body or "raw[:5]" in body, (
            "check_body should normalize to dashed format"
        )

    def test_cnic_idempotent_field_not_duplicated(self):
        """If 'cnic' field already exists, it is NOT added again."""
        existing_fields = [
            {"name": "name", "type": "Char", "required": True},
            {"name": "cnic", "type": "Char", "size": 15},
        ]
        spec = _make_spec(
            models=[_make_model(fields=existing_fields, pk_fields=["cnic"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        cnic_fields = [f for f in model["fields"] if f["name"] == "cnic"]
        assert len(cnic_fields) == 1, "Should not duplicate existing cnic field"

    def test_cnic_idempotent_sql_constraint_not_duplicated(self):
        """If SQL constraint already exists with model-prefixed name, not added again."""
        spec = _make_spec(
            models=[_make_model(
                name="test.model",
                pk_fields=["cnic"],
                sql_constraints=[{
                    "name": "test_model_cnic_unique",
                    "definition": "UNIQUE(cnic)",
                    "message": "CNIC must be unique.",
                }],
            )],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        cnic_constraints = [
            c for c in model.get("sql_constraints", [])
            if "cnic_unique" in c.get("name", "")
        ]
        assert len(cnic_constraints) == 1, "Should not duplicate existing SQL constraint"


# ===========================================================================
# TestPhoneInjection
# ===========================================================================


class TestPhoneInjection:
    """Phone_pk field and complex_constraint with phonenumbers + regex fallback."""

    def test_phone_field_added(self):
        """phone_pk field is added with correct attributes."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["phone"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        field = _get_field(model, "phone_pk")
        assert field is not None, "phone_pk field not found"
        assert field["type"] == "Char"
        assert field["string"] == "Phone (PK)"
        assert field["tracking"] is True

    def test_phone_complex_constraint(self):
        """Complex constraint entry with phonenumbers and regex fallback."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["phone"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        cc = _get_complex_constraint(model, "phone_pakistan")
        assert cc is not None, "phone_pakistan complex_constraint not found"
        assert cc["type"] == "pk_phone"
        assert cc["fields"] == ["phone_pk"]
        body = cc["check_body"]
        # Should contain phonenumbers import attempt
        assert "phonenumbers" in body, "check_body should reference phonenumbers library"
        assert "ImportError" in body, "check_body should handle ImportError"
        # Should contain regex fallback
        assert "mobile" in body.lower() or r"3\d{9}" in body, (
            "check_body should have mobile regex pattern"
        )


# ===========================================================================
# TestNtnStrnInjection
# ===========================================================================


class TestNtnStrnInjection:
    """NTN and STRN fields with SQL constraints, model-prefixed names."""

    def test_ntn_field_added(self):
        """NTN field is added with correct attributes."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["ntn"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        field = _get_field(model, "ntn")
        assert field is not None, "NTN field not found"
        assert field["type"] == "Char"
        assert field["size"] == 9
        assert field["string"] == "NTN"
        assert field["copy"] is False
        assert field["tracking"] is True

    def test_ntn_sql_constraint_with_model_prefix(self):
        """NTN SQL constraint name is prefixed with model variable name."""
        spec = _make_spec(
            models=[_make_model(name="company.partner", pk_fields=["ntn"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        constraint = _get_sql_constraint(model, "company_partner_ntn_unique")
        assert constraint is not None
        assert "UNIQUE(ntn)" in constraint["definition"]

    def test_strn_field_added(self):
        """STRN field is added with correct attributes."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["strn"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        field = _get_field(model, "strn")
        assert field is not None, "STRN field not found"
        assert field["type"] == "Char"
        assert field["size"] == 15
        assert field["string"] == "STRN"
        assert field["copy"] is False
        assert field["tracking"] is True

    def test_strn_sql_constraint_with_model_prefix(self):
        """STRN SQL constraint name is prefixed with model variable name."""
        spec = _make_spec(
            models=[_make_model(name="tax.entity", pk_fields=["strn"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        constraint = _get_sql_constraint(model, "tax_entity_strn_unique")
        assert constraint is not None
        assert "UNIQUE(strn)" in constraint["definition"]

    def test_ntn_strn_combined(self):
        """Both NTN and STRN can be injected into the same model."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["ntn", "strn"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        assert _get_field(model, "ntn") is not None
        assert _get_field(model, "strn") is not None


# ===========================================================================
# TestHecFields
# ===========================================================================


class TestHecFields:
    """HEC registration, GPA, credit_hours, degree_level, recognition_status."""

    def test_hec_registration_field(self):
        """HEC registration field with correct attributes."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["hec_registration"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        field = _get_field(model, "hec_registration_no")
        assert field is not None, "hec_registration_no field not found"
        assert field["type"] == "Char"
        assert field["copy"] is False
        assert field["tracking"] is True
        assert field["string"] == "HEC Registration No."

    def test_hec_registration_sql_constraint(self):
        """HEC registration has SQL unique constraint with model prefix."""
        spec = _make_spec(
            models=[_make_model(name="hec.student", pk_fields=["hec_registration"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        constraint = _get_sql_constraint(model, "hec_student_hec_reg_unique")
        assert constraint is not None
        assert "UNIQUE(hec_registration_no)" in constraint["definition"]

    def test_gpa_field(self):
        """GPA field with Float type and correct digits."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["gpa"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        field = _get_field(model, "gpa")
        assert field is not None, "GPA field not found"
        assert field["type"] == "Float"
        assert field["digits"] == (3, 2)
        assert field["default"] == 0.0
        assert field["string"] == "GPA"

    def test_gpa_complex_constraint(self):
        """GPA has complex_constraint validating 0.00-4.00 range."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["gpa"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        cc = _get_complex_constraint(model, "gpa")
        assert cc is not None, "GPA complex_constraint not found"
        assert cc["type"] == "pk_gpa"
        body = cc["check_body"]
        assert "0.0" in body or "0.00" in body
        assert "4.0" in body or "4.00" in body

    def test_credit_hours_field(self):
        """Credit hours field with Integer type and default=3."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["credit_hours"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        field = _get_field(model, "credit_hours")
        assert field is not None, "credit_hours field not found"
        assert field["type"] == "Integer"
        assert field["default"] == 3
        assert field["string"] == "Credit Hours"

    def test_credit_hours_complex_constraint(self):
        """Credit hours has complex_constraint validating 0-6 range."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["credit_hours"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        cc = _get_complex_constraint(model, "credit_hours")
        assert cc is not None, "credit_hours complex_constraint not found"
        assert cc["type"] == "pk_credit_hours"
        body = cc["check_body"]
        assert "0" in body
        assert "6" in body

    def test_degree_level_selection(self):
        """Degree level is a Selection with 7 HEC-standard values."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["degree_level"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        field = _get_field(model, "degree_level")
        assert field is not None, "degree_level field not found"
        assert field["type"] == "Selection"
        assert field["string"] == "Degree Level"
        selection = field["selection"]
        assert len(selection) == 7
        keys = [s[0] for s in selection]
        assert "matriculation" in keys
        assert "intermediate" in keys
        assert "bachelor" in keys
        assert "master" in keys
        assert "mphil" in keys
        assert "phd" in keys
        assert "postdoc" in keys

    def test_recognition_status_selection(self):
        """Recognition status is a Selection with 4 values and default."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["recognition_status"])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        field = _get_field(model, "recognition_status")
        assert field is not None, "recognition_status field not found"
        assert field["type"] == "Selection"
        assert field["string"] == "Recognition Status"
        assert field["default"] == "recognized"
        selection = field["selection"]
        assert len(selection) == 4
        keys = [s[0] for s in selection]
        assert "recognized" in keys
        assert "chartered" in keys
        assert "affiliated" in keys
        assert "not_recognized" in keys


# ===========================================================================
# TestCurrencyAndTax
# ===========================================================================


class TestCurrencyAndTax:
    """extra_data_files contains pk_currency_data.xml path."""

    def test_extra_data_files_contains_pkr(self):
        """Spec with localization=pk sets extra_data_files with PKR currency path."""
        spec = _make_spec(
            models=[_make_model()],
            localization="pk",
        )
        result = _process(spec)
        extra = result.get("extra_data_files", [])
        assert "data/pk_currency_data.xml" in extra

    def test_extra_data_files_preserves_existing(self):
        """Existing extra_data_files entries are preserved."""
        spec = _make_spec(
            models=[_make_model()],
            localization="pk",
            extra_data_files=["data/existing.xml"],
        )
        result = _process(spec)
        extra = result.get("extra_data_files", [])
        assert "data/existing.xml" in extra
        assert "data/pk_currency_data.xml" in extra

    def test_no_extra_data_files_for_non_pk(self):
        """Non-pk spec does not get extra_data_files."""
        spec = _make_spec(
            models=[_make_model()],
            localization="us",
        )
        result = _process(spec)
        assert "extra_data_files" not in result


# ===========================================================================
# TestImmutability
# ===========================================================================


class TestImmutability:
    """Input spec is never mutated."""

    def test_input_spec_not_mutated(self):
        """Processing does not modify the input spec dict."""
        original_model = _make_model(
            name="test.student",
            pk_fields=["cnic", "phone", "gpa", "credit_hours"],
        )
        spec = _make_spec(
            models=[original_model],
            localization="pk",
        )
        spec_copy = copy.deepcopy(spec)
        _process(spec)
        assert spec == spec_copy, "Input spec was mutated"

    def test_input_model_fields_not_mutated(self):
        """Original model's fields list is not modified."""
        original_fields = [
            {"name": "name", "type": "Char", "required": True},
        ]
        model = _make_model(
            fields=original_fields,
            pk_fields=["cnic"],
        )
        spec = _make_spec(models=[model], localization="pk")
        original_field_count = len(model["fields"])
        _process(spec)
        assert len(model["fields"]) == original_field_count, (
            "Original model's fields list was mutated"
        )

    def test_output_is_new_dict(self):
        """Output spec is a different dict object from input."""
        spec = _make_spec(
            models=[_make_model(pk_fields=["cnic"])],
            localization="pk",
        )
        result = _process(spec)
        assert result is not spec

    def test_multiple_models_independence(self):
        """Processing multiple models does not cross-contaminate."""
        spec = _make_spec(
            models=[
                _make_model(name="test.student", pk_fields=["cnic"]),
                _make_model(name="test.teacher", pk_fields=["ntn"]),
            ],
            localization="pk",
        )
        result = _process(spec)
        student = result["models"][0]
        teacher = result["models"][1]
        assert _get_field(student, "cnic") is not None
        assert _get_field(student, "ntn") is None
        assert _get_field(teacher, "ntn") is not None
        assert _get_field(teacher, "cnic") is None


# ===========================================================================
# TestMultipleFieldsCombined
# ===========================================================================


class TestMultipleFieldsCombined:
    """Test that multiple pk_fields on one model all get injected correctly."""

    def test_all_fields_injected(self):
        """Model with all pk_fields gets all fields injected."""
        spec = _make_spec(
            models=[_make_model(pk_fields=[
                "cnic", "phone", "ntn", "strn", "hec_registration",
                "gpa", "credit_hours", "degree_level", "recognition_status",
            ])],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        expected_fields = [
            "cnic", "phone_pk", "ntn", "strn", "hec_registration_no",
            "gpa", "credit_hours", "degree_level", "recognition_status",
        ]
        for fname in expected_fields:
            assert _get_field(model, fname) is not None, (
                f"Expected field '{fname}' not found"
            )

    def test_sql_constraints_all_prefixed(self):
        """All SQL constraints are prefixed with model variable name."""
        spec = _make_spec(
            models=[_make_model(
                name="test.entity",
                pk_fields=["cnic", "ntn", "strn", "hec_registration"],
            )],
            localization="pk",
        )
        result = _process(spec)
        model = result["models"][0]
        sql_names = [c["name"] for c in model.get("sql_constraints", [])]
        for name in sql_names:
            assert name.startswith("test_entity_"), (
                f"SQL constraint '{name}' not prefixed with model var"
            )


# ===========================================================================
# TestPakistanE2E -- End-to-end integration tests
# ===========================================================================


def _make_e2e_spec(
    localization: str | None = None,
    pk_models: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a full spec suitable for render_module() E2E testing."""
    models = pk_models or [
        {
            "name": "university.student",
            "description": "University Student",
            "fields": [
                {"name": "name", "type": "Char", "required": True},
                {"name": "email", "type": "Char"},
            ],
            "pk_fields": ["cnic", "phone", "gpa"],
        },
        {
            "name": "university.company",
            "description": "University Company",
            "fields": [
                {"name": "name", "type": "Char", "required": True},
            ],
            "pk_fields": ["ntn", "degree_level"],
        },
    ]
    spec: dict[str, Any] = {
        "module_name": "test_pk_module",
        "module_title": "Test PK Module",
        "summary": "Test module for Pakistan E2E",
        "author": "Test Author",
        "website": "https://test.example.com",
        "license": "LGPL-3",
        "category": "Education",
        "odoo_version": "17.0",
        "depends": ["base"],
        "application": True,
        "models": models,
    }
    if localization is not None:
        spec["localization"] = localization
    return spec


class TestPakistanE2E:
    """End-to-end integration tests: full module render with Pakistan localization."""

    def _render(self, spec: dict[str, Any]) -> tuple[Path, list[Path]]:
        """Render a spec to a temp directory and return (module_dir, files)."""
        from amil_utils.renderer import render_module, get_template_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            files, warnings = render_module(
                spec, get_template_dir(), output_dir, no_context7=True
            )
            module_dir = output_dir / spec["module_name"]
            # Read results before temp dir is cleaned up
            results: dict[str, str] = {}
            for f in files:
                if f.exists():
                    results[str(f.relative_to(module_dir))] = f.read_text(
                        encoding="utf-8"
                    )
            return module_dir, files, results

    def test_pkr_currency_xml_exists(self):
        """data/pk_currency_data.xml exists and contains base.PKR record."""
        spec = _make_e2e_spec(localization="pk")
        _module_dir, _files, results = self._render(spec)
        pkr_path = "data/pk_currency_data.xml"
        assert pkr_path in results, (
            f"PKR currency file not found in output. Keys: {list(results.keys())}"
        )
        content = results[pkr_path]
        assert 'id="base.PKR"' in content
        assert 'model="res.currency"' in content
        assert 'forcecreate="false"' in content
        assert 'eval="True"' in content

    def test_manifest_includes_pkr_data_file(self):
        """__manifest__.py data list includes data/pk_currency_data.xml."""
        spec = _make_e2e_spec(localization="pk")
        _module_dir, _files, results = self._render(spec)
        manifest = results.get("__manifest__.py", "")
        assert "data/pk_currency_data.xml" in manifest, (
            "PKR data file not in manifest data list"
        )

    def test_cnic_constraint_with_api_constrains(self):
        """Generated model .py has _check_cnic with @api.constrains('cnic')."""
        spec = _make_e2e_spec(localization="pk")
        _module_dir, _files, results = self._render(spec)
        model_py = results.get("models/university_student.py", "")
        assert "@api.constrains" in model_py, "Missing @api.constrains decorator"
        assert "_check_cnic" in model_py, "Missing _check_cnic method"
        # Should have @api.constrains("cnic") before _check_cnic
        lines = model_py.splitlines()
        constrains_line = None
        check_line = None
        for i, line in enumerate(lines):
            if '@api.constrains("cnic")' in line:
                constrains_line = i
            if "def _check_cnic" in line:
                check_line = i
                break
        assert constrains_line is not None, "No @api.constrains('cnic') found"
        assert check_line is not None, "No _check_cnic method found"
        assert constrains_line < check_line, (
            "@api.constrains must be before _check_cnic"
        )

    def test_cnic_normalization_in_generated_code(self):
        """Generated model contains re.sub normalization for CNIC."""
        spec = _make_e2e_spec(localization="pk")
        _module_dir, _files, results = self._render(spec)
        model_py = results.get("models/university_student.py", "")
        assert "re.sub(r'[^0-9]', '', rec.cnic)" in model_py, (
            "CNIC normalization with re.sub not found"
        )

    def test_phone_phonenumbers_import_pattern(self):
        """Generated model contains phonenumbers try/except import pattern."""
        spec = _make_e2e_spec(localization="pk")
        _module_dir, _files, results = self._render(spec)
        model_py = results.get("models/university_student.py", "")
        assert "import phonenumbers" in model_py
        assert "ImportError" in model_py

    def test_gpa_constraint_range(self):
        """Generated model contains GPA 0.00-4.00 constraint."""
        spec = _make_e2e_spec(localization="pk")
        _module_dir, _files, results = self._render(spec)
        model_py = results.get("models/university_student.py", "")
        assert "_check_gpa" in model_py, "Missing _check_gpa method"
        assert "4.0" in model_py, "Missing GPA upper bound 4.0"

    def test_ntn_and_degree_level_fields(self):
        """Generated model contains NTN field and degree_level Selection."""
        spec = _make_e2e_spec(localization="pk")
        _module_dir, _files, results = self._render(spec)
        company_py = results.get("models/university_company.py", "")
        assert "ntn" in company_py, "NTN field not found in generated model"
        assert "degree_level" in company_py, "degree_level field not found"
        # degree_level should render as Selection
        assert "Selection" in company_py, "degree_level should be Selection type"
        # Check some selection values
        assert "matriculation" in company_py
        assert "phd" in company_py

    def test_sql_constraints_with_model_prefix(self):
        """Generated model SQL constraints include model-prefixed unique constraints."""
        spec = _make_e2e_spec(localization="pk")
        _module_dir, _files, results = self._render(spec)
        student_py = results.get("models/university_student.py", "")
        assert "university_student_cnic_unique" in student_py, (
            "Model-prefixed CNIC unique constraint not found"
        )

    def test_needs_api_import(self):
        """Generated model with pk_* constraints imports api from odoo."""
        spec = _make_e2e_spec(localization="pk")
        _module_dir, _files, results = self._render(spec)
        student_py = results.get("models/university_student.py", "")
        assert "from odoo import api," in student_py, (
            "api import missing -- needs_api should be True for pk_* constraints"
        )

    def test_no_localization_renders_normally(self):
        """Spec without localization key renders identically to before (no regression)."""
        spec = _make_e2e_spec(localization=None)
        _module_dir, _files, results = self._render(spec)
        # No PKR data file
        assert "data/pk_currency_data.xml" not in results, (
            "PKR file should not exist without localization"
        )
        # No pk_* constraint methods in model
        student_py = results.get("models/university_student.py", "")
        assert "_check_cnic" not in student_py, (
            "CNIC constraint should not exist without localization"
        )
        assert "phonenumbers" not in student_py, (
            "phonenumbers should not appear without localization"
        )
        # Manifest should not include pk_currency_data.xml
        manifest = results.get("__manifest__.py", "")
        assert "pk_currency_data" not in manifest
