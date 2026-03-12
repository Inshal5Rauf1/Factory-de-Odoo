"""Stub-zone-aware merge for preserving filled implementations.

Provides:
- ``extract_filled_stubs`` — scans source lines for BUSINESS LOGIC
  zones that have been filled with real implementations (not just
  ``pass`` or TODO comments).
- ``inject_stubs_into`` — transplants filled implementations from
  a previous file into a re-rendered structural template, matching
  by method name (position-independent).

These are **pure functions** operating on string data only.
"""

from __future__ import annotations

import re
from typing import Any

from odoo_gen_utils.logic_writer.stub_detector import _find_stub_zones


def _is_unfilled(content_lines: list[str]) -> bool:
    """Return True if stub zone content is just ``pass`` or TODO comments.

    A zone is considered unfilled if after stripping whitespace and
    comments, only ``pass`` statements or nothing remains.
    """
    stripped = []
    for line in content_lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            # Check for TODO/FIXME/XXX patterns
            if re.search(r"\b(TODO|FIXME|XXX|HACK)\b", s, re.IGNORECASE):
                continue
            stripped.append(s)
        else:
            stripped.append(s)

    # If nothing remains after filtering, it's unfilled
    if not stripped:
        return True

    # If only "pass" remains, it's unfilled
    if all(s == "pass" for s in stripped):
        return True

    return False


def _find_method_name_above(source_lines: list[str], start_line: int) -> str | None:
    """Scan backward from *start_line* (1-based) to find the ``def`` line.

    Returns the method name or None if no def found within 10 lines.
    """
    # start_line is the line of the START marker (1-based)
    # Scan upward from start_line - 1 (the line above the marker)
    for offset in range(1, 11):
        idx = start_line - 1 - offset  # 0-based
        if idx < 0:
            break
        line = source_lines[idx].strip()
        match = re.match(r"def\s+(\w+)\s*\(", line)
        if match:
            return match.group(1)
    return None


def extract_filled_stubs(source_lines: list[str]) -> list[dict[str, Any]]:
    """Find BUSINESS LOGIC zones with real implementations.

    For each zone found via ``_find_stub_zones()``:
    1. Extract content lines between markers (exclusive of markers).
    2. Check if content is unfilled (just ``pass`` or TODO).
    3. Scan backward to find the method name from the ``def`` line.

    Returns a list of dicts with:
    - ``method_name``: str -- the Python method name
    - ``content_lines``: list[str] -- the implementation lines
    - ``start_line``: int -- 1-based line of the START marker
    - ``end_line``: int -- 1-based line of the END marker

    Unfilled zones (pass/TODO only) are skipped.
    """
    zones = _find_stub_zones(source_lines)
    result: list[dict[str, Any]] = []

    for zone in zones:
        start = zone["start_line"]  # 1-based, line of START marker
        end = zone["end_line"]  # 1-based, line of END marker

        # Extract content between markers (exclusive of markers themselves)
        # start is 1-based, so source_lines[start] is the line AFTER the marker
        content_lines = source_lines[start: end - 1]  # 0-based slice

        if _is_unfilled(content_lines):
            continue

        method_name = _find_method_name_above(source_lines, start)
        if method_name is None:
            continue  # Can't identify the method

        result.append({
            "method_name": method_name,
            "content_lines": content_lines,
            "start_line": start,
            "end_line": end,
        })

    return result


def inject_stubs_into(new_structure: str, filled_stubs: list[dict[str, Any]]) -> str:
    """Transplant filled implementations into a re-rendered template.

    Parses *new_structure* into lines, finds BUSINESS LOGIC zones,
    matches each zone to a filled stub by method name, and replaces
    the zone content with the filled implementation.

    Unmatched zones (new methods not previously implemented) are left
    as-is with their original content.

    Args:
        new_structure: The re-rendered file content as a string.
        filled_stubs: Output from ``extract_filled_stubs()`` on the
            previous version of the file.

    Returns:
        Merged file content as a string with implementations preserved.
    """
    lines = new_structure.splitlines()
    zones = _find_stub_zones(lines)

    if not zones:
        return new_structure

    # Build lookup: method_name -> filled content
    stub_lookup: dict[str, list[str]] = {}
    for stub in filled_stubs:
        stub_lookup[stub["method_name"]] = stub["content_lines"]

    # Process zones in reverse order to preserve line indices
    for zone in reversed(zones):
        start = zone["start_line"]  # 1-based, line of START marker
        end = zone["end_line"]  # 1-based, line of END marker

        method_name = _find_method_name_above(lines, start)
        if method_name is None:
            continue

        if method_name not in stub_lookup:
            continue  # No matching filled stub -- leave as-is

        # Replace content between markers (exclusive)
        # Lines[start] through lines[end-2] are the content (0-based)
        filled_content = stub_lookup[method_name]
        lines[start: end - 1] = filled_content

    return "\n".join(lines)
