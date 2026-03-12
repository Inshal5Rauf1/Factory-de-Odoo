"""Public API for the OCA module search package."""

from odoo_gen_utils.search.analyzer import (  # noqa: F401
    ModuleAnalysis,
    analyze_module,
    format_analysis_text,
)
from odoo_gen_utils.search.fork import (  # noqa: F401
    clone_oca_module,
    setup_companion_dir,
)
from odoo_gen_utils.search.index import (  # noqa: F401
    build_oca_index,
    get_github_token,
    get_index_status,
)
from odoo_gen_utils.search.query import (  # noqa: F401
    SearchResult,
    format_results_json,
    format_results_text,
    search_modules,
)
from odoo_gen_utils.search.types import IndexEntry, IndexStatus  # noqa: F401
from odoo_gen_utils.search.wizard import (  # noqa: F401
    AuthStatus,
    check_github_auth,
    format_auth_guidance,
)

__all__ = [
    "ModuleAnalysis",
    "analyze_module",
    "clone_oca_module",
    "build_oca_index",
    "format_analysis_text",
    "format_results_json",
    "format_results_text",
    "get_github_token",
    "get_index_status",
    "IndexEntry",
    "IndexStatus",
    "SearchResult",
    "search_modules",
    "setup_companion_dir",
    "AuthStatus",
    "check_github_auth",
    "format_auth_guidance",
]
