"""Tests for iterative stub-zone-aware merge (merge.py)."""

from __future__ import annotations

import pytest

from amil_utils.iterative.merge import (
    extract_filled_stubs,
    inject_stubs_into,
)


# ---------------------------------------------------------------------------
# extract_filled_stubs tests
# ---------------------------------------------------------------------------


class TestExtractFilledStubs:
    """extract_filled_stubs identifies method names and content from filled zones."""

    def test_extracts_method_name_and_content(self) -> None:
        source = (
            "class FeeInvoice:\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        for rec in self:\n"
            "            rec.total = rec.amount * rec.qty\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        result = extract_filled_stubs(source.splitlines())
        assert len(result) == 1
        assert result[0]["method_name"] == "_compute_total"
        assert "for rec in self:" in "\n".join(result[0]["content_lines"])

    def test_skips_unfilled_zones_pass(self) -> None:
        source = (
            "class FeeInvoice:\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        pass\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        result = extract_filled_stubs(source.splitlines())
        assert len(result) == 0

    def test_skips_unfilled_zones_todo(self) -> None:
        source = (
            "class FeeInvoice:\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        # TODO: implement business logic\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        result = extract_filled_stubs(source.splitlines())
        assert len(result) == 0

    def test_handles_multiple_zones(self) -> None:
        source = (
            "class FeeInvoice:\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        for rec in self:\n"
            "            rec.total = rec.amount * rec.qty\n"
            "        # --- BUSINESS LOGIC END ---\n"
            "\n"
            "    def _compute_tax(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        for rec in self:\n"
            "            rec.tax = rec.total * 0.1\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        result = extract_filled_stubs(source.splitlines())
        assert len(result) == 2
        names = {s["method_name"] for s in result}
        assert names == {"_compute_total", "_compute_tax"}

    def test_returns_empty_when_no_zones(self) -> None:
        source = "class FeeInvoice:\n    pass\n"
        result = extract_filled_stubs(source.splitlines())
        assert result == []

    def test_content_lines_exclude_markers(self) -> None:
        source = (
            "class FeeInvoice:\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        for rec in self:\n"
            "            rec.total = 42\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        result = extract_filled_stubs(source.splitlines())
        assert len(result) == 1
        for line in result[0]["content_lines"]:
            assert "BUSINESS LOGIC START" not in line
            assert "BUSINESS LOGIC END" not in line


# ---------------------------------------------------------------------------
# inject_stubs_into tests
# ---------------------------------------------------------------------------


class TestInjectStubs:
    """inject_stubs_into replaces stub zone content with filled implementations."""

    def test_replaces_stub_zone_content(self) -> None:
        new_structure = (
            "class FeeInvoice:\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        pass\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        filled_stubs = [{
            "method_name": "_compute_total",
            "content_lines": [
                "        for rec in self:",
                "            rec.total = rec.amount * rec.qty",
            ],
            "start_line": 3,
            "end_line": 5,
        }]
        result = inject_stubs_into(new_structure, filled_stubs)
        assert "rec.total = rec.amount * rec.qty" in result
        assert "pass" not in result.split("# --- BUSINESS LOGIC END ---")[0].split("# --- BUSINESS LOGIC START ---")[1]

    def test_matches_by_method_name(self) -> None:
        new_structure = (
            "class FeeInvoice:\n"
            "    def some_other_method(self):\n"
            "        return True\n"
            "\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        pass\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        filled_stubs = [{
            "method_name": "_compute_total",
            "content_lines": [
                "        for rec in self:",
                "            rec.total = 99",
            ],
            "start_line": 999,  # Different position; matches by name
            "end_line": 1001,
        }]
        result = inject_stubs_into(new_structure, filled_stubs)
        assert "rec.total = 99" in result

    def test_preserves_unmatched_zones(self) -> None:
        new_structure = (
            "class FeeInvoice:\n"
            "    def _compute_new_field(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        pass\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        filled_stubs = [{
            "method_name": "_compute_total",  # No match
            "content_lines": ["        for rec in self:", "            rec.total = 99"],
            "start_line": 3,
            "end_line": 5,
        }]
        result = inject_stubs_into(new_structure, filled_stubs)
        # Unmatched zone should keep its original content
        lines = result.splitlines()
        # Find the pass line between markers
        in_zone = False
        zone_content = []
        for line in lines:
            if "BUSINESS LOGIC START" in line:
                in_zone = True
                continue
            if "BUSINESS LOGIC END" in line:
                in_zone = False
                continue
            if in_zone:
                zone_content.append(line.strip())
        assert "pass" in zone_content

    def test_no_stub_zones_returns_unchanged(self) -> None:
        new_structure = "class FeeInvoice:\n    name = 'test'\n"
        filled_stubs = [{
            "method_name": "_compute_total",
            "content_lines": ["        for rec in self:", "            rec.total = 99"],
            "start_line": 3,
            "end_line": 5,
        }]
        result = inject_stubs_into(new_structure, filled_stubs)
        assert result == new_structure

    def test_handles_multiple_zones(self) -> None:
        new_structure = (
            "class FeeInvoice:\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        pass\n"
            "        # --- BUSINESS LOGIC END ---\n"
            "\n"
            "    def _compute_tax(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        pass\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )
        filled_stubs = [
            {
                "method_name": "_compute_total",
                "content_lines": ["        for rec in self:", "            rec.total = 42"],
                "start_line": 3,
                "end_line": 5,
            },
            {
                "method_name": "_compute_tax",
                "content_lines": ["        for rec in self:", "            rec.tax = 7"],
                "start_line": 8,
                "end_line": 10,
            },
        ]
        result = inject_stubs_into(new_structure, filled_stubs)
        assert "rec.total = 42" in result
        assert "rec.tax = 7" in result


class TestRoundTrip:
    """Extract from file A, inject into file B -> implementations preserved."""

    def test_round_trip_preserves_implementations(self) -> None:
        # File A: user has filled in business logic
        file_a = (
            "class FeeInvoice:\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        for rec in self:\n"
            "            rec.total = rec.amount * rec.qty\n"
            "        # --- BUSINESS LOGIC END ---\n"
            "\n"
            "    def _compute_tax(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        for rec in self:\n"
            "            rec.tax = rec.total * 0.18\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )

        # File B: re-rendered with new structure but empty stubs
        file_b = (
            "class FeeInvoice:\n"
            "    # New field added by re-render\n"
            "    discount = fields.Float()\n"
            "\n"
            "    def _compute_total(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        pass\n"
            "        # --- BUSINESS LOGIC END ---\n"
            "\n"
            "    def _compute_tax(self):\n"
            "        # --- BUSINESS LOGIC START ---\n"
            "        pass\n"
            "        # --- BUSINESS LOGIC END ---\n"
        )

        # Extract filled stubs from A, inject into B
        filled = extract_filled_stubs(file_a.splitlines())
        result = inject_stubs_into(file_b, filled)

        # Implementations from A should be in the merged output
        assert "rec.total = rec.amount * rec.qty" in result
        assert "rec.tax = rec.total * 0.18" in result
        # New structure from B should be preserved
        assert "discount = fields.Float()" in result
