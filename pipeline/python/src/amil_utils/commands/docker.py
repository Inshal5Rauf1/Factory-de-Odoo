"""Business logic for the ``factory-docker`` CLI command.

Pure Python -- no Click dependency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def execute_factory_docker(
    *,
    action: str | None = None,
    install: str | None = None,
    test: str | None = None,
    cross_test: tuple[str, ...] = (),
    url: bool = False,
    history: bool = False,
    state_dir: str = ".planning",
) -> dict[str, Any]:
    """Manage the persistent Docker factory instance.

    Returns a result dict with keys:
        - output: str -- primary output text
        - error: str | None -- error message
        - exit_code: int -- 0 for success, 1 for failure
    """
    from amil_utils.validation.persistent_docker import PersistentDockerManager

    mgr = PersistentDockerManager()
    sd = Path(state_dir)

    if url:
        return {"output": mgr.get_web_url(), "error": None, "exit_code": 0}

    if history:
        mgr._state_dir = sd
        mgr._load_state()
        return {"output": json.dumps(mgr.get_install_history(), indent=2), "error": None, "exit_code": 0}

    if action == "status":
        mgr._state_dir = sd
        mgr._load_state()
        running = mgr._running and mgr._health_check()
        data = {
            "running": running,
            "installed_count": len(mgr.installed_modules),
            "installed_modules": mgr.installed_modules,
            "url": mgr.get_web_url() if running else None,
        }
        return {"output": json.dumps(data, indent=2), "error": None, "exit_code": 0}

    if action == "start":
        ok = mgr.ensure_running(state_dir=sd)
        if ok:
            return {
                "output": f"Persistent Docker instance is running.\nAccess Odoo at {mgr.get_web_url()}",
                "error": None,
                "exit_code": 0,
            }
        return {"output": "", "error": "Failed to start persistent Docker instance.", "exit_code": 1}

    if action == "stop":
        mgr._state_dir = sd
        mgr._load_state()
        mgr.stop()
        return {"output": "Persistent Docker instance stopped (data preserved).", "error": None, "exit_code": 0}

    if action == "reset":
        mgr._state_dir = sd
        mgr._load_state()
        mgr.reset()
        return {"output": "Persistent Docker instance destroyed (all data removed).", "error": None, "exit_code": 0}

    if install:
        mgr._state_dir = sd
        mgr._load_state()
        if not mgr._running:
            return {"output": "", "error": "Docker not running. Start with: factory-docker --action start", "exit_code": 1}
        r = mgr.install_module(Path(install))
        if r.success and r.data and r.data.success:
            return {
                "output": f"Installed {Path(install).name} successfully.\nTotal modules: {len(mgr.installed_modules)}",
                "error": None,
                "exit_code": 0,
            }
        msg = r.data.error_message if r.success and r.data else "; ".join(r.errors)
        return {"output": "", "error": f"Install failed: {msg}", "exit_code": 1}

    if test:
        mgr._state_dir = sd
        mgr._load_state()
        r = mgr.run_module_tests(Path(test))
        if r.success:
            return {"output": f"Tests completed for {Path(test).name}.", "error": None, "exit_code": 0}
        return {"output": "", "error": f"Test run failed: {'; '.join(r.errors)}", "exit_code": 1}

    if cross_test:
        mgr._state_dir = sd
        mgr._load_state()
        r = mgr.run_cross_module_test(list(cross_test))
        if r.success:
            return {"output": f"Cross-module tests completed for: {', '.join(cross_test)}", "error": None, "exit_code": 0}
        return {"output": "", "error": f"Cross-module test failed: {'; '.join(r.errors)}", "exit_code": 1}

    return {"output": "", "error": "Specify --action, --install, --test, --cross-test, --url, or --history.", "exit_code": 1}
