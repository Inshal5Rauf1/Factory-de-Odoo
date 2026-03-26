"""Centralized Odoo version defaults. Single source of truth.

Import from here instead of hardcoding version strings:

    from amil_utils.version_defaults import get_default_version
"""
from __future__ import annotations

DEFAULT_ODOO_VERSION: str = "19.0"
VALID_ODOO_VERSIONS: tuple[str, ...] = ("17.0", "18.0", "19.0")


def get_default_version() -> str:
    """Return the default Odoo target version."""
    return DEFAULT_ODOO_VERSION


def get_valid_versions() -> tuple[str, ...]:
    """Return all supported Odoo versions."""
    return VALID_ODOO_VERSIONS


def get_default_manifest_version(odoo_version: str | None = None) -> str:
    """Return the default module manifest version string.

    Format: ``{odoo_version}.1.0.0`` (e.g., ``19.0.1.0.0``).
    """
    v = odoo_version or DEFAULT_ODOO_VERSION
    return f"{v}.1.0.0"
