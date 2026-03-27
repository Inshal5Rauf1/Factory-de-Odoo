"""Frontmatter — YAML frontmatter parsing, serialization, and CRUD.

Ported from orchestrator/amil/bin/lib/frontmatter.cjs (299 lines, since deleted).
Also provides compiled patterns for STATE.md field extraction (shared with state.py).
"""
from __future__ import annotations

import re

# ── Compiled patterns for STATE.md field extraction ──────────────────────────

BOLD_FIELD = re.compile(r"^\*\*([^*]+)\*\*[:\s]*(.+)$", re.MULTILINE)
PLAIN_FIELD = re.compile(r"^([A-Z][^:]+):\s*(.+)$", re.MULTILINE)

# ── Parsing engine ───────────────────────────────────────────────────────────

_FM_BLOCK_RE = re.compile(r"^---\n([\s\S]+?)\n---")
_KEY_VALUE_RE = re.compile(r"^(\s*)([a-zA-Z0-9_-]+):\s*(.*)")


def extract_frontmatter(content: str) -> dict:
    """Parse YAML-like frontmatter from `---` delimited block."""
    match = _FM_BLOCK_RE.match(content)
    if not match:
        return {}

    yaml_text = match.group(1)
    lines = yaml_text.split("\n")
    frontmatter: dict = {}

    # Stack tracks nested context: [{obj, key, indent}]
    stack: list[dict] = [{"obj": frontmatter, "key": None, "indent": -1}]

    for line in lines:
        if not line.strip():
            continue

        indent_match = re.match(r"^(\s*)", line)
        indent = len(indent_match.group(1)) if indent_match else 0

        # Pop stack back to appropriate level
        while len(stack) > 1 and indent <= stack[-1]["indent"]:
            stack.pop()

        current = stack[-1]

        # Check for key: value pattern
        kv_match = _KEY_VALUE_RE.match(line)
        if kv_match:
            key = kv_match.group(2)
            value = kv_match.group(3).strip()

            if value == "" or value == "[":
                # Key with no value or opening bracket
                current["obj"][key] = [] if value == "[" else {}
                current["key"] = None
                stack.append({"obj": current["obj"][key], "key": None, "indent": indent})
            elif value.startswith("[") and value.endswith("]"):
                # Inline array: key: [a, b, c]
                items = [
                    s.strip().strip("\"'")
                    for s in value[1:-1].split(",")
                    if s.strip()
                ]
                current["obj"][key] = items
                current["key"] = None
            else:
                # Simple key: value
                current["obj"][key] = value.strip("\"'")
                current["key"] = None
        elif line.strip().startswith("- "):
            # Array item
            item_value = line.strip()[2:].strip("\"'")

            if (
                isinstance(current["obj"], dict)
                and not isinstance(current["obj"], list)
                and len(current["obj"]) == 0
            ):
                # Empty object -> convert to array in parent
                if len(stack) > 1:
                    parent = stack[-2]
                    for k in list(parent["obj"].keys()):
                        if parent["obj"][k] is current["obj"]:
                            parent["obj"][k] = [item_value]
                            current["obj"] = parent["obj"][k]
                            break
            elif isinstance(current["obj"], list):
                current["obj"].append(item_value)

    return frontmatter


def reconstruct_frontmatter(obj: dict) -> str:
    """Serialize a dict back to YAML-like frontmatter string."""
    lines: list[str] = []

    def _format_value(key: str, value: object, indent: str = "") -> None:
        if value is None:
            return
        if isinstance(value, list):
            if len(value) == 0:
                lines.append(f"{indent}{key}: []")
            elif (
                all(isinstance(v, str) for v in value)
                and len(value) <= 3
                and len(", ".join(value)) < 60
            ):
                lines.append(f"{indent}{key}: [{', '.join(value)}]")
            else:
                lines.append(f"{indent}{key}:")
                for item in value:
                    sv = str(item)
                    if ":" in sv or "#" in sv:
                        lines.append(f'{indent}  - "{sv}"')
                    else:
                        lines.append(f"{indent}  - {sv}")
        elif isinstance(value, dict):
            lines.append(f"{indent}{key}:")
            for sub_key, sub_val in value.items():
                _format_value(sub_key, sub_val, indent + "  ")
        else:
            sv = str(value)
            if ":" in sv or "#" in sv or sv.startswith("[") or sv.startswith("{"):
                lines.append(f'{indent}{key}: "{sv}"')
            else:
                lines.append(f"{indent}{key}: {sv}")

    for key, value in obj.items():
        _format_value(key, value)

    return "\n".join(lines)


