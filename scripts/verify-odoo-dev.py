#!/usr/bin/env python3
"""XML-RPC connectivity smoke test for Odoo dev instance.

Verifies:
  1. Server version is reachable
  2. Authentication succeeds
  3. ir.model is queryable (modules loaded)
  4. Required modules are installed (base, mail, sale, purchase, hr, account)

Usage:
  scripts/verify-odoo-dev.py

Environment variables (all optional, with sensible defaults):
  ODOO_URL           - Odoo server URL (default: http://localhost:{ODOO_DEV_PORT or 8069})
  ODOO_DEV_DB        - Database name (default: odoo_dev)
  ODOO_DEV_USER      - Admin username (default: admin)
  ODOO_DEV_PASSWORD   - Admin password (default: admin)
  ODOO_DEV_PORT      - Port (default: 8069, used to construct ODOO_URL if not set)
"""
import os
import sys
import xmlrpc.client


def verify_xmlrpc(
    url: str | None = None,
    db: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> bool:
    """Verify XML-RPC connectivity to the Odoo dev instance.

    Returns True if all checks pass, False otherwise.
    """
    port = os.environ.get("ODOO_DEV_PORT", "8069")
    url = url or os.environ.get("ODOO_URL", f"http://localhost:{port}")
    db = db or os.environ.get("ODOO_DEV_DB", "odoo_dev")
    username = username or os.environ.get("ODOO_DEV_USER", "admin")
    password = password or os.environ.get("ODOO_DEV_PASSWORD", "admin")

    try:
        # Step 1: Check server version
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        version_info = common.version()
        server_version = version_info.get("server_version", "unknown")
        print(f"Server version: {server_version}")

        # Step 2: Authenticate
        uid = common.authenticate(db, username, password, {})
        if not uid:
            print("ERROR: Authentication failed (uid=False)")
            return False
        print(f"Authenticated as uid={uid}")

        # Step 3: Query ir.model (proves modules are loaded)
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        model_count = models.execute_kw(
            db, uid, password,
            "ir.model", "search_count", [[]],
        )
        print(f"Models available: {model_count}")

        # Step 4: Verify required modules are installed
        installed = models.execute_kw(
            db, uid, password,
            "ir.module.module", "search_read",
            [[["state", "=", "installed"]]],
            {"fields": ["name"]},
        )
        installed_names = {m["name"] for m in installed}
        required = {"base", "mail", "sale", "purchase", "hr", "account"}
        missing = required - installed_names

        print(f"Installed modules: {len(installed_names)}")
        if missing:
            print(f"WARNING: Missing required modules: {missing}")
            return False
        print("All required modules installed.")
        return True

    except ConnectionRefusedError:
        print("ERROR: Connection refused. Is Odoo running?")
        print(f"  Tried: {url}")
        return False
    except xmlrpc.client.Fault as exc:
        print(f"ERROR: XML-RPC fault: {exc.faultString}")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        return False


if __name__ == "__main__":
    success = verify_xmlrpc()
    sys.exit(0 if success else 1)
