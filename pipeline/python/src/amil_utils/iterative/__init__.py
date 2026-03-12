"""Iterative refinement subpackage for spec change detection and safe re-generation.

Provides:
- Spec stash management (save/load .odoo-gen-spec.json)
- Spec diff orchestration (compute_spec_diff)
- Diff-to-stage mapping (determine_affected_stages, AffectedStages)
- Three-way conflict detection (detect_conflicts, ConflictResult)
- Stub-zone-aware merge (extract_filled_stubs, inject_stubs_into)
- Conflict resolution (resolve_status, resolve_accept_new, resolve_keep_mine,
  resolve_accept_all, PENDING_DIR_NAME)
"""

from odoo_gen_utils.iterative.diff import (
    compute_spec_diff,
    load_spec_stash,
    save_spec_stash,
)
from odoo_gen_utils.iterative.affected import (
    AffectedStages,
    determine_affected_stages,
)
from odoo_gen_utils.iterative.conflict import (
    ConflictResult,
    detect_conflicts,
)
from odoo_gen_utils.iterative.merge import (
    extract_filled_stubs,
    inject_stubs_into,
)
from odoo_gen_utils.iterative.resolve import (
    PENDING_DIR_NAME,
    resolve_accept_all,
    resolve_accept_new,
    resolve_keep_mine,
    resolve_status,
)

__all__ = [
    "save_spec_stash",
    "load_spec_stash",
    "compute_spec_diff",
    "determine_affected_stages",
    "AffectedStages",
    "detect_conflicts",
    "ConflictResult",
    "extract_filled_stubs",
    "inject_stubs_into",
    "resolve_status",
    "resolve_accept_new",
    "resolve_keep_mine",
    "resolve_accept_all",
    "PENDING_DIR_NAME",
]
