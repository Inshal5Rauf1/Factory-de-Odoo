"""Pylint-odoo and Docker auto-fix loops with escalation.

Mechanically fixes known pylint-odoo violation codes and Docker error
patterns, re-validates, and escalates remaining issues in a grouped
file:line + suggestion format.

QUAL-09: pylint auto-fix (6 fixable codes, configurable iterations)
QUAL-10: Docker auto-fix (5 fixable patterns, configurable iterations)
AFIX-01: missing mail.thread auto-fix
AFIX-02: unused import auto-fix
DFIX-01: 3 new Docker fix functions (xml_parse_error, missing_acl, manifest_load_order)
"""

from __future__ import annotations

import ast
import csv
import io
import logging
import re
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

from amil_utils.validation.pylint_runner import run_pylint_odoo
from amil_utils.validation.types import Result, Violation

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

FIXABLE_PYLINT_CODES: frozenset[str] = frozenset({
    "W8113",  # redundant string= parameter on field
    "W8111",  # renamed field parameter
    "C8116",  # superfluous manifest key
    "W8150",  # absolute import should be relative
    "C8107",  # missing required manifest key
    "W8161",  # use self.env._() instead of _() in model methods
})

DEFAULT_MAX_FIX_ITERATIONS: int = 5

FIXABLE_DOCKER_PATTERNS: frozenset[str] = frozenset({
    "xml_parse_error",
    "missing_acl",
    "missing_import",
    "manifest_load_order",
    "missing_mail_thread",
})

# Map of renamed field parameters (old -> new) for W8111
_RENAMED_PARAMS: dict[str, str | None] = {
    "track_visibility": "tracking",
    "oldname": None,  # removed entirely
    "digits_compute": "digits",
    "select": "index",
}

# Default values for missing manifest keys (C8107)
_MANIFEST_KEY_DEFAULTS: dict[str, str] = {
    "license": "LGPL-3",
    "author": "",
    "website": "",
    "category": "Uncategorized",
    "version": "19.0.1.0.0",
    "application": "False",
    # "installable" intentionally omitted — True is the default (C8116)
}

# Docker diagnosis text -> pattern ID mapping keywords
_DOCKER_PATTERN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "xml_parse_error": ("xml", "syntax error", "parse", "xmlsyntaxerror", "mismatched tag"),
    "missing_acl": ("access control", "acl", "ir.model.access", "access rights", "no access rule"),
    "missing_import": ("no module named", "importerror", "modulenotfounderror", "could not be imported"),
    "manifest_load_order": ("action", "act_window", "does not exist", "external id not found"),
    "missing_mail_thread": ("mail.thread", "oe_chatter", "chatter", "mail.activity.mixin", "message_follower_ids"),
}


# -------------------------------------------------------------------------
# AST splice utilities (shared by all fixers)
# -------------------------------------------------------------------------


