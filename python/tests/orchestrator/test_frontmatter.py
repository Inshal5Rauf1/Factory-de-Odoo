"""Tests for orchestrator frontmatter module."""
from __future__ import annotations

from pathlib import Path

import pytest

from amil_utils.orchestrator.frontmatter import (
    FRONTMATTER_SCHEMAS,
    extract_frontmatter,
    parse_must_haves_block,
    reconstruct_frontmatter,
    splice_frontmatter,
    validate_frontmatter,
)


# ── extract_frontmatter ────────────────────────────────────────────────────


class TestExtractFrontmatter:
    def test_basic_extraction(self) -> None:
        content = "---\nphase: 1.0\nstatus: executing\n---\n\n# Body"
        fm = extract_frontmatter(content)
        assert fm["phase"] == "1.0"
        assert fm["status"] == "executing"

    def test_empty_when_no_frontmatter(self) -> None:
        assert extract_frontmatter("# Just a heading\n") == {}

    def test_inline_array(self) -> None:
        content = "---\ntags: [a, b, c]\n---\n"
        fm = extract_frontmatter(content)
        assert fm["tags"] == ["a", "b", "c"]

    def test_multiline_array(self) -> None:
        content = "---\nfiles:\n  - main.py\n  - test.py\n---\n"
        fm = extract_frontmatter(content)
        assert fm["files"] == ["main.py", "test.py"]

    def test_nested_object(self) -> None:
        content = "---\nconfig:\n  model: opus\n  tier: quality\n---\n"
        fm = extract_frontmatter(content)
        assert fm["config"]["model"] == "opus"
        assert fm["config"]["tier"] == "quality"

    def test_quoted_values(self) -> None:
        content = '---\nname: "hello world"\n---\n'
        fm = extract_frontmatter(content)
        assert fm["name"] == "hello world"

    def test_empty_value_creates_nested(self) -> None:
        content = "---\nparent:\n  child: value\n---\n"
        fm = extract_frontmatter(content)
        assert fm["parent"]["child"] == "value"

    def test_complex_frontmatter(self) -> None:
        content = (
            "---\nphase: 12A.1\nplan: core-setup\ntype: implementation\n"
            "wave: 1\ndepends_on: []\nfiles_modified: [src/main.py, tests/test_main.py]\n"
            "autonomous: true\n---\n\n# Plan\n"
        )
        fm = extract_frontmatter(content)
        assert fm["phase"] == "12A.1"
        assert fm["autonomous"] == "true"
        assert isinstance(fm["files_modified"], list)
        assert len(fm["files_modified"]) == 2


# ── reconstruct_frontmatter ─────────────────────────────────────────────────


class TestReconstructFrontmatter:
    def test_simple_key_values(self) -> None:
        result = reconstruct_frontmatter({"phase": "1.0", "status": "active"})
        assert "phase: 1.0" in result
        assert "status: active" in result

    def test_inline_array(self) -> None:
        result = reconstruct_frontmatter({"tags": ["a", "b"]})
        assert "tags: [a, b]" in result

    def test_empty_array(self) -> None:
        result = reconstruct_frontmatter({"items": []})
        assert "items: []" in result

    def test_long_array_uses_multiline(self) -> None:
        result = reconstruct_frontmatter(
            {"files": ["very/long/path/one.py", "very/long/path/two.py", "three.py", "four.py"]}
        )
        assert "  - very/long/path/one.py" in result

    def test_nested_object(self) -> None:
        result = reconstruct_frontmatter({"config": {"model": "opus"}})
        assert "config:" in result
        assert "  model: opus" in result

    def test_skips_none_values(self) -> None:
        result = reconstruct_frontmatter({"a": "b", "c": None})
        assert "a: b" in result
        assert "c:" not in result

    def test_quotes_colons(self) -> None:
        result = reconstruct_frontmatter({"url": "http://example.com"})
        assert '"http://example.com"' in result

    def test_roundtrip(self) -> None:
        original = {"phase": "1.0", "tags": ["a", "b"], "status": "active"}
        yaml_str = reconstruct_frontmatter(original)
        content = f"---\n{yaml_str}\n---\n\n# Body"
        parsed = extract_frontmatter(content)
        assert parsed["phase"] == "1.0"
        assert parsed["tags"] == ["a", "b"]


# ── splice_frontmatter ──────────────────────────────────────────────────────


class TestSpliceFrontmatter:
    def test_replaces_existing(self) -> None:
        content = "---\nold: value\n---\n\n# Body text"
        result = splice_frontmatter(content, {"new": "data"})
        assert "new: data" in result
        assert "# Body text" in result
        assert "old: value" not in result

    def test_adds_to_content_without_frontmatter(self) -> None:
        content = "# Just a heading"
        result = splice_frontmatter(content, {"phase": "1.0"})
        assert result.startswith("---\n")
        assert "phase: 1.0" in result
        assert "# Just a heading" in result


# ── parse_must_haves_block ──────────────────────────────────────────────────


class TestParseMustHavesBlock:
    def test_extracts_artifacts(self) -> None:
        content = (
            "---\nmust_haves:\n    artifacts:\n"
            '      - path: "src/main.py"\n'
            "        provides: core logic\n"
            '      - path: "tests/test_main.py"\n'
            "        provides: test coverage\n"
            "---\n"
        )
        items = parse_must_haves_block(content, "artifacts")
        assert len(items) == 2
        assert items[0]["path"] == "src/main.py"

    def test_returns_empty_for_no_block(self) -> None:
        content = "---\nphase: 1.0\n---\n"
        assert parse_must_haves_block(content, "artifacts") == []

    def test_returns_empty_for_no_frontmatter(self) -> None:
        assert parse_must_haves_block("# No frontmatter", "artifacts") == []

    def test_simple_string_items(self) -> None:
        content = (
            "---\nmust_haves:\n    truths:\n"
            '      - "First truth"\n'
            '      - "Second truth"\n'
            "---\n"
        )
        items = parse_must_haves_block(content, "truths")
        assert len(items) == 2
        assert items[0] == "First truth"


# ── validate_frontmatter ────────────────────────────────────────────────────


class TestValidateFrontmatter:
    def test_valid_plan(self) -> None:
        fm = {
            "phase": "1.0",
            "plan": "setup",
            "type": "implementation",
            "wave": "1",
            "depends_on": [],
            "files_modified": [],
            "autonomous": "true",
            "must_haves": {},
        }
        result = validate_frontmatter(fm, "plan")
        assert result["valid"] is True
        assert result["missing"] == []

    def test_invalid_plan_missing_fields(self) -> None:
        fm = {"phase": "1.0"}
        result = validate_frontmatter(fm, "plan")
        assert result["valid"] is False
        assert "plan" in result["missing"]

    def test_unknown_schema(self) -> None:
        with pytest.raises(ValueError, match="Unknown schema"):
            validate_frontmatter({}, "nonexistent")


# ── FRONTMATTER_SCHEMAS ─────────────────────────────────────────────────────


class TestSchemas:
    def test_plan_schema_exists(self) -> None:
        assert "plan" in FRONTMATTER_SCHEMAS
        assert "required" in FRONTMATTER_SCHEMAS["plan"]

    def test_summary_schema_exists(self) -> None:
        assert "summary" in FRONTMATTER_SCHEMAS

    def test_verification_schema_exists(self) -> None:
        assert "verification" in FRONTMATTER_SCHEMAS
