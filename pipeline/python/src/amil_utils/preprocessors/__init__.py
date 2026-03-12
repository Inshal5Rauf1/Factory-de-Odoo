"""Preprocessor package with auto-discovery and backward-compatible exports."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any

from odoo_gen_utils.preprocessors._registry import (
    get_registered_preprocessors,
    register_preprocessor,
)

# Auto-discover all submodules (triggers @register_preprocessor decorators)
_pkg_path = str(Path(__file__).parent)
for _finder, _name, _ispkg in pkgutil.iter_modules([_pkg_path]):
    if not _name.startswith("_"):
        importlib.import_module(f"{__name__}.{_name}")


def _rediscover() -> None:
    """Re-import submodules to re-register preprocessors after a registry clear."""
    import sys

    for _finder2, _name2, _ispkg2 in pkgutil.iter_modules([_pkg_path]):
        if not _name2.startswith("_"):
            fqn = f"{__name__}.{_name2}"
            if fqn in sys.modules:
                importlib.reload(sys.modules[fqn])
            else:
                importlib.import_module(fqn)


def run_preprocessors(spec: dict[str, Any]) -> dict[str, Any]:
    """Execute all registered preprocessors in order.

    Each preprocessor receives the spec dict and returns a new spec dict.
    This is the primary public API for the preprocessor pipeline.

    If the registry is empty (e.g. after clear_registry() in tests),
    submodules are re-imported to restore all registrations.
    """
    if not get_registered_preprocessors():
        _rediscover()
    for _order, _name, fn in get_registered_preprocessors():
        spec = fn(spec)
    return spec


# ---------------------------------------------------------------------------
# Backward-compatible re-exports
# ---------------------------------------------------------------------------
# Every function that was importable from the old monolith preprocessors.py
# must still be importable via `from odoo_gen_utils.preprocessors import X`.

from odoo_gen_utils.preprocessors.relationships import (  # noqa: E402,F401
    _enrich_self_referential_m2m,
    _init_override_sources,
    _inject_one2many_links,
    _process_relationships,
    _resolve_comodel,
    _synthesize_through_model,
)
from odoo_gen_utils.preprocessors.validation import (  # noqa: E402,F401
    _validate_no_cycles,
)
from odoo_gen_utils.preprocessors.computation_chains import (  # noqa: E402,F401
    _process_computation_chains,
)
from odoo_gen_utils.preprocessors.constraints import (  # noqa: E402,F401
    _process_constraints,
)
from odoo_gen_utils.preprocessors.performance import (  # noqa: E402,F401
    _enrich_model_performance,
    _process_performance,
)
from odoo_gen_utils.preprocessors.production import (  # noqa: E402,F401
    _process_production_patterns,
)
from odoo_gen_utils.preprocessors.security import (  # noqa: E402,F401
    _inject_legacy_security,
    _parse_crud,
    _process_security_patterns,
    _security_auto_fix_views,
    _security_build_acl_matrix,
    _security_build_roles,
    _security_detect_record_rule_scopes,
    _security_enrich_fields,
    _security_validate_spec,
)
from odoo_gen_utils.preprocessors.audit import (  # noqa: E402,F401
    _build_audit_log_model,
    _process_audit_patterns,
)
from odoo_gen_utils.preprocessors.approval import (  # noqa: E402,F401
    _process_approval_patterns,
)
from odoo_gen_utils.preprocessors.notifications import (  # noqa: E402,F401
    _process_notification_patterns,
    _resolve_recipient,
    _select_body_fields,
)
from odoo_gen_utils.preprocessors.webhooks import (  # noqa: E402,F401
    _process_webhook_patterns,
)
from odoo_gen_utils.preprocessors.bulk_operations import (  # noqa: E402,F401
    _process_bulk_operations,
)
from odoo_gen_utils.preprocessors.portal import (  # noqa: E402,F401
    _process_portal,
)
from odoo_gen_utils.preprocessors.extensions import (  # noqa: E402,F401
    _process_extensions,
)
from odoo_gen_utils.preprocessors.archival import (  # noqa: E402,F401
    _process_archival_strategy,
)
from odoo_gen_utils.preprocessors.controllers import (  # noqa: E402,F401
    _process_controllers,
)