def splice_frontmatter(content: str, new_obj: dict) -> str:
    """Replace or add frontmatter in content."""
    yaml_str = reconstruct_frontmatter(new_obj)
    match = _FM_BLOCK_RE.match(content)
    if match:
        return f"---\n{yaml_str}\n---{content[match.end():]}"
    return f"---\n{yaml_str}\n---\n\n{content}"


def parse_must_haves_block(content: str, block_name: str) -> list:
    """Extract a specific block from must_haves in raw frontmatter YAML."""
    fm_match = _FM_BLOCK_RE.match(content)
    if not fm_match:
        return []

    yaml_text = fm_match.group(1)
    block_pattern = re.compile(rf"^\s{{4}}{re.escape(block_name)}:\s*$", re.MULTILINE)
    block_start = block_pattern.search(yaml_text)
    if not block_start:
        return []

    after_block = yaml_text[block_start.start():]
    block_lines = after_block.split("\n")[1:]  # skip the header line

    items: list = []
    current: dict | str | None = None

    for line in block_lines:
        if not line.strip():
            continue
        indent_m = re.match(r"^(\s*)", line)
        indent = len(indent_m.group(1)) if indent_m else 0
        if indent <= 4 and line.strip():
            break  # back to must_haves level or higher

        if re.match(r"^\s{6}-\s+", line):
            # New list item at 6-space indent
            if current is not None:
                items.append(current)
            current = {}

            # Check if simple string item
            simple = re.match(r'^\s{6}-\s+"?([^"]+)"?\s*$', line)
            if simple and ":" not in line:
                current = simple.group(1)
            else:
                # Key-value on same line as dash
                kv = re.match(r'^\s{6}-\s+(\w+):\s*"?([^"]*)"?\s*$', line)
                if kv:
                    current = {kv.group(1): kv.group(2)}

        elif current is not None and isinstance(current, dict):
            # Continuation key-value at 8+ space indent
            kv = re.match(r'^\s{8,}(\w+):\s*"?([^"]*)"?\s*$', line)
            if kv:
                val = kv.group(2)
                current[kv.group(1)] = int(val) if val.isdigit() else val

            # Array items under a key
            arr = re.match(r'^\s{10,}-\s+"?([^"]+)"?\s*$', line)
            if arr:
                keys = list(current.keys())
                if keys:
                    last_key = keys[-1]
                    if not isinstance(current[last_key], list):
                        current[last_key] = [current[last_key]] if current[last_key] else []
                    current[last_key].append(arr.group(1))

    if current is not None:
        items.append(current)

    return items


# ── Frontmatter schemas ─────────────────────────────────────────────────────

FRONTMATTER_SCHEMAS: dict[str, dict[str, list[str]]] = {
    "plan": {
        "required": [
            "phase", "plan", "type", "wave", "depends_on",
            "files_modified", "autonomous", "must_haves",
        ],
    },
    "summary": {
        "required": ["phase", "plan", "subsystem", "tags", "duration", "completed"],
    },
    "verification": {
        "required": ["phase", "verified", "status", "score"],
    },
}


def validate_frontmatter(fm: dict, schema_name: str) -> dict:
    """Validate frontmatter against a named schema."""
    schema = FRONTMATTER_SCHEMAS.get(schema_name)
    if not schema:
        available = ", ".join(FRONTMATTER_SCHEMAS.keys())
        raise ValueError(f"Unknown schema: {schema_name}. Available: {available}")

    required = schema["required"]
    missing = [f for f in required if f not in fm]
    present = [f for f in required if f in fm]
    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "present": present,
        "schema": schema_name,
    }
