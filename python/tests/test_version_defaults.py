"""Tests for centralized Odoo version defaults."""
from __future__ import annotations

from amil_utils.version_defaults import (
    DEFAULT_ODOO_VERSION,
    VALID_ODOO_VERSIONS,
    get_default_version,
    get_valid_versions,
    get_default_manifest_version,
)


class TestVersionDefaults:
    def test_default_version_is_19(self):
        assert get_default_version() == "19.0"

    def test_default_version_matches_constant(self):
        assert get_default_version() == DEFAULT_ODOO_VERSION

    def test_valid_versions_includes_all_supported(self):
        versions = get_valid_versions()
        assert "17.0" in versions
        assert "18.0" in versions
        assert "19.0" in versions

    def test_valid_versions_is_tuple(self):
        assert isinstance(get_valid_versions(), tuple)

    def test_default_manifest_version(self):
        assert get_default_manifest_version() == "19.0.1.0.0"

    def test_manifest_version_for_17(self):
        assert get_default_manifest_version("17.0") == "17.0.1.0.0"

    def test_manifest_version_for_18(self):
        assert get_default_manifest_version("18.0") == "18.0.1.0.0"
