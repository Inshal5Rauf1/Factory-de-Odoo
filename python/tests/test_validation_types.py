"""Tests for validation dataclasses (types.py).

Verifies immutability (frozen=True), correct defaults, and field access.
"""

from __future__ import annotations

import dataclasses

import pytest

from amil_utils.validation.types import (
    InstallResult,
    TestResult,
    ValidationReport,
    Violation,
)


class TestViolation:
    """Tests for the Violation dataclass."""

    def test_violation_creation(self) -> None:
        """Violation with all fields creates correctly."""
        v = Violation(
            file="model.py",
            line=10,
            column=0,
            rule_code="C8101",
            symbol="manifest-required-author",
            severity="convention",
            message="Author is required in manifest",
        )
        assert v.file == "model.py"
        assert v.line == 10
        assert v.column == 0
        assert v.rule_code == "C8101"
        assert v.symbol == "manifest-required-author"
        assert v.severity == "convention"
        assert v.message == "Author is required in manifest"
        assert v.suggestion == ""  # default

    def test_violation_with_suggestion(self) -> None:
        """Violation with explicit suggestion field."""
        v = Violation(
            file="model.py",
            line=5,
            column=0,
            rule_code="W8105",
            symbol="attribute-deprecated",
            severity="warning",
            message="Use of deprecated attribute 'attrs'",
            suggestion="Replace attrs with inline expressions",
        )
        assert v.suggestion == "Replace attrs with inline expressions"

    def test_violation_immutability(self) -> None:
        """Assigning to a frozen dataclass field raises FrozenInstanceError."""
        v = Violation(
            file="model.py",
            line=10,
            column=0,
            rule_code="C8101",
            symbol="manifest-required-author",
            severity="convention",
            message="msg",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.line = 20  # type: ignore[misc]


class TestTestResult:
    """Tests for the TestResult dataclass."""

    def test_test_result_creation(self) -> None:
        """TestResult with required fields and defaults."""
        tr = TestResult(test_name="test_create", passed=True)
        assert tr.test_name == "test_create"
        assert tr.passed is True
        assert tr.error_message == ""
        assert tr.duration_seconds == 0.0

    def test_test_result_with_error(self) -> None:
        """TestResult with explicit error message and duration."""
        tr = TestResult(
            test_name="test_fail",
            passed=False,
            error_message="AssertionError: 1 != 2",
            duration_seconds=1.5,
        )
        assert tr.passed is False
        assert tr.error_message == "AssertionError: 1 != 2"
        assert tr.duration_seconds == 1.5

    def test_test_result_immutability(self) -> None:
        """TestResult is frozen."""
        tr = TestResult(test_name="test_x", passed=True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            tr.passed = False  # type: ignore[misc]


class TestInstallResult:
    """Tests for the InstallResult dataclass."""

    def test_install_result_creation(self) -> None:
        """InstallResult creates correctly."""
        ir = InstallResult(success=True, log_output="OK", error_message="")
        assert ir.success is True
        assert ir.log_output == "OK"
        assert ir.error_message == ""

    def test_install_result_failure(self) -> None:
        """InstallResult with failure."""
        ir = InstallResult(
            success=False,
            log_output="install log...",
            error_message="Module not found",
        )
        assert ir.success is False
        assert ir.error_message == "Module not found"

    def test_install_result_immutability(self) -> None:
        """InstallResult is frozen."""
        ir = InstallResult(success=True, log_output="", error_message="")
        with pytest.raises(dataclasses.FrozenInstanceError):
            ir.success = False  # type: ignore[misc]


class TestValidationReport:
    """Tests for the ValidationReport dataclass."""

    def test_validation_report_creation(self) -> None:
        """ValidationReport with all sections populated."""
        v = Violation(
            file="model.py",
            line=10,
            column=0,
            rule_code="C8101",
            symbol="manifest-required-author",
            severity="convention",
            message="msg",
        )
        ir = InstallResult(success=True, log_output="", error_message="")
        tr = TestResult(test_name="test_create", passed=True)
        report = ValidationReport(
            module_name="test_module",
            pylint_violations=(v,),
            install_result=ir,
            test_results=(tr,),
            diagnosis=("Check manifest",),
            docker_available=True,
        )
        assert report.module_name == "test_module"
        assert len(report.pylint_violations) == 1
        assert report.install_result is not None
        assert report.install_result.success is True
        assert len(report.test_results) == 1
        assert len(report.diagnosis) == 1
        assert report.docker_available is True

    def test_validation_report_empty(self) -> None:
        """ValidationReport with module_name only uses defaults."""
        report = ValidationReport(module_name="test")
        assert report.module_name == "test"
        assert report.pylint_violations == ()
        assert report.install_result is None
        assert report.test_results == ()
        assert report.diagnosis == ()
        assert report.docker_available is True

    def test_validation_report_install_defaults_to_none(self) -> None:
        """install_result defaults to None (not run)."""
        report = ValidationReport(module_name="test")
        assert report.install_result is None

    def test_validation_report_immutability(self) -> None:
        """ValidationReport is frozen."""
        report = ValidationReport(module_name="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.module_name = "other"  # type: ignore[misc]


class TestResult_:
    """Tests for the Result[T] generic type."""

    def test_result_ok_creates_success(self) -> None:
        """Result.ok(data) creates Result with success=True, data=data, errors=()."""
        from amil_utils.validation.types import Result

        r = Result.ok("hello")
        assert r.success is True
        assert r.data == "hello"
        assert r.errors == ()

    def test_result_fail_creates_failure(self) -> None:
        """Result.fail('msg') creates Result with success=False, data=None, errors=('msg',)."""
        from amil_utils.validation.types import Result

        r = Result.fail("something went wrong")
        assert r.success is False
        assert r.data is None
        assert r.errors == ("something went wrong",)

    def test_result_fail_multiple_errors(self) -> None:
        """Result.fail('a', 'b') stores multiple errors as tuple."""
        from amil_utils.validation.types import Result

        r = Result.fail("a", "b")
        assert r.errors == ("a", "b")
        assert r.success is False

    def test_result_is_frozen(self) -> None:
        """Result is frozen -- assigning to .success raises FrozenInstanceError."""
        from amil_utils.validation.types import Result

        r = Result.ok(42)
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.success = False  # type: ignore[misc]

    def test_result_generic_type_annotation(self) -> None:
        """Result[tuple[Violation, ...]] type annotation works."""
        from amil_utils.validation.types import Result

        v = Violation(
            file="m.py", line=1, column=0, rule_code="C0001",
            symbol="test", severity="convention", message="msg",
        )
        r: Result[tuple[Violation, ...]] = Result.ok((v,))
        assert r.success is True
        assert len(r.data) == 1  # type: ignore[arg-type]

    def test_result_errors_default_empty_tuple(self) -> None:
        """Result with no errors has empty tuple (not None)."""
        from amil_utils.validation.types import Result

        r = Result.ok("data")
        assert r.errors == ()
        assert isinstance(r.errors, tuple)

    def test_result_ok_none_is_valid(self) -> None:
        """Result.ok(None) is valid (success=True, data=None)."""
        from amil_utils.validation.types import Result

        r = Result.ok(None)
        assert r.success is True
        assert r.data is None
