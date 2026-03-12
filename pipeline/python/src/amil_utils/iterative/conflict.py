"""Three-way conflict detection for iterative refinement.

Provides:
- ``ConflictResult`` — frozen dataclass classifying affected files into
  safe-to-overwrite, conflicts, and stub-mergeable categories.
- ``detect_conflicts`` — compares manifest checksums against current
  file state to determine the safest update strategy.

Uses the manifest's per-file SHA256 checksums as the "base" version.
When a file's current hash differs from the manifest, stub-zone analysis
determines whether the edits are confined to BUSINESS LOGIC markers
(safe to auto-merge) or extend into structural code (requires manual
resolution).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from odoo_gen_utils.logic_writer.stub_detector import _find_stub_zones
from odoo_gen_utils.manifest import compute_file_sha256

if TYPE_CHECKING:
    from odoo_gen_utils.manifest import GenerationManifest

logger = logging.getLogger("odoo-gen.iterative.conflict")


@dataclass(frozen=True)
class ConflictResult:
    """Immutable classification of files into conflict categories.

    Attributes:
        safe_to_overwrite: Files unchanged since generation (hash match)
            or new files not in the manifest.
        conflicts: Files edited outside stub zones -- require manual review.
        stub_mergeable: Files edited only within BUSINESS LOGIC zones --
            safe for automatic stub-zone merge.
    """

    safe_to_overwrite: tuple[str, ...]
    conflicts: tuple[str, ...]
    stub_mergeable: tuple[str, ...]


def _lines_outside_zones(lines: list[str]) -> list[str]:
    """Extract lines that are OUTSIDE BUSINESS LOGIC zones.

    Zone markers (START/END) are considered outside (template-generated).
    Content between markers is inside (user-editable) and excluded.
    """
    zones = _find_stub_zones(lines)

    # Build a set of 1-based line numbers inside zones (content only,
    # exclusive of marker lines themselves)
    inside: set[int] = set()
    for zone in zones:
        for line_no in range(zone["start_line"] + 1, zone["end_line"]):
            inside.add(line_no)

    return [
        line for idx, line in enumerate(lines, start=1)
        if idx not in inside
    ]


def _edits_only_in_stub_zones(
    skeleton_lines: list[str],
    current_lines: list[str],
) -> bool:
    """Return True if ALL differences between skeleton and current are within stub zones.

    Extracts lines outside zones from both files and compares the
    sequences. If the outside-zone lines are identical, all edits
    are confined to stub zones and safe for automatic merge.

    This approach handles line count changes within zones (e.g. user
    replaced ``pass`` with a multi-line implementation) without false
    positives from shifted line indices.
    """
    skel_outside = _lines_outside_zones(skeleton_lines)
    curr_outside = _lines_outside_zones(current_lines)
    return skel_outside == curr_outside


def detect_conflicts(
    manifest: "GenerationManifest",
    affected_files: list[str],
    module_dir: Path,
    skeleton_dir: Path | None = None,
) -> ConflictResult:
    """Classify affected files into safe, conflict, or stub-mergeable.

    For each file in *affected_files*:
    1. Look up its ArtifactEntry in the manifest.
    2. If not in manifest -> safe (new file, no prior version).
    3. If file doesn't exist on disk -> safe (will be created fresh).
    4. Compute current SHA256 and compare against manifest hash.
    5. Hash match -> safe_to_overwrite.
    6. Hash mismatch -> check if edits are only within stub zones:
       - If skeleton_dir is provided and skeleton file exists, compare
         skeleton vs current. If all differences are within BUSINESS
         LOGIC zones -> stub_mergeable.
       - Otherwise -> conflicts.

    Args:
        manifest: The generation manifest with per-file checksums.
        affected_files: List of relative file paths to check.
        module_dir: Path to the generated module directory.
        skeleton_dir: Optional path to the skeleton copy for
            three-way stub-zone comparison.

    Returns:
        ``ConflictResult`` with files classified into three categories.
    """
    safe: list[str] = []
    conflicts: list[str] = []
    mergeable: list[str] = []

    # Build a lookup from path -> ArtifactEntry
    artifact_lookup: dict[str, str] = {}
    for entry in manifest.artifacts.files:
        artifact_lookup[entry.path] = entry.sha256

    for rel_path in affected_files:
        # Step 1: Check if in manifest
        manifest_sha = artifact_lookup.get(rel_path)
        if manifest_sha is None:
            # New file, not tracked -> safe to create
            safe.append(rel_path)
            continue

        # Step 2: Check if file exists on disk
        file_path = module_dir / rel_path
        if not file_path.exists():
            # File deleted by user -> safe to create fresh
            safe.append(rel_path)
            continue

        # Step 3: Compare hashes
        try:
            current_sha = compute_file_sha256(file_path)
        except OSError:
            logger.warning("Cannot read %s, treating as conflict", rel_path)
            conflicts.append(rel_path)
            continue

        if current_sha == manifest_sha:
            # Unchanged since generation -> safe
            safe.append(rel_path)
            continue

        # Step 4: Hash mismatch -> check stub zones
        if skeleton_dir is not None:
            skeleton_path = skeleton_dir / rel_path
            if skeleton_path.exists():
                try:
                    skeleton_lines = skeleton_path.read_text(encoding="utf-8").splitlines()
                    current_lines = file_path.read_text(encoding="utf-8").splitlines()

                    if _edits_only_in_stub_zones(skeleton_lines, current_lines):
                        mergeable.append(rel_path)
                        continue
                except OSError:
                    logger.warning("Cannot read skeleton for %s", rel_path)

        # All other cases -> conflict
        conflicts.append(rel_path)

    return ConflictResult(
        safe_to_overwrite=tuple(safe),
        conflicts=tuple(conflicts),
        stub_mergeable=tuple(mergeable),
    )
