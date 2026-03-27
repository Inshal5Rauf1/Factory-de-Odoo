"""Pylint-odoo auto-fix loops with escalation.

Mechanically fixes known pylint-odoo violation codes, re-validates, and
escalates remaining issues in a grouped file:line + suggestion format.

Docker-specific fix functions live in ``auto_fix_docker.py`` and are
re-exported here for backward compatibility.

QUAL-09: pylint auto-fix (6 fixable codes, configurable iterations)
AFIX-02: unused import auto-fix
"""

from __future__ import annotations

import ast
import logging
import re
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

from amil_utils.validation.pylint_runner import run_pylint_odoo
from amil_utils.validation.types import Result, Violation
from amil_utils.version_defaults import get_default_manifest_version

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
    "version": get_default_manifest_version(),
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


# -------------------------------------------------------------------------
# Backward-compatible re-exports from auto_fix_docker
# -------------------------------------------------------------------------

from amil_utils.auto_fix_docker import (  # noqa: E402, F401
    _dispatch_docker_fix,
    fix_manifest_load_order,
    fix_missing_acl,
    fix_missing_mail_thread,
    fix_xml_parse_error,
    run_docker_fix_loop,
)

__all__ = [
    # Constants
    "DEFAULT_MAX_FIX_ITERATIONS",
    "FIXABLE_DOCKER_PATTERNS",
    "FIXABLE_PYLINT_CODES",
    "_DOCKER_PATTERN_KEYWORDS",
    # Pylint
    "fix_pylint_violation",
    "fix_pylint_violations",
    "fix_unused_imports",
    "format_escalation",
    "identify_docker_fix",
    "is_fixable_pylint",
    "run_pylint_fix_loop",
    # Docker (re-exported)
    "_dispatch_docker_fix",
    "fix_manifest_load_order",
    "fix_missing_acl",
    "fix_missing_mail_thread",
    "fix_xml_parse_error",
    "run_docker_fix_loop",
]
