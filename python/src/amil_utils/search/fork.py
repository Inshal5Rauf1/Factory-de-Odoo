"""Git sparse checkout clone for OCA modules.

Clones individual modules from OCA GitHub repositories using git sparse
checkout for efficient partial cloning. Also provides companion directory
setup for fork-and-extend workflows.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_SAFE_REPO_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
_SAFE_BRANCH = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9./_-]*$")
_SAFE_MODULE_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


def _validate_clone_inputs(repo_name: str, module_name: str, branch: str) -> None:
    """Validate inputs for clone_oca_module to prevent path traversal."""
    if not _SAFE_REPO_NAME.match(repo_name):
        raise ValueError(f"Unsafe repo_name: {repo_name!r}")
    if not _SAFE_MODULE_NAME.match(module_name):
        raise ValueError(f"Unsafe module_name: {module_name!r}")
    if not _SAFE_BRANCH.match(branch):
        raise ValueError(f"Unsafe branch: {branch!r}")


def clone_oca_module(
    repo_name: str,
    module_name: str,
    output_dir: Path,
    branch: str = "19.0",
) -> Path:
    """Clone a single OCA module via git sparse checkout.

    Uses ``--no-checkout --filter=blob:none --sparse`` for efficient
    partial cloning. Only the specified module directory is checked out.

    Args:
        repo_name: OCA repository name (e.g., "sale-workflow").
        module_name: Module directory name within the repo (e.g., "sale_order_type").
        output_dir: Parent directory where the clone will be created.
        branch: Git branch to clone (default: "19.0").

    Returns:
        Path to the cloned module directory (clone_dir / module_name).

    Raises:
        subprocess.CalledProcessError: If any git command fails (check=True).
    """
    _validate_clone_inputs(repo_name, module_name, branch)
    repo_url = f"https://github.com/OCA/{repo_name}.git"
    clone_dir = output_dir / f"oca_{repo_name}"

    # Step 1: Clone with sparse checkout flags
    subprocess.run(
        [
            "git", "clone",
            "--no-checkout",
            "--filter=blob:none",
            "--sparse",
            "-b", branch,
            repo_url,
            str(clone_dir),
        ],
        check=True,
    )

    # Step 2: Set sparse-checkout to only include the target module
    subprocess.run(
        ["git", "-C", str(clone_dir), "sparse-checkout", "set", module_name],
        check=True,
    )

    # Step 3: Checkout the branch
    subprocess.run(
        ["git", "-C", str(clone_dir), "checkout", branch],
        check=True,
    )

    return clone_dir / module_name


def setup_companion_dir(
    original_module_path: Path,
    ext_module_name: str | None = None,
) -> Path:
    """Create a companion _ext module directory structure.

    Sets up the extension module directory with standard Odoo subdirectories.
    The companion module is created alongside the original module directory.

    Args:
        original_module_path: Path to the original cloned module.
        ext_module_name: Custom name for the extension module. Defaults to
            ``{original_module_name}_ext`` (per Decision C).

    Returns:
        Path to the created companion directory.
    """
    name = ext_module_name or f"{original_module_path.name}_ext"
    ext_dir = original_module_path.parent / name

    ext_dir.mkdir(parents=True, exist_ok=True)

    # Create standard Odoo subdirectories
    for subdir in ("models", "views", "security", "tests"):
        (ext_dir / subdir).mkdir(exist_ok=True)

    return ext_dir
