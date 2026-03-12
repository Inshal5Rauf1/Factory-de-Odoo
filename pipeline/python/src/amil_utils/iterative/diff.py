"""Spec stash management and diff orchestration for iterative refinement.

Provides:
- ``save_spec_stash`` / ``load_spec_stash`` — persist raw spec as
  ``.odoo-gen-spec.json`` sidecar for later diffing.
- ``compute_spec_diff`` — SHA256-gated diff returning ``SpecDiff | None``.

These are **pure functions** (except file I/O for stash persistence).
No coupling to renderer.py or cli.py.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from odoo_gen_utils.manifest import compute_spec_sha256
from odoo_gen_utils.spec_differ import diff_specs

if TYPE_CHECKING:
    from odoo_gen_utils.spec_differ import SpecDiff

logger = logging.getLogger("odoo-gen.iterative.diff")

SPEC_STASH_FILENAME = ".odoo-gen-spec.json"


def save_spec_stash(spec: dict, module_path: Path) -> Path:
    """Write *spec* as canonical JSON to ``module_path / .odoo-gen-spec.json``.

    Uses ``sort_keys=True`` for deterministic output and a trailing newline.
    Stashes the RAW spec (before preprocessing) so that future diffs compare
    user-authored content, not preprocessor-injected metadata.

    Returns the path to the written file.
    """
    stash_path = module_path / SPEC_STASH_FILENAME
    stash_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(spec, sort_keys=True, indent=2) + "\n"
    stash_path.write_text(content, encoding="utf-8")
    logger.debug("Spec stash saved: %s", stash_path)
    return stash_path


def load_spec_stash(module_path: Path) -> dict | None:
    """Load a previously stashed spec from ``module_path / .odoo-gen-spec.json``.

    Returns ``None`` when the file does not exist or is invalid JSON.
    """
    stash_path = module_path / SPEC_STASH_FILENAME
    if not stash_path.exists():
        return None

    raw = stash_path.read_text(encoding="utf-8").strip()
    if not raw:
        logger.warning("Spec stash file is empty: %s", stash_path)
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse spec stash %s: %s", stash_path, exc)
        return None


def compute_spec_diff(old_spec: dict, new_spec: dict) -> "SpecDiff | None":
    """Compute the diff between two spec versions.

    Uses SHA256 comparison for fast identity check. When the canonical
    hashes match, returns ``None`` (no changes). Otherwise delegates to
    ``diff_specs()`` from ``spec_differ.py``.

    Args:
        old_spec: The previously stashed spec.
        new_spec: The new spec provided by the user.

    Returns:
        A ``SpecDiff`` dict when changes are detected, or ``None`` when
        the two specs are identical.
    """
    old_hash = compute_spec_sha256(old_spec)
    new_hash = compute_spec_sha256(new_spec)

    if old_hash == new_hash:
        logger.info("Spec unchanged (sha256: %s). Nothing to do.", old_hash[:12])
        return None

    logger.info(
        "Spec changed: %s -> %s. Computing diff.",
        old_hash[:12],
        new_hash[:12],
    )
    return diff_specs(old_spec, new_spec)
