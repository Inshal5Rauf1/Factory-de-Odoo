"""Shared pytest fixtures and configuration for the amil-utils test suite.

Provides:
- Auto-skip fixture for tests marked ``@pytest.mark.docker`` when Docker
  daemon is unavailable or when a required Odoo instance is unreachable.
"""
from __future__ import annotations

import xmlrpc.client

import pytest


# ---------------------------------------------------------------------------
# Docker / Odoo availability helpers
# ---------------------------------------------------------------------------


def _is_docker_functional() -> bool:
    """Return True when Docker daemon is reachable and responsive."""
    try:
        from amil_utils.validation.docker_runner import check_docker_available

        return check_docker_available()
    except Exception:
        return False


def _is_odoo_reachable() -> bool:
    """Return True when a live Odoo instance responds at localhost:8069."""
    try:
        proxy = xmlrpc.client.ServerProxy(
            "http://localhost:8069/xmlrpc/2/common",
            allow_none=True,
        )
        proxy.version()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Autouse fixture: skip docker-marked tests when Docker is unavailable
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _skip_docker_when_unavailable(request: pytest.FixtureRequest) -> None:
    """Auto-skip tests decorated with ``@pytest.mark.docker``.

    * If Docker daemon is not functional -> skip.
    * If the test also exercises the *verifier* (node ID contains
      ``verifier``) and the local Odoo instance is unreachable -> skip.
    """
    marker = request.node.get_closest_marker("docker")
    if marker is None:
        return

    if not _is_docker_functional():
        pytest.skip("Docker daemon not available")

    if "verifier" in request.node.nodeid and not _is_odoo_reachable():
        pytest.skip("Odoo instance not reachable at localhost:8069")
