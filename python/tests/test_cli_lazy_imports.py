"""Tests for CLI lazy imports — heavy libraries must not load at import time."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


# Heavy modules that should NOT be loaded when cli.py is imported
HEAVY_MODULE_PREFIXES = [
    "chromadb",
    "github",
    "git",
    "docker",
]

HEAVY_SUBMODULES = [
    "amil_utils.auto_fix",
    "amil_utils.search",
    "amil_utils.validation",
    "amil_utils.renderer",
    "amil_utils.i18n_extractor",
    "amil_utils.edition",
    "amil_utils.kb_validator",
    "amil_utils.verifier",
    "amil_utils.registry",
    "amil_utils.mermaid",
]


class TestCLILazyImportsInProcess:
    """Verify that importing cli does not pull in heavy deps (in-process check)."""

    def test_no_heavy_third_party_modules_loaded(self) -> None:
        """After importing cli, sys.modules must not contain chromadb, github, git, docker."""
        # We need a subprocess for a clean check since other tests may have
        # already imported these modules in this process.
        # This test checks the module-level import list statically.
        import ast

        cli_path = (
            Path(__file__).parent.parent / "src" / "amil_utils" / "cli.py"
        )
        source = cli_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        top_level_imports: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_level_imports.append(node.module)

        # These must NOT appear at module level
        forbidden_prefixes = [
            "amil_utils.auto_fix",
            "amil_utils.i18n_extractor",
            "amil_utils.kb_validator",
            "amil_utils.search",
            "amil_utils.edition",
            "amil_utils.renderer",
            "amil_utils.verifier",
            "amil_utils.validation",
            "amil_utils.registry",
            "amil_utils.mermaid",
            "chromadb",
            "github",
            "docker",
        ]

        violations = []
        for imp in top_level_imports:
            for prefix in forbidden_prefixes:
                if imp.startswith(prefix):
                    violations.append(imp)

        assert not violations, (
            f"Module-level imports contain heavy dependencies: {violations}"
        )

    def test_allowed_top_level_imports_only(self) -> None:
        """Only click, json, sys, pathlib, __future__, and amil_utils.__version__ at top level."""
        import ast

        cli_path = (
            Path(__file__).parent.parent / "src" / "amil_utils" / "cli.py"
        )
        source = cli_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        allowed = {
            "__future__",
            "json",
            "logging",
            "sys",
            "pathlib",
            "click",
            "amil_utils",
        }

        top_level_imports: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_level_imports.append(node.module)

        violations = []
        for imp in top_level_imports:
            root_module = imp.split(".")[0]
            if root_module not in allowed:
                violations.append(imp)

        assert not violations, (
            f"Unexpected top-level imports: {violations}. "
            f"Only {allowed} should be at module level."
        )


class TestCLILazyImportsSubprocess:
    """Verify lazy imports in a clean subprocess (no prior imports)."""

    def test_clean_process_no_heavy_deps(self) -> None:
        """In a fresh Python process, importing cli.main must not load heavy deps."""
        code = (
            "from amil_utils.cli import main; "
            "import sys; "
            "heavy = [m for m in sys.modules "
            "if any(h in m for h in "
            "['chromadb','github','docker','gitpython']"
            ")]; "
            "assert not heavy, f'Heavy modules loaded: {heavy}'"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Subprocess failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_each_command_function_exists(self) -> None:
        """CLI module exposes the expected command group."""
        code = (
            "from amil_utils.cli import main; "
            "import click; "
            "assert isinstance(main, click.Group), 'main is not a click Group'; "
            "cmds = list(main.commands.keys()); "
            "expected = ['validate', 'render', 'build-index', 'search-modules', "
            "'extract-i18n', 'check-edition', 'validate-kb', 'render-module', "
            "'list-templates', 'index-status', 'extend-module', 'registry', 'mermaid']; "
            "missing = [c for c in expected if c not in cmds]; "
            "assert not missing, f'Missing commands: {missing}'"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Subprocess failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
