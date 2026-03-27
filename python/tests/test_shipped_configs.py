"""Tests that shipped config files don't contain hardcoded passwords."""
from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "src" / "amil_utils" / "data"


class TestNoHardcodedCredentials:
    def test_odoo_conf_no_hardcoded_db_password(self):
        content = (DATA_DIR / "odoo.conf").read_text()
        assert "db_password = odoo" not in content
        assert "db_password=odoo" not in content

    def test_odoo_conf_no_hardcoded_admin_password(self):
        content = (DATA_DIR / "odoo.conf").read_text()
        assert "admin_passwd = admin" not in content
        assert "admin_passwd=admin" not in content

    def test_compose_no_hardcoded_postgres_password(self):
        content = (DATA_DIR / "docker-compose.yml").read_text()
        assert "POSTGRES_PASSWORD: odoo" not in content

    def test_persistent_compose_no_fallback_password(self):
        content = (DATA_DIR / "docker" / "persistent-compose.yml").read_text()
        # Password lines should NOT have fallback default :-odoo
        for line in content.splitlines():
            if "PASSWORD" in line.upper():
                assert ":-odoo" not in line, (
                    f"Password line has insecure fallback: {line.strip()}"
                )
