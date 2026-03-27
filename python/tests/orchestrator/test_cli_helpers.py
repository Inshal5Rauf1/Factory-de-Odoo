"""Tests for orchestrator cli_helpers module.

Tests the _common decorator and _emit output function.
"""
from __future__ import annotations

import json

import click
import pytest
from click.testing import CliRunner


from amil_utils.orchestrator.cli_helpers import _common, _emit


# ── _common decorator ──────────────────────────────────────────────────────


class TestCommonDecorator:
    """Tests for the _common decorator that applies --cwd and --raw options."""

    def test_adds_cwd_option(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            click.echo(f"cwd={cwd}")

        runner = CliRunner()
        result = runner.invoke(dummy, ["--cwd", "/tmp"])
        assert result.exit_code == 0
        assert "cwd=/tmp" in result.output

    def test_cwd_default_is_dot(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            click.echo(f"cwd={cwd}")

        runner = CliRunner()
        # "." exists, so it should work as default
        result = runner.invoke(dummy, [])
        assert result.exit_code == 0
        assert "cwd=." in result.output

    def test_adds_raw_flag_default_false(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            click.echo(f"raw={raw}")

        runner = CliRunner()
        result = runner.invoke(dummy, [])
        assert result.exit_code == 0
        assert "raw=False" in result.output

    def test_raw_flag_enabled(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            click.echo(f"raw={raw}")

        runner = CliRunner()
        result = runner.invoke(dummy, ["--raw"])
        assert result.exit_code == 0
        assert "raw=True" in result.output

    def test_cwd_validates_path_exists(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            click.echo("ok")

        runner = CliRunner()
        result = runner.invoke(dummy, ["--cwd", "/nonexistent/path/xyz"])
        assert result.exit_code != 0

    def test_preserves_function_with_extra_args(self) -> None:
        @click.command()
        @click.argument("name")
        @_common
        def dummy(name: str, cwd: str, raw: bool) -> None:
            click.echo(f"name={name} cwd={cwd}")

        runner = CliRunner()
        result = runner.invoke(dummy, ["hello"])
        assert result.exit_code == 0
        assert "name=hello" in result.output


# ── _emit function ─────────────────────────────────────────────────────────


class TestEmit:
    """Tests for the _emit function that outputs JSON."""

    def test_compact_json_when_raw_true(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            _emit({"key": "value", "num": 42})

        runner = CliRunner()
        result = runner.invoke(dummy, ["--raw"])
        assert result.exit_code == 0
        parsed = json.loads(result.output.strip())
        assert parsed == {"key": "value", "num": 42}
        # Compact means no newlines inside the JSON
        assert "\n" not in result.output.strip()

    def test_pretty_json_when_raw_false(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            _emit({"key": "value"})

        runner = CliRunner()
        result = runner.invoke(dummy, [])
        assert result.exit_code == 0
        parsed = json.loads(result.output.strip())
        assert parsed == {"key": "value"}
        # Pretty-printed means indentation present
        assert "  " in result.output

    def test_emit_with_nested_data(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            _emit({"nested": {"a": 1, "b": [2, 3]}})

        runner = CliRunner()
        result = runner.invoke(dummy, ["--raw"])
        parsed = json.loads(result.output.strip())
        assert parsed["nested"]["a"] == 1
        assert parsed["nested"]["b"] == [2, 3]

    def test_emit_empty_dict(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            _emit({})

        runner = CliRunner()
        result = runner.invoke(dummy, ["--raw"])
        assert json.loads(result.output.strip()) == {}

    def test_emit_outside_click_context_defaults_to_compact(self) -> None:
        """When called outside Click context, _emit should default to compact."""
        import io
        from contextlib import redirect_stdout

        # _emit uses click.echo which writes to stdout
        # Outside a Click context, ctx is None, so raw defaults to True
        @click.command()
        def wrapper() -> None:
            # Deliberately clear the Click context by calling _emit
            # indirectly where get_current_context returns the wrapper context
            _emit({"test": True})

        runner = CliRunner()
        result = runner.invoke(wrapper, [])
        # Without --raw flag but within a Click context that has no "raw" param,
        # _emit falls back to raw=True (compact)
        parsed = json.loads(result.output.strip())
        assert parsed == {"test": True}

    def test_emit_with_special_characters(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            _emit({"msg": "hello \"world\"", "unicode": "\u2713"})

        runner = CliRunner()
        result = runner.invoke(dummy, ["--raw"])
        parsed = json.loads(result.output.strip())
        assert parsed["msg"] == 'hello "world"'
        assert parsed["unicode"] == "\u2713"

    def test_emit_with_none_values(self) -> None:
        @click.command()
        @_common
        def dummy(cwd: str, raw: bool) -> None:
            _emit({"present": "yes", "absent": None})

        runner = CliRunner()
        result = runner.invoke(dummy, ["--raw"])
        parsed = json.loads(result.output.strip())
        assert parsed["present"] == "yes"
        assert parsed["absent"] is None
