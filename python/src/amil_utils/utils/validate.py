"""Input validation utilities for preprocessor security.

Prevents code injection, SQL injection, and template injection by
enforcing that spec-supplied identifiers (field names, model names)
match the Odoo identifier pattern before interpolation into code,
SQL, or QWeb expressions.
"""

from __future__ import annotations

import re

# Odoo field/model names: lowercase + digits + underscore, starting with
# letter/underscore.  Dots allowed for model technical names (e.g. "uni.student").
_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_.]*$")


def validate_identifier(value: str, context: str = "identifier") -> str:
    """Validate that *value* is a safe Odoo identifier.

    Raises ValueError if the value contains characters outside [a-z0-9_.].
    Returns the validated value unchanged for chaining.

    Args:
        value: The identifier to validate.
        context: Human-readable label for error messages (e.g. "field name").
    """
    if not isinstance(value, str) or not _IDENTIFIER_RE.match(value):
        raise ValueError(
            f"Invalid {context}: {value!r} — "
            f"must match {_IDENTIFIER_RE.pattern}"
        )
    return value


def validate_message(value: str, context: str = "message") -> str:
    """Validate that *value* is safe for embedding in Python string literals.

    Rejects values containing unescaped quotes or backslashes that could
    break out of a string interpolation context.

    Returns the validated value unchanged.
    """
    if not isinstance(value, str):
        raise ValueError(
            f"Invalid {context}: expected string, got {type(value).__name__}"
        )
    # Block characters that break out of f-string / _() contexts
    dangerous = {'"', "'", "\\", "\n", "\r"}
    found = [ch for ch in value if ch in dangerous]
    if found:
        raise ValueError(
            f"Invalid {context}: contains dangerous characters "
            f"{set(found)} — use only alphanumeric, spaces, and punctuation"
        )
    return value