def _find_call_at_line(tree: ast.Module, target_line: int) -> ast.Call | None:
    """Walk AST to find a Call node whose line range includes target_line.

    Args:
        tree: Parsed AST module.
        target_line: 1-based line number to search for.

    Returns:
        The ast.Call node covering that line, or None.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                hasattr(node, "lineno")
                and hasattr(node, "end_lineno")
                and node.lineno <= target_line <= (node.end_lineno or node.lineno)
            ):
                return node
    return None


def _splice_remove_keyword(source: str, call_node: ast.Call, kw_idx: int) -> str:
    """Remove a keyword argument from a Call node using AST positions.

    Handles comma cleanup and blank line removal. Works correctly for
    multi-line function calls where keyword is on its own line.

    Args:
        source: Full source code string.
        call_node: The ast.Call node containing the keyword.
        kw_idx: Index of the keyword to remove in call_node.keywords.

    Returns:
        New source string with keyword removed.
    """
    lines = source.split("\n")
    kw = call_node.keywords[kw_idx]

    # AST positions: lineno is 1-based, col_offset is 0-based
    kw_start_line = kw.lineno - 1
    kw_end_line = (kw.end_lineno or kw.lineno) - 1
    kw_start_col = kw.col_offset
    kw_end_col = kw.end_col_offset or (len(lines[kw_end_line]) if kw_end_line < len(lines) else 0)

    # Determine if keyword spans the entire line (whitespace + keyword + optional comma)
    is_only_on_line = lines[kw_start_line][:kw_start_col].strip() == ""

    if kw_start_line == kw_end_line and is_only_on_line:
        # Keyword is on its own line -- remove entire line(s)
        line_text = lines[kw_start_line]
        # Check if there's a trailing comma after the keyword end
        rest_after = line_text[kw_end_col:].strip()
        if rest_after == "," or rest_after == "":
            # Remove entire line
            new_lines = lines[:kw_start_line] + lines[kw_start_line + 1:]
        else:
            # There's more content after -- just remove the keyword portion
            before = line_text[:kw_start_col]
            after = line_text[kw_end_col:]
            # Clean trailing comma
            after = after.lstrip()
            if after.startswith(","):
                after = after[1:].lstrip()
            new_lines = list(lines)
            new_lines[kw_start_line] = before + after
    elif kw_start_line != kw_end_line:
        # Multi-line keyword value -- remove all lines from start to end
        # Check if line after kw_end has only a comma
        end_line_text = lines[kw_end_line]
        rest_after_end = end_line_text[kw_end_col:].strip()

        lines_to_remove = list(range(kw_start_line, kw_end_line + 1))

        # Check if we need to also consume a trailing comma on the end line
        if rest_after_end == ",":
            pass  # Already included, the whole line goes
        elif rest_after_end.startswith(","):
            # Trim the comma from remaining text
            remaining = end_line_text[kw_end_col:].lstrip()
            if remaining.startswith(","):
                remaining = remaining[1:]
            if remaining.strip() == "":
                pass  # Whole line goes
            else:
                lines[kw_end_line] = end_line_text[:kw_start_col] + remaining.lstrip()
                lines_to_remove = list(range(kw_start_line, kw_end_line))

        new_lines = [l for i, l in enumerate(lines) if i not in lines_to_remove]
    else:
        # Same line, not the only content -- inline removal
        line_text = lines[kw_start_line]
        before = line_text[:kw_start_col]
        after = line_text[kw_end_col:]

        # Clean up commas
        after_stripped = after.lstrip()
        if after_stripped.startswith(","):
            after = after_stripped[1:]
        elif before.rstrip().endswith(","):
            before = before.rstrip()[:-1]

        new_line = before.rstrip() + after.lstrip()
        # Clean up ", )" -> ")"
        new_line = re.sub(r",\s*\)", ")", new_line)
        new_lines = list(lines)
        new_lines[kw_start_line] = new_line

    # Handle preceding comma if keyword was the last one
    if kw_idx == len(call_node.keywords) - 1 and kw_idx > 0:
        prev_kw = call_node.keywords[kw_idx - 1]
        prev_end_line = (prev_kw.end_lineno or prev_kw.lineno) - 1
        if prev_end_line < len(new_lines):
            prev_line = new_lines[prev_end_line]
            # Remove trailing comma from previous keyword's line if present
            stripped = prev_line.rstrip()
            if stripped.endswith(","):
                new_lines[prev_end_line] = stripped[:-1] + prev_line[len(stripped):]

    # Also check: if this was the last keyword and there are positional args,
    # the last positional arg may now have a trailing comma that needs cleanup
    if kw_idx == 0 and len(call_node.keywords) == 1 and call_node.args:
        last_arg = call_node.args[-1]
        arg_end_line = (last_arg.end_lineno or last_arg.lineno) - 1
        if arg_end_line < len(new_lines):
            arg_line = new_lines[arg_end_line]
            stripped = arg_line.rstrip()
            if stripped.endswith(","):
                new_lines[arg_end_line] = stripped[:-1] + arg_line[len(stripped):]

    result = "\n".join(new_lines)
    # Clean up double blank lines
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result


def _splice_rename_keyword(source: str, kw: ast.keyword, new_name: str) -> str:
    """Rename a keyword argument at its precise AST position.

    Only replaces the keyword name (e.g., 'track_visibility' -> 'tracking'),
    leaving the value and everything else untouched.

    Args:
        source: Full source code string.
        kw: The ast.keyword node to rename.
        new_name: The new keyword argument name.

    Returns:
        New source string with keyword renamed.
    """
    lines = source.split("\n")
    line_idx = kw.lineno - 1
    col = kw.col_offset
    old_name = kw.arg

    if old_name is None:
        return source

    line = lines[line_idx]
    # The keyword name starts at col_offset and spans len(old_name) characters
    before = line[:col]
    after = line[col + len(old_name):]
    new_lines = list(lines)
    new_lines[line_idx] = before + new_name + after
    return "\n".join(new_lines)


def _splice_remove_dict_entry(source: str, key_node: ast.expr, val_node: ast.expr) -> str:
    """Remove a key-value pair from a dict literal using AST positions.

    Handles multi-line values (lists, strings spanning multiple lines).

    Args:
        source: Full source code string.
        key_node: The AST node for the dict key.
        val_node: The AST node for the dict value.

    Returns:
        New source string with the dict entry removed.
    """
    lines = source.split("\n")

    key_start_line = key_node.lineno - 1
    val_end_line = (val_node.end_lineno or val_node.lineno) - 1
    val_end_col = val_node.end_col_offset or len(lines[val_end_line])

    # Check what's after the value on its end line
    rest_after = lines[val_end_line][val_end_col:].strip()

    # Consume trailing comma if present
    if rest_after.startswith(","):
        # Check if there's anything after the comma on the same line
        after_comma = rest_after[1:].strip()
        if after_comma == "":
            # Nothing else on line -- remove entire lines from key_start to val_end
            end_remove = val_end_line + 1
        else:
            # Something after comma -- only remove up to and including comma
            end_remove = val_end_line  # Don't remove this line entirely
            comma_pos = lines[val_end_line].index(",", val_end_col)
            lines[val_end_line] = lines[val_end_line][comma_pos + 1:].lstrip()
            # Preserve indentation
            if lines[val_end_line].strip():
                indent = lines[key_start_line][:len(lines[key_start_line]) - len(lines[key_start_line].lstrip())]
                lines[val_end_line] = indent + lines[val_end_line].lstrip()
    elif rest_after == "":
        end_remove = val_end_line + 1
    else:
        end_remove = val_end_line + 1

    # Remove the lines
    if end_remove > val_end_line:
        new_lines = lines[:key_start_line] + lines[end_remove:]
    else:
        new_lines = lines[:key_start_line] + lines[end_remove:]

    result = "\n".join(new_lines)
    # Clean up double blank lines
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result


# -------------------------------------------------------------------------
# Pylint auto-fix
# -------------------------------------------------------------------------


def is_fixable_pylint(violation: Violation) -> bool:
    """Check whether a pylint violation can be mechanically auto-fixed."""
    return violation.rule_code in FIXABLE_PYLINT_CODES


def fix_pylint_violation(violation: Violation, module_path: Path) -> bool:
    """Apply a mechanical fix for a single pylint violation.

    Reads the source file, applies the fix based on the rule_code,
    and writes the corrected content back. Uses immutable patterns:
    read content -> create new content -> write back.

    Args:
        violation: The Violation to fix.
        module_path: Root path of the Odoo module.

    Returns:
        True if fix was applied, False if not applicable or failed.
    """
    if violation.rule_code not in FIXABLE_PYLINT_CODES:
        return False

    file_path = module_path / violation.file
    if not file_path.exists():
        return False

    handlers = {
        "W8113": _fix_w8113_redundant_string,
        "W8111": _fix_w8111_renamed_parameter,
        "C8116": _fix_c8116_superfluous_manifest_key,
        "W8150": _fix_w8150_absolute_import,
        "C8107": _fix_c8107_missing_manifest_key,
        "W8161": _fix_w8161_env_translate,
    }

    handler = handlers.get(violation.rule_code)
    if handler is None:
        return False

    return handler(violation, file_path)


def _fix_w8113_redundant_string(violation: Violation, file_path: Path) -> bool:
    """W8113: Remove redundant string= parameter from field definition.

    Uses AST to locate the Call node and its 'string' keyword argument,
    then splices it out using precise AST positions. Handles multi-line
    field definitions correctly.
    """
    content = file_path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False

    call_node = _find_call_at_line(tree, violation.line)
    if call_node is None:
        return False

    # Find the 'string' keyword
    kw_idx = None
    for idx, kw in enumerate(call_node.keywords):
        if kw.arg == "string":
            kw_idx = idx
            break

    if kw_idx is None:
        return False

    new_content = _splice_remove_keyword(content, call_node, kw_idx)
    if new_content == content:
        return False

    file_path.write_text(new_content, encoding="utf-8")
    return True


def _fix_w8111_renamed_parameter(violation: Violation, file_path: Path) -> bool:
    """W8111: Rename deprecated field parameter to its replacement.

    Uses AST to locate the exact keyword argument and either rename it
    (via _splice_rename_keyword) or remove it (via _splice_remove_keyword).
    Only modifies the precise keyword location, not global string replace.
    """
    content = file_path.read_text(encoding="utf-8")

    # Extract old parameter name from the violation message
    # Message format: '"track_visibility" has been renamed to "tracking"'
    match = re.search(r'"(\w+)"\s+has been renamed', violation.message)
    if not match:
        return False

    old_param = match.group(1)
    new_param = _RENAMED_PARAMS.get(old_param)

    if old_param not in _RENAMED_PARAMS:
        return False

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False

    call_node = _find_call_at_line(tree, violation.line)
    if call_node is None:
        return False

    # Find the keyword with arg == old_param
    kw_idx = None
    for idx, kw in enumerate(call_node.keywords):
        if kw.arg == old_param:
            kw_idx = idx
            break

    if kw_idx is None:
        return False

    if new_param is None:
        # Parameter removed entirely
        new_content = _splice_remove_keyword(content, call_node, kw_idx)
    else:
        # Rename the parameter
        new_content = _splice_rename_keyword(content, call_node.keywords[kw_idx], new_param)

    if new_content == content:
        return False

    file_path.write_text(new_content, encoding="utf-8")
    return True


def _fix_c8116_superfluous_manifest_key(violation: Violation, file_path: Path) -> bool:
    """C8116: Remove a superfluous/deprecated key from __manifest__.py.

    Uses AST to locate the Dict node and find the key-value pair,
    then uses _splice_remove_dict_entry to remove it. Handles multi-line
    values (lists, strings) correctly.
    """
    content = file_path.read_text(encoding="utf-8")

    # Extract key name from message: 'Deprecated key "description" in manifest file'
    match = re.search(r'"(\w+)"', violation.message)
    if not match:
        return False

    key_name = match.group(1)

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False

    # Walk to find the Dict node and the matching key
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key_node, val_node in zip(node.keys, node.values):
                if (
                    isinstance(key_node, ast.Constant)
                    and key_node.value == key_name
                ):
                    new_content = _splice_remove_dict_entry(content, key_node, val_node)
                    if new_content == content:
                        return False
                    file_path.write_text(new_content, encoding="utf-8")
                    return True

    return False


def _fix_w8150_absolute_import(violation: Violation, file_path: Path) -> bool:
    """W8150: Convert absolute odoo.addons import to relative import.

    Uses AST to find ImportFrom nodes with 'odoo.addons.' prefix and
    rewrites the module path using precise AST positions.
    """
    content = file_path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False

    lines = content.split("\n")
    changed = False

    # Collect import nodes to process (process in reverse to avoid line shifts)
    import_nodes: list[ast.ImportFrom] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("odoo.addons."):
            import_nodes.append(node)

    # Sort by line number descending for safe modification
    import_nodes.sort(key=lambda n: n.lineno, reverse=True)

    for node in import_nodes:
        line_idx = node.lineno - 1
        if line_idx >= len(lines):
            continue

        old_module = node.module
        if old_module is None:
            continue

        # Strip "odoo.addons.module_name" prefix
        # odoo.addons.my_module -> "."
        # odoo.addons.my_module.sub -> ".sub"
        parts = old_module.split(".")
        # parts[0] = "odoo", parts[1] = "addons", parts[2] = module_name
        if len(parts) < 3:
            continue

        if len(parts) == 3:
            new_module = "."
        else:
            new_module = "." + ".".join(parts[3:])

        # Replace the module path in the line using AST col_offset
        line = lines[line_idx]
        # Find "from <module>" pattern in the line
        # The import statement starts at col_offset
        # Find the old module string in the line after "from "
        from_idx = line.find("from ", node.col_offset)
        if from_idx == -1:
            continue

        module_start = from_idx + 5  # len("from ")
        # Skip whitespace
        while module_start < len(line) and line[module_start] == " ":
            module_start += 1

        module_end = module_start + len(old_module)
        if line[module_start:module_end] == old_module:
            new_line = line[:module_start] + new_module + line[module_end:]
            lines[line_idx] = new_line
            changed = True

    if not changed:
        return False

    new_content = "\n".join(lines)
    file_path.write_text(new_content, encoding="utf-8")
    return True


def _fix_c8107_missing_manifest_key(violation: Violation, file_path: Path) -> bool:
    """C8107: Add a missing required key to __manifest__.py.

    Uses AST to locate the Dict node and validate the key doesn't already
    exist, then inserts the new key-value pair after the opening brace.
    """
    content = file_path.read_text(encoding="utf-8")

    # Extract missing key name: 'Missing required key "license" in manifest file'
    match = re.search(r'"(\w+)"', violation.message)
    if not match:
        return False

    key_name = match.group(1)
    default_value = _MANIFEST_KEY_DEFAULTS.get(key_name, "")

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False

    # Walk to find the Dict node and check if key already exists
    dict_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            # Check if key already exists
            for key_nd in node.keys:
                if isinstance(key_nd, ast.Constant) and key_nd.value == key_name:
                    return False  # Key already exists
            dict_node = node
            break

    if dict_node is None:
        return False

    # Build the insertion line
    if default_value in ("True", "False"):
        insert_line = f'    "{key_name}": {default_value},'
    else:
        insert_line = f'    "{key_name}": "{default_value}",'

    # Insert after the dict's opening brace line (dict_node.lineno is 1-based)
    lines = content.split("\n")
    insert_idx = dict_node.lineno  # Insert after the { line (0-based: lineno is already the line after)
    new_lines = lines[:insert_idx] + [insert_line] + lines[insert_idx:]
    new_content = "\n".join(new_lines)

    if new_content == content:
        return False

    file_path.write_text(new_content, encoding="utf-8")
    return True


def _fix_w8161_env_translate(violation: Violation, file_path: Path) -> bool:
    """W8161: Replace _('msg') with self.env._('msg') in method bodies.

    Uses AST to find FunctionDef nodes containing Name('_') calls,
    and replaces them with self.env._() via text substitution at precise
    AST positions. Also removes the standalone _ import.

    Only transforms _() calls inside def blocks — class-level _() calls
    (e.g., _description = _("...")) are left untouched.
    """
    content = file_path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False

    # Collect line numbers of all _("...") calls inside FunctionDef nodes
    call_positions_set: set[tuple[int, int]] = set()  # deduplicate (line_0based, col_offset)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # Only walk direct body nodes — NOT nested FunctionDefs (which ast.walk
        # would recurse into, causing double-counting of _() calls in inner funcs)
        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is not node:
                continue
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "_"
            ):
                call_positions_set.add(
                    (child.func.lineno - 1, child.func.col_offset)
                )

    call_positions: list[tuple[int, int]] = list(call_positions_set)

    if not call_positions:
        return False

    lines = content.split("\n")
    changed = False

    # Process in reverse order so line/col positions stay valid
    for line_idx, col in sorted(call_positions, reverse=True):
        line = lines[line_idx]
        # Verify the character at col is actually "_" followed by "("
        if col < len(line) and line[col] == "_":
            rest = line[col + 1:].lstrip()
            if rest.startswith("("):
                # Replace bare "_" with "self.env._"
                lines[line_idx] = line[:col] + "self.env._" + line[col + 1:]
                changed = True

    if not changed:
        return False

    # Remove standalone _ from imports:
    # "from odoo import _" or "from odoo import _, models" etc.
    # "from odoo.tools.translate import _"
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Handle "from odoo import _" (sole import)
        if stripped == "from odoo import _":
            continue
        if stripped == "from odoo.tools.translate import _":
            continue
        # Handle "from odoo import _, X, Y" -> "from odoo import X, Y"
        if re.match(r"^from\s+odoo\s+import\s+", stripped):
            new_line = re.sub(r"\b_\s*,\s*", "", line)
            # Also handle trailing: "X, _" -> "X"
            new_line = re.sub(r",\s*_\s*$", "", new_line)
            # Handle "from odoo import _\n" (already caught above, but safety)
            check = re.sub(r"^from\s+odoo\s+import\s*", "", new_line.strip())
            if not check.strip():
                continue
            new_lines.append(new_line)
        elif re.match(r"^from\s+odoo\.tools\.translate\s+import\s+", stripped):
            new_line = re.sub(r"\b_\s*,\s*", "", line)
            new_line = re.sub(r",\s*_\s*$", "", new_line)
            check = re.sub(r"^from\s+odoo\.tools\.translate\s+import\s*", "", new_line.strip())
            if not check.strip():
                continue
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    new_content = "\n".join(new_lines)

    if new_content == content:
        return False

    file_path.write_text(new_content, encoding="utf-8")
    return True


def fix_pylint_violations(
    violations: tuple[Violation, ...],
    module_path: Path,
) -> tuple[int, tuple[Violation, ...]]:
    """Process a batch of violations, fixing what can be fixed.

    Args:
        violations: All violations to process.
        module_path: Root path of the Odoo module.

    Returns:
        Tuple of (fixed_count, remaining_violations) where remaining
        includes non-fixable violations and failed fixes.
    """
    fixed_count = 0
    remaining: list[Violation] = []

    for violation in violations:
        if is_fixable_pylint(violation):
            if fix_pylint_violation(violation, module_path):
                fixed_count += 1
            else:
                remaining.append(violation)
        else:
            remaining.append(violation)

    return fixed_count, tuple(remaining)


def run_pylint_fix_loop(
    module_path: Path,
    pylintrc_path: Path | None = None,
    max_iterations: int = DEFAULT_MAX_FIX_ITERATIONS,
) -> Result[tuple[int, tuple[Violation, ...]]]:
    """Run pylint-odoo with up to max_iterations auto-fix cycles.

    Each cycle: run pylint -> fix fixable violations -> count.
    If a cycle produces 0 fixable violations, stop early.

    Args:
        module_path: Root path of the Odoo module.
        pylintrc_path: Optional path to .pylintrc-odoo config file.
        max_iterations: Maximum number of fix cycles (default 5).

    Returns:
        Result.ok((total_fixed, remaining_violations)) after all cycles.
    """
    total_fixed = 0
    remaining: tuple[Violation, ...] = ()

    for _cycle in range(max_iterations):
        pylint_result = run_pylint_odoo(module_path, pylintrc_path=pylintrc_path)
        if not pylint_result.success:
            break
        violations = pylint_result.data or ()

        if not violations:
            break

        # Handle W0611 (unused-import) via fix_unused_imports
        w0611_violations = [v for v in violations if v.rule_code == "W0611"]
        non_w0611 = tuple(v for v in violations if v.rule_code != "W0611")

        w0611_applied = False
        if w0611_violations:
            w0611_files = {v.file for v in w0611_violations}
            for rel_file in w0611_files:
                file_path = module_path / rel_file
                if file_path.exists():
                    if fix_unused_imports(file_path):
                        w0611_applied = True
                        total_fixed += sum(
                            1 for v in w0611_violations if v.file == rel_file
                        )

        # Check if any remaining are fixable by pylint fixer
        has_fixable = any(is_fixable_pylint(v) for v in non_w0611)
        if not has_fixable:
            remaining = non_w0611
            if w0611_applied:
                # W0611 fixes shifted line numbers; re-run pylint to get
                # updated violations that may now be fixable
                continue
            break

        cycle_fixed, remaining = fix_pylint_violations(non_w0611, module_path)
        total_fixed += cycle_fixed

        if cycle_fixed == 0 and not w0611_applied:
            break

    return Result.ok((total_fixed, remaining))


# -------------------------------------------------------------------------
# Docker auto-fix identification
# -------------------------------------------------------------------------


def identify_docker_fix(diagnosis: str) -> str | None:
    """Identify whether a Docker error diagnosis matches a fixable pattern.

    Matches diagnosis text against known fixable Docker error patterns
    using keyword matching against the error_patterns.json taxonomy.

    Args:
        diagnosis: A diagnosis string from diagnose_errors().

    Returns:
        The pattern ID string if fixable, None if not.
    """
    diagnosis_lower = diagnosis.lower()

    for pattern_id, keywords in _DOCKER_PATTERN_KEYWORDS.items():
        if any(kw in diagnosis_lower for kw in keywords):
            return pattern_id

    return None


# -------------------------------------------------------------------------
# Escalation formatting
# -------------------------------------------------------------------------


def format_escalation(violations: tuple[Violation, ...]) -> str:
    """Format remaining violations as a grouped escalation report.

    Groups violations by file, includes file:line reference and
    one fix suggestion per violation per CONTEXT.md Decision E.

    Args:
        violations: Remaining violations after auto-fix exhausted.

    Returns:
        Formatted escalation string, or "No remaining issues." if empty.
    """
    if not violations:
        return "No remaining issues."

    grouped: dict[str, list[Violation]] = defaultdict(list)
    for v in violations:
        grouped[v.file].append(v)

    lines: list[str] = ["Auto-fix exhausted. Remaining violations:", ""]

    for file_path in sorted(grouped.keys()):
        file_violations = sorted(grouped[file_path], key=lambda v: v.line)
        for v in file_violations:
            lines.append(f"[{v.file}:{v.line}] {v.rule_code}: {v.message}")
            if v.suggestion:
                lines.append(f"  -> {v.suggestion}")

    return "\n".join(lines)


# -------------------------------------------------------------------------
# Module-level auto-fix: missing mail.thread (AFIX-01)
# -------------------------------------------------------------------------

# Chatter indicators in XML view files
_CHATTER_INDICATORS: tuple[str, ...] = (
    "oe_chatter",
    "<chatter",
    "message_follower_ids",
    "message_ids",
)


def _has_chatter_references(module_path: Path) -> bool:
    """Check whether any XML file in views/ contains chatter indicators."""
    views_dir = module_path / "views"
    if not views_dir.is_dir():
        return False

    for xml_file in views_dir.glob("*.xml"):
        content = xml_file.read_text(encoding="utf-8")
        if any(indicator in content for indicator in _CHATTER_INDICATORS):
            return True

    return False


def _has_mail_thread_inherit(model_content: str) -> bool:
    """Check whether model content already contains mail.thread inheritance."""
    return "mail.thread" in model_content


def _find_model_file(module_path: Path) -> Path | None:
    """Find the first .py file in models/ that defines _name."""
    models_dir = module_path / "models"
    if not models_dir.is_dir():
        return None

    for py_file in sorted(models_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        content = py_file.read_text(encoding="utf-8")
        if "_name" in content and "_name =" in content:
            return py_file

    return None


def fix_missing_mail_thread(module_path: Path) -> bool:
    """Detect and fix missing mail.thread inheritance when chatter XML exists.

    Scans XML files in views/ for chatter indicators (oe_chatter, <chatter/>,
    message_follower_ids, message_ids). If found, checks whether the model
    already inherits from mail.thread. If not, inserts the _inherit line
    after _description.

    Args:
        module_path: Root path of the Odoo module.

    Returns:
        True if fix was applied, False if not needed or not applicable.
    """
    if not _has_chatter_references(module_path):
        return False

    model_file = _find_model_file(module_path)
    if model_file is None:
        return False

    content = model_file.read_text(encoding="utf-8")

    if _has_mail_thread_inherit(content):
        return False

    # Insert _inherit after _description line
    lines = content.split("\n")
    description_idx: int | None = None

    for idx, line in enumerate(lines):
        if "_description" in line and "=" in line:
            description_idx = idx
            break

    if description_idx is None:
        return False

    # Detect the indentation from the _description line
    desc_line = lines[description_idx]
    indent = ""
    for ch in desc_line:
        if ch in (" ", "\t"):
            indent += ch
        else:
            break

    inherit_line = f"{indent}_inherit = ['mail.thread', 'mail.activity.mixin']"

    new_lines = list(lines)
    new_lines.insert(description_idx + 1, inherit_line)
    new_content = "\n".join(new_lines)

    model_file.write_text(new_content, encoding="utf-8")
    return True


# -------------------------------------------------------------------------
# Module-level auto-fix: XML parse error (fix mismatched tags)
# -------------------------------------------------------------------------


def fix_xml_parse_error(module_path: Path, error_output: str) -> bool:
    """Detect and fix mismatched closing tags in XML view files.

    Parses the error output to find the file and the mismatched tag details.
    Common pattern from lxml: "Opening and ending tag mismatch: X line N and Y"
    This means the opening tag is X but the closing tag is Y (a typo).

    Args:
        module_path: Root path of the Odoo module.
        error_output: Error text from Docker validation.

    Returns:
        True if fix was applied, False if not applicable or XML is well-formed.
    """
    import xml.etree.ElementTree as ET

    # Try to find referenced XML files in the error output
    xml_files: list[Path] = []

    # Pattern: "(filename, line N)" or "File "...filename""
    file_matches = re.findall(
        r'(?:(?:\(|File\s+["\'])([^)"\']+\.xml))', error_output
    )
    for fname in file_matches:
        candidate = module_path / fname
        # Guard against path traversal (e.g., "../../etc/passwd.xml")
        if not candidate.resolve().is_relative_to(module_path.resolve()):
            continue
        if candidate.exists():
            xml_files.append(candidate)

    # If no specific file found, scan all XML files in views/
    if not xml_files:
        views_dir = module_path / "views"
        if views_dir.is_dir():
            xml_files = sorted(views_dir.glob("*.xml"))

    if not xml_files:
        return False

    # Extract mismatch info from error output
    # Pattern: "Opening and ending tag mismatch: OPEN line N and CLOSE"
    mismatch_match = re.search(
        r"(?:Opening and ending tag mismatch|Mismatched tag):\s*(\w+)\s+line\s+\d+\s+and\s+(\w+)",
        error_output,
    )

    any_fixed = False

    for xml_file in xml_files:
        content = xml_file.read_text(encoding="utf-8")

        # First, try to parse -- if it parses fine, no fix needed
        try:
            ET.fromstring(content)
            continue  # Well-formed, skip
        except ET.ParseError:
            pass  # Has errors, try to fix

        if mismatch_match:
            open_tag = mismatch_match.group(1)
            close_tag = mismatch_match.group(2)

            # Replace the wrong closing tag with the correct one
            wrong_close = f"</{close_tag}>"
            right_close = f"</{open_tag}>"

            if wrong_close in content:
                new_content = content.replace(wrong_close, right_close, 1)
                if new_content != content:
                    xml_file.write_text(new_content, encoding="utf-8")
                    any_fixed = True
                    continue

        # Fallback: try heuristic detection of common mismatched tags
        # Look for closing tags that don't have matching opening tags
        opening_tags = re.findall(r"<([\w\-:\.]+)[\s>]", content)
        closing_tags = re.findall(r"</([\w\-:\.]+)>", content)

        open_counts: dict[str, int] = {}
        for tag in opening_tags:
            open_counts[tag] = open_counts.get(tag, 0) + 1

        close_counts: dict[str, int] = {}
        for tag in closing_tags:
            close_counts[tag] = close_counts.get(tag, 0) + 1

        # Find tags that appear in closing but not in opening (likely typos)
        new_content = content
        for close_tag_name in close_counts:
            if close_tag_name not in open_counts:
                # This closing tag has no matching opener -- find the best match
                # by looking for an opener with more opens than closes
                for open_tag_name in open_counts:
                    open_excess = open_counts.get(open_tag_name, 0) - close_counts.get(
                        open_tag_name, 0
                    )
                    if open_excess > 0:
                        wrong = f"</{close_tag_name}>"
                        right = f"</{open_tag_name}>"
                        new_content = new_content.replace(wrong, right, 1)
                        break

        if new_content != content:
            xml_file.write_text(new_content, encoding="utf-8")
            any_fixed = True

    return any_fixed


# -------------------------------------------------------------------------
# Module-level auto-fix: missing ACL (create ir.model.access.csv)
# -------------------------------------------------------------------------


def _extract_model_names(module_path: Path) -> tuple[str, ...]:
    """Scan models/ directory for all Python files defining _name.

    Returns:
        Tuple of model technical names found (e.g., ("my.model", "my.other")).
    """
    models_dir = module_path / "models"
    if not models_dir.is_dir():
        return ()

    model_names: list[str] = []
    for py_file in sorted(models_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        content = py_file.read_text(encoding="utf-8")
        # Match _name = "model.name" or _name = 'model.name'
        matches = re.findall(r"""_name\s*=\s*["']([^"']+)["']""", content)
        model_names.extend(matches)

    return tuple(model_names)


def _build_acl_row(model_name: str) -> list[str]:
    """Build a single ACL CSV row for a model.

    Returns a list of field values suitable for csv.writer.
    Format: access_{underscored},access.{dotted},model_{underscored},base.group_user,1,1,1,0
    """
    model_underscore = model_name.replace(".", "_")
    return [
        f"access_{model_underscore}",
        f"access.{model_name}",
        f"model_{model_underscore}",
        "base.group_user",
        "1", "1", "1", "0",
    ]


def fix_missing_acl(module_path: Path, error_output: str) -> bool:
    """Create or update security/ir.model.access.csv for all models.

    Scans models/ for _name definitions, checks if CSV exists with entries
    for each model, and creates/updates as needed. Also ensures __manifest__.py
    includes the CSV path in its data list.

    Args:
        module_path: Root path of the Odoo module.
        error_output: Error text from Docker validation.

    Returns:
        True if fix was applied, False if all models already have ACL entries.
    """
    model_names = _extract_model_names(module_path)
    if not model_names:
        return False

    csv_path = module_path / "security" / "ir.model.access.csv"
    header = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink"

    existing_content = ""
    if csv_path.exists():
        existing_content = csv_path.read_text(encoding="utf-8")

    # Find which models are missing from the CSV
    missing_models: list[str] = []
    for model_name in model_names:
        model_underscore = model_name.replace(".", "_")
        if f"model_{model_underscore}" not in existing_content:
            missing_models.append(model_name)

    if not missing_models:
        return False

    # Build new CSV content using csv.writer for proper escaping
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")

    if existing_content.strip():
        # Preserve existing lines, append new rows
        lines = existing_content.rstrip("\n").split("\n")
        for line in lines:
            buf.write(line + "\n")
    else:
        writer.writerow(header.split(","))

    for model_name in missing_models:
        writer.writerow(_build_acl_row(model_name))

    new_csv_content = buf.getvalue()

    # Create security/ directory if needed
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(new_csv_content, encoding="utf-8")

    # Update __manifest__.py to include the CSV path if not already there
    manifest_path = module_path / "__manifest__.py"
    if manifest_path.exists():
        manifest_content = manifest_path.read_text(encoding="utf-8")
        csv_ref = "security/ir.model.access.csv"
        if csv_ref not in manifest_content:
            # Insert into the 'data' list using AST for safe parsing
            try:
                tree = ast.parse(manifest_content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Dict):
                        for key_node, value_node in zip(node.keys, node.values):
                            if (
                                isinstance(key_node, ast.Constant)
                                and key_node.value == "data"
                                and isinstance(value_node, ast.List)
                            ):
                                # Found the data list -- insert CSV reference
                                # Use string manipulation to add it
                                new_manifest = manifest_content.replace(
                                    '"data": [',
                                    f'"data": [\n        "{csv_ref}",',
                                )
                                if new_manifest == manifest_content:
                                    # Try alternate formatting
                                    new_manifest = manifest_content.replace(
                                        "'data': [",
                                        f"'data': [\n        '{csv_ref}',",
                                    )
                                if new_manifest != manifest_content:
                                    manifest_path.write_text(new_manifest, encoding="utf-8")
                                else:
                                    logger.warning(
                                        "Found 'data' key in manifest but string replacement "
                                        "failed — manifest formatting may be non-standard"
                                    )
                                break
            except SyntaxError:
                pass  # Cannot parse manifest, skip update

    return True


# -------------------------------------------------------------------------
# Module-level auto-fix: manifest load order (reorder data files)
# -------------------------------------------------------------------------


def _is_action_definer(file_path: Path) -> bool:
    """Check if an XML file defines actions (ir.actions.act_window or <act_window>)."""
    if not file_path.exists():
        return False
    content = file_path.read_text(encoding="utf-8")
    return bool(
        "ir.actions.act_window" in content
        or "<act_window" in content
    )


def _is_action_reference(file_path: Path) -> bool:
    """Check if an XML file references actions (action= attribute in menus)."""
    if not file_path.exists():
        return False
    content = file_path.read_text(encoding="utf-8")
    return bool(re.search(r'\baction\s*=\s*["\']', content))


def fix_manifest_load_order(module_path: Path, error_output: str) -> bool:
    """Reorder manifest data list so action definitions precede action references.

    Reads __manifest__.py, identifies files that define actions and files that
    reference actions, and reorders so definitions come first.

    Args:
        module_path: Root path of the Odoo module.
        error_output: Error text from Docker validation.

    Returns:
        True if fix was applied, False if order is already correct.
    """
    manifest_path = module_path / "__manifest__.py"
    if not manifest_path.exists():
        return False

    manifest_content = manifest_path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(manifest_content)
    except SyntaxError:
        return False

    # Find the 'data' list in the manifest dict
    data_list: list[str] | None = None
    data_node: ast.List | None = None

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key_node, value_node in zip(node.keys, node.values):
                if (
                    isinstance(key_node, ast.Constant)
                    and key_node.value == "data"
                    and isinstance(value_node, ast.List)
                ):
                    data_list = []
                    data_node = value_node
                    for elt in value_node.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            data_list.append(elt.value)
                    break

    if data_list is None or len(data_list) < 2:
        return False

    # Classify each file
    definers: list[str] = []
    referencers: list[str] = []
    others: list[str] = []

    for file_ref in data_list:
        file_path = module_path / file_ref
        if _is_action_definer(file_path):
            definers.append(file_ref)
        elif _is_action_reference(file_path):
            referencers.append(file_ref)
        else:
            others.append(file_ref)

    if not definers or not referencers:
        return False

    # Check if order is already correct: all definers before all referencers
    first_referencer_idx = min(data_list.index(r) for r in referencers)
    last_definer_idx = max(data_list.index(d) for d in definers)

    if last_definer_idx < first_referencer_idx:
        # Already in correct order
        return False

    # Build new order: others first, then definers, then referencers
    # Preserve relative order within each group
    reordered = others + definers + referencers

    # Rebuild the manifest content with the new data list
    # Get the source text segment for the old data list and replace it
    assert data_node is not None
    # Build new list repr
    new_list_items = ", ".join(f'"{item}"' for item in reordered)
    new_list_str = f"[{new_list_items}]"

    # Extract old data list string from source
    # Use line/col info from AST
    lines = manifest_content.split("\n")
    # Find "data": [...] and replace the list portion
    new_manifest = re.sub(
        r'("data"\s*:\s*)\[.*?\]',
        rf'\1{new_list_str}',
        manifest_content,
        flags=re.DOTALL,
    )

    if new_manifest == manifest_content:
        return False

    manifest_path.write_text(new_manifest, encoding="utf-8")
    return True


# -------------------------------------------------------------------------
# Docker auto-fix dispatch loop
# -------------------------------------------------------------------------

# Additional keyword patterns for pylint-reported unused imports
_DOCKER_UNUSED_IMPORT_KEYWORDS: tuple[str, ...] = (
    "unused-import",
    "unused import",
    "w0611",
)


def _dispatch_docker_fix(
    module_path: Path,
    error_output: str,
    tried_patterns: set[str] | None = None,
) -> tuple[bool, str | None]:
    """Dispatch a single Docker fix based on error pattern identification.

    Internal helper used by run_docker_fix_loop. Identifies the error pattern
    and dispatches to the appropriate fix function.

    Args:
        module_path: Root path of the Odoo module.
        error_output: The error text from Docker validation.
        tried_patterns: Set of pattern IDs already attempted. These are
            skipped to avoid wasting iterations. None means no filtering.
            The "unused_import" pattern is exempt (cumulative fix).

    Returns:
        Tuple of (fix_applied, pattern_id). pattern_id is the ID of the
        pattern that was attempted, or None if no fix was applied.
    """
    import logging

    logger = logging.getLogger(__name__)

    if not error_output or not error_output.strip():
        return (False, None)

    # Check for unused-import pattern first (not in Docker patterns)
    # Unused imports are exempt from tried_patterns — they are cumulative fixes
    error_lower = error_output.lower()
    if any(kw in error_lower for kw in _DOCKER_UNUSED_IMPORT_KEYWORDS):
        logger.info("run_docker_fix_loop: detected unused-import pattern")
        models_dir = module_path / "models"
        if models_dir.is_dir():
            applied = False
            for py_file in sorted(models_dir.glob("*.py")):
                if py_file.name == "__init__.py":
                    continue
                if fix_unused_imports(py_file):
                    logger.info("run_docker_fix_loop: fixed unused imports in %s", py_file)
                    applied = True
            if applied:
                return (True, "unused_import")

    # Standard Docker pattern identification
    pattern_id = identify_docker_fix(error_output)

    if pattern_id is None:
        logger.debug("run_docker_fix_loop: no fixable pattern identified")
        return (False, None)

    # Skip patterns already tried (except unused_import which is cumulative)
    if tried_patterns is not None and pattern_id in tried_patterns:
        logger.info(
            "run_docker_fix_loop: skipping already-tried pattern '%s'",
            pattern_id,
        )
        return (False, pattern_id)

    logger.info("run_docker_fix_loop: detected pattern '%s'", pattern_id)

    # Dispatch dict: pattern_id -> (fix_function, needs_error_output)
    # missing_mail_thread only needs module_path; the 3 new functions
    # also need error_output for context-aware fixing.
    dispatch: dict[str, tuple[object, bool]] = {
        "xml_parse_error": (fix_xml_parse_error, True),
        "missing_acl": (fix_missing_acl, True),
        "manifest_load_order": (fix_manifest_load_order, True),
        "missing_mail_thread": (fix_missing_mail_thread, False),
    }

    entry = dispatch.get(pattern_id)
    if entry is None:
        logger.debug("run_docker_fix_loop: no fix function for pattern '%s'", pattern_id)
        return (False, pattern_id)

    fix_func, needs_error = entry
    if needs_error:
        result = fix_func(module_path, error_output)  # type: ignore[operator]
    else:
        result = fix_func(module_path)  # type: ignore[operator]
    logger.info("run_docker_fix_loop: fix for '%s' returned %s", pattern_id, result)
    return (result, pattern_id)


def run_docker_fix_loop(
    module_path: Path,
    error_output: str,
    max_iterations: int = DEFAULT_MAX_FIX_ITERATIONS,
    revalidate_fn: object | None = None,
) -> Result[tuple[bool, str]]:
    """Run Docker error fixes in a loop with configurable iteration cap.

    Each iteration: identify error pattern -> dispatch fix -> if fix applied
    and revalidate_fn provided, call it to get new error_output -> repeat.
    If no revalidate_fn, runs a single pass.

    Args:
        module_path: Root path of the Odoo module.
        error_output: The error text from Docker validation.
        max_iterations: Maximum fix iterations (default 5).
        revalidate_fn: Optional callable returning Result[InstallResult] for re-validation.
            When provided, enables multi-iteration fixing.

    Returns:
        Result.ok((any_fix_applied, remaining_error_output)).
        When iteration cap is reached, remaining output includes escalation message.
    """
    import logging

    logger = logging.getLogger(__name__)

    any_fix_applied = False
    current_error = error_output
    tried_patterns: set[str] = set()

    for iteration in range(max_iterations):
        logger.debug("run_docker_fix_loop: iteration %d/%d", iteration + 1, max_iterations)

        fixed, pattern_id = _dispatch_docker_fix(
            module_path, current_error, tried_patterns,
        )

        if not fixed:
            logger.debug("run_docker_fix_loop: no fix applied in iteration %d", iteration + 1)
            break

        any_fix_applied = True
        if pattern_id is not None:
            tried_patterns.add(pattern_id)

        if revalidate_fn is None:
            # Single-pass mode (no re-validation)
            break

        # Re-validate to get new error output (revalidate_fn returns Result[InstallResult])
        revalidation_result = revalidate_fn()  # type: ignore[operator]
        if revalidation_result.success and revalidation_result.data and revalidation_result.data.success:
            logger.info("run_docker_fix_loop: re-validation succeeded after iteration %d", iteration + 1)
            current_error = ""
            break

        # Extract error output from the InstallResult inside the Result wrapper
        if revalidation_result.success and revalidation_result.data:
            install_data = revalidation_result.data
            current_error = install_data.log_output or install_data.error_message
        else:
            # Infrastructure error from docker_install_module
            current_error = "; ".join(revalidation_result.errors) if revalidation_result.errors else ""
        if not current_error or not current_error.strip():
            break
    else:
        # Loop completed without breaking -> cap reached
        if any_fix_applied and revalidate_fn is not None:
            cap_msg = (
                f"Iteration cap ({max_iterations}) reached. "
                "Remaining errors require manual review."
            )
            current_error = f"{current_error}\n{cap_msg}" if current_error else cap_msg
            logger.warning("run_docker_fix_loop: %s", cap_msg)

    return Result.ok((any_fix_applied, current_error))


# -------------------------------------------------------------------------
# Module-level auto-fix: unused imports (AFIX-02)
# -------------------------------------------------------------------------

def _find_all_name_references(tree: ast.Module, exclude_imports: bool = True) -> set[str]:
    """Collect every ast.Name.id in the module body, excluding import statements.

    This walks the full AST and returns all ``ast.Name`` node identifiers,
    optionally skipping names that appear on import lines (so we don't count
    ``from X import foo`` as a *usage* of ``foo``).

    Attribute access like ``api.constrains`` produces an ``ast.Attribute``
    whose ``value`` is ``ast.Name(id='api')``, so ``api`` is captured.
    """
    import_lines: set[int] = set()
    if exclude_imports:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for line_no in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                    import_lines.add(line_no)

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.lineno not in import_lines:
            names.add(node.id)
    return names


def _find_all_in_module(tree: ast.Module) -> set[str]:
    """Extract names listed in ``__all__`` if defined at module level.

    Returns the set of string constants found in the ``__all__`` list, or an
    empty set if ``__all__`` is not defined.
    """
    all_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                all_names.add(elt.value)
    return all_names


def fix_unused_imports(file_path: Path) -> bool:
    """Detect and remove unused imports in a generated Python file.

    Uses a full AST body scan to find all name references (``ast.Name``
    nodes) and compares against imported names.  Any imported name with
    zero references in the file body is removed.  Star imports are never
    removed.  Names listed in ``__all__`` are treated as used.

    Args:
        file_path: Path to the Python file to check.

    Returns:
        True if any imports were removed, False if no changes needed.
    """
    content = file_path.read_text(encoding="utf-8")
    if not content.strip():
        return False

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False

    # Collect all referenced names in the file body (excluding import lines)
    used_names = _find_all_name_references(tree)
    # Names in __all__ count as used
    used_names |= _find_all_in_module(tree)

    changes_made = False
    lines = content.split("\n")

    # Gather import nodes (both `import X` and `from X import Y`)
    import_nodes: list[ast.ImportFrom | ast.Import] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ImportFrom, ast.Import)):
            import_nodes.append(node)

    # Sort by line number descending so we can modify lines without shifting
    import_nodes.sort(key=lambda n: n.lineno, reverse=True)

    for node in import_nodes:
        if not node.names:
            continue

        # Skip star imports -- never remove them
        if any(alias.name == "*" for alias in node.names):
            continue

        start_idx = node.lineno - 1
        end_idx = (node.end_lineno or node.lineno) - 1
        if start_idx < 0 or end_idx >= len(lines):
            continue

        original_line = lines[start_idx]

        names_to_keep: list[str] = []
        names_to_remove: list[str] = []

        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            if name in used_names:
                names_to_keep.append(name)
            else:
                names_to_remove.append(name)

        if not names_to_remove:
            continue

        changes_made = True

        if not names_to_keep:
            # Remove the entire import line(s) (handles multi-line imports)
            for idx in range(start_idx, end_idx + 1):
                lines[idx] = ""
        else:
            # Rebuild the import line with only kept names
            module = node.module or "" if isinstance(node, ast.ImportFrom) else ""
            if isinstance(node, ast.ImportFrom):
                new_import = f"from {module} import {', '.join(names_to_keep)}"
            else:
                new_import = f"import {', '.join(names_to_keep)}"
            # Preserve leading indentation
            leading_space = ""
            for ch in original_line:
                if ch in (" ", "\t"):
                    leading_space += ch
                else:
                    break
            lines[start_idx] = leading_space + new_import
            # Clear any continuation lines for multi-line imports
            for idx in range(start_idx + 1, end_idx + 1):
                lines[idx] = ""

    if not changes_made:
        return False

    # Clean up empty lines left by removed imports (collapse consecutive blanks)
    new_lines: list[str] = []
    prev_empty = False
    for line in lines:
        is_empty = line.strip() == ""
        if is_empty and prev_empty:
            continue
        new_lines.append(line)
        prev_empty = is_empty

    new_content = "\n".join(new_lines)
    file_path.write_text(new_content, encoding="utf-8")
    return True
