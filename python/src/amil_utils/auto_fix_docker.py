"""Docker auto-fix loops with escalation.

Mechanically fixes known Docker error patterns (XML parse errors, missing ACLs,
manifest load order, missing mail.thread inheritance), re-validates, and
escalates remaining issues.

Extracted from auto_fix.py to keep each file under ~800 lines.

QUAL-10: Docker auto-fix (5 fixable patterns, configurable iterations)
AFIX-01: missing mail.thread auto-fix
DFIX-01: 3 Docker fix functions (xml_parse_error, missing_acl, manifest_load_order)
"""

from __future__ import annotations

import ast
import csv
import io
import logging
import re
from pathlib import Path

from amil_utils.auto_fix import (
    DEFAULT_MAX_FIX_ITERATIONS,
    _DOCKER_PATTERN_KEYWORDS,
    fix_unused_imports,
    identify_docker_fix,
)
from amil_utils.validation.types import Result

logger = logging.getLogger(__name__)

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
