"""Static i18n .pot file extractor for Odoo modules.

Extracts translatable strings from Python files (_() calls via ast)
and XML files (string= attributes via xml.etree.ElementTree), then
generates a standard Odoo .pot file.

No live Odoo server required -- pure static analysis.
"""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def extract_python_strings(file_path: Path) -> list[tuple[str, str, int]]:
    """Extract translatable strings from a Python file.

    Finds two patterns:
    1. _("text") calls — standard Odoo translation markers
    2. fields.*(string="text") — field label declarations (auto-translated by Odoo)

    Uses ast.parse() to build AST and walks for Call nodes matching
    either pattern.

    Args:
        file_path: Path to the Python file to scan.

    Returns:
        List of (msgid, filename, line_number) tuples.
    """
    source = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    results: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # Pattern 1: _("text") calls
        if isinstance(node.func, ast.Name) and node.func.id == "_":
            if node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(
                    first_arg.value, str
                ):
                    results.append((first_arg.value, str(file_path), node.lineno))

        # Pattern 2: fields.*(string="text") keyword arguments
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "fields"
        ):
            for kw in node.keywords:
                if (
                    kw.arg == "string"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    results.append((kw.value.value, str(file_path), node.lineno))

    return results


def extract_xml_strings(file_path: Path) -> list[tuple[str, str, int]]:
    """Extract translatable strings from an XML file.

    Scans all elements for ``string`` attribute values and ``<label>``
    elements for text content.  Uses 0 as line number because
    ElementTree does not track line numbers reliably.

    Malformed XML is handled gracefully (returns empty list, no crash).

    Args:
        file_path: Path to the XML file to scan.

    Returns:
        List of (msgid, filename, line_number) tuples.
    """
    try:
        tree = ET.parse(str(file_path))  # noqa: S314
    except ET.ParseError:
        return []

    results: list[tuple[str, str, int]] = []
    for elem in tree.iter():
        string_attr = elem.get("string")
        if string_attr:
            results.append((string_attr, str(file_path), 0))
        if elem.tag == "label" and elem.text and elem.text.strip():
            results.append((elem.text.strip(), str(file_path), 0))

    return results


def extract_translatable_strings(module_path: Path) -> list[tuple[str, str, int]]:
    """Scan a module directory recursively for all translatable strings.

    Calls extract_python_strings on every .py file and
    extract_xml_strings on every .xml file.

    Args:
        module_path: Root path of the Odoo module to scan.

    Returns:
        Combined, sorted list of (msgid, filename, line_number) tuples.
    """
    results: list[tuple[str, str, int]] = []

    for py_file in sorted(module_path.rglob("*.py")):
        results = [*results, *extract_python_strings(py_file)]

    for xml_file in sorted(module_path.rglob("*.xml")):
        results = [*results, *extract_xml_strings(xml_file)]

    return sorted(results, key=lambda t: (t[1], t[2], t[0]))


def generate_pot(module_name: str, strings: list[tuple[str, str, int]]) -> str:
    """Generate a .pot file content string with standard Odoo header.

    Deduplicates identical msgid strings by merging their source
    references.  Always produces the header even when no strings
    are found (per project decision: never skip generation).

    Args:
        module_name: Technical name of the Odoo module.
        strings: List of (msgid, filename, line_number) tuples.

    Returns:
        Complete POT file content as a string.
    """
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M+0000")

    header = (
        f"# Translation of {module_name}.pot in English\n"
        f"# This file contains the translation of the following modules:\n"
        f"# * {module_name}\n"
        'msgid ""\n'
        'msgstr ""\n'
        f'"Project-Id-Version: Odoo Server 19.0\\n"\n'
        f'"Report-Msgid-Bugs-To: \\n"\n'
        f'"POT-Creation-Date: {timestamp}\\n"\n'
        f'"PO-Revision-Date: \\n"\n'
        f'"Last-Translator: \\n"\n'
        f'"Language-Team: \\n"\n'
        f'"MIME-Version: 1.0\\n"\n'
        f'"Content-Type: text/plain; charset=UTF-8\\n"\n'
        f'"Content-Transfer-Encoding: \\n"\n'
        f'"Plural-Forms: \\n"\n'
    )

    if not strings:
        return header

    # Deduplicate msgids, merging source references
    msgid_refs: dict[str, list[str]] = {}
    for msgid, filename, line in strings:
        ref = f"{filename}:{line}"
        if msgid not in msgid_refs:
            msgid_refs[msgid] = []
        msgid_refs[msgid] = [*msgid_refs[msgid], ref]

    entries: list[str] = []
    for msgid, refs in msgid_refs.items():
        ref_lines = "\n".join(f"#: {r}" for r in refs)
        entry = f"\n{ref_lines}\n" f'msgid "{msgid}"\n' f'msgstr ""\n'
        entries.append(entry)

    return header + "".join(entries)
