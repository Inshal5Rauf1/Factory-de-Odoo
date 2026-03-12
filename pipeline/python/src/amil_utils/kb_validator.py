"""Knowledge base format validator for custom and shipped rule files.

Validates markdown structure (headings, code blocks, line count) without
performing any semantic validation of rule content.
"""

from __future__ import annotations

from pathlib import Path


MAX_LINES = 500


def validate_kb_file(path: Path) -> dict:
    """Validate a single knowledge base markdown file for expected structure.

    Checks performed (format-only, no semantic validation):
      1. File is valid markdown (not empty, starts with ``#`` heading)
      2. Contains at least one rule section (line starting with ``### ``)
      3. Contains at least one code block (triple backtick)
      4. Does not exceed 500 lines
      5. Has no unclosed code blocks

    Args:
        path: Path to the ``.md`` file to validate.

    Returns:
        A dict with keys ``valid`` (bool), ``errors`` (list[str]),
        and ``warnings`` (list[str]).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # -- Basic file checks ------------------------------------------------
    if not path.exists():
        return {"valid": False, "errors": [f"File not found: {path}"], "warnings": []}

    if not path.is_file():
        return {"valid": False, "errors": [f"Not a file: {path}"], "warnings": []}

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"valid": False, "errors": [f"Cannot read file: {exc}"], "warnings": []}

    lines = content.split("\n")

    # -- Check 1: Not empty and starts with heading -----------------------
    if not content.strip():
        errors.append("File is empty")
        return {"valid": False, "errors": errors, "warnings": warnings}

    first_non_empty = ""
    for line in lines:
        stripped = line.strip()
        if stripped:
            first_non_empty = stripped
            break

    if not first_non_empty.startswith("#"):
        errors.append(
            f"File must start with a markdown heading (``#``), "
            f"found: {first_non_empty[:60]!r}"
        )

    # -- Check 2: At least one rule section (### heading) -----------------
    rule_sections = [line for line in lines if line.startswith("### ")]
    if not rule_sections:
        errors.append("No rule sections found (expected at least one ``### `` heading)")

    # -- Check 3: At least one code block ---------------------------------
    code_fence_count = sum(1 for line in lines if line.strip().startswith("```"))
    if code_fence_count == 0:
        errors.append("No code blocks found (expected at least one triple-backtick block)")

    # -- Check 4: Line count within limit ---------------------------------
    line_count = len(lines)
    if line_count > MAX_LINES:
        errors.append(
            f"File has {line_count} lines (maximum is {MAX_LINES}). "
            f"Split into subcategory files to stay within the limit."
        )

    # -- Check 5: No unclosed code blocks ---------------------------------
    if code_fence_count % 2 != 0:
        errors.append(
            f"Unclosed code block detected ({code_fence_count} triple-backtick "
            f"lines found, expected an even number)"
        )

    # -- Warnings (non-fatal) ---------------------------------------------
    if rule_sections and code_fence_count >= 2 and len(rule_sections) * 2 > code_fence_count:
        warnings.append(
            "Some rule sections may lack code examples "
            f"({len(rule_sections)} rules, {code_fence_count // 2} code blocks)"
        )

    if line_count > MAX_LINES * 0.8:
        warnings.append(
            f"File is {line_count} lines ({line_count * 100 // MAX_LINES}% of "
            f"{MAX_LINES}-line limit). Consider splitting soon."
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def validate_kb_directory(path: Path) -> dict:
    """Validate all ``.md`` files in a knowledge base directory.

    Args:
        path: Directory path to scan for ``.md`` files.

    Returns:
        A dict with keys:
        - ``valid`` (bool): True if **all** files pass validation.
        - ``files`` (dict[str, dict]): Per-file validation results keyed by filename.
        - ``summary`` (dict): Counts of total, valid, invalid, and warnings.
    """
    if not path.exists():
        return {
            "valid": False,
            "files": {},
            "summary": {"total": 0, "valid": 0, "invalid": 0, "warnings": 0},
        }

    if not path.is_dir():
        return {
            "valid": False,
            "files": {},
            "summary": {"total": 0, "valid": 0, "invalid": 0, "warnings": 0},
        }

    md_files = sorted(path.glob("*.md"))

    # Skip README.md in custom/ directory (it's documentation, not a rule file)
    md_files = [f for f in md_files if f.name != "README.md"]

    if not md_files:
        return {
            "valid": True,
            "files": {},
            "summary": {"total": 0, "valid": 0, "invalid": 0, "warnings": 0},
        }

    file_results: dict[str, dict] = {}
    total_valid = 0
    total_invalid = 0
    total_warnings = 0

    for md_file in md_files:
        result = validate_kb_file(md_file)
        file_results[md_file.name] = result
        if result["valid"]:
            total_valid += 1
        else:
            total_invalid += 1
        if result["warnings"]:
            total_warnings += 1

    return {
        "valid": total_invalid == 0,
        "files": file_results,
        "summary": {
            "total": len(md_files),
            "valid": total_valid,
            "invalid": total_invalid,
            "warnings": total_warnings,
        },
    }
