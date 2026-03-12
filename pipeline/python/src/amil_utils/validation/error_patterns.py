"""Error pattern matching and diagnosis engine for Odoo validation logs.

Loads a library of common Odoo error patterns from a JSON data file and
matches them against log text to produce human-readable diagnosis strings
with actionable fix suggestions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from odoo_gen_utils.validation.log_parser import extract_traceback

# Module-level cache for loaded patterns
_CACHED_PATTERNS: tuple[dict, ...] | None = None

_DATA_FILE = Path(__file__).parent / "data" / "error_patterns.json"


def load_error_patterns() -> tuple[dict, ...]:
    """Load and return error patterns from the JSON data file.

    Patterns are cached after the first load to avoid repeated file I/O.

    Returns:
        Tuple of pattern dicts, each with keys: id, regex, context_regex,
        explanation, suggestion, severity.
    """
    global _CACHED_PATTERNS  # noqa: PLW0603

    if _CACHED_PATTERNS is not None:
        return _CACHED_PATTERNS

    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    _CACHED_PATTERNS = tuple(raw)
    return _CACHED_PATTERNS


def diagnose_errors(
    log_text: str,
    patterns: tuple[dict, ...] | None = None,
) -> tuple[str, ...]:
    """Match Odoo error log text against the pattern library.

    For each matching pattern, returns a formatted diagnosis string with
    the severity, explanation, and suggested fix. If no patterns match
    but a traceback is found, returns the raw traceback text. If no
    patterns match and no traceback is found, returns an empty tuple.

    Args:
        log_text: The log/error text to diagnose.
        patterns: Optional pattern library override. If None, loads
            from the default JSON data file.

    Returns:
        Tuple of diagnosis strings. Empty tuple if no matches and
        no traceback found.
    """
    if not log_text or not log_text.strip():
        return ()

    if patterns is None:
        patterns = load_error_patterns()

    diagnoses: list[str] = []

    for pattern in patterns:
        compiled = re.compile(pattern["regex"], re.IGNORECASE | re.MULTILINE)
        match = compiled.search(log_text)

        if not match:
            continue

        # If context_regex is specified, confirm context also matches
        context_regex = pattern.get("context_regex")
        if context_regex is not None:
            context_compiled = re.compile(context_regex, re.IGNORECASE | re.MULTILINE)
            if not context_compiled.search(log_text):
                continue

        severity = pattern["severity"].upper()
        explanation = pattern["explanation"]
        suggestion = pattern["suggestion"]
        diagnosis = f"[{severity}] {explanation}\nSuggested fix: {suggestion}"
        diagnoses.append(diagnosis)

    if diagnoses:
        return tuple(diagnoses)

    # No pattern matched -- fall back to raw traceback
    traceback_text = extract_traceback(log_text)
    if traceback_text:
        return (f"Unrecognized error. Raw traceback:\n{traceback_text}",)

    return ()
