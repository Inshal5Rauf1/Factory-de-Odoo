"""Tests for Docker compose path resolution via importlib.resources."""

from __future__ import annotations

import ast
import os
from pathlib import Path
from unittest.mock import patch

from amil_utils.validation.docker_runner import get_compose_file


class TestGetComposeFileDefault:
    """get_compose_file returns a valid path using importlib.resources."""

    def test_returns_path_object(self) -> None:
        """get_compose_file returns a Path instance."""
        result = get_compose_file()
        assert isinstance(result, Path)

    def test_path_ends_with_docker_compose_yml(self) -> None:
        """Returned path ends with docker-compose.yml."""
        result = get_compose_file()
        assert result.name == "docker-compose.yml"

    def test_path_exists(self) -> None:
        """Returned path actually exists on disk."""
        result = get_compose_file()
        assert result.exists(), f"Compose file not found at {result}"


class TestGetComposeFileEnvOverride:
    """AMIL_COMPOSE_FILE env var overrides default path."""

    def test_env_var_overrides_default(self, tmp_path: Path) -> None:
        """When AMIL_COMPOSE_FILE is set, get_compose_file returns that path."""
        custom_compose = tmp_path / "custom-compose.yml"
        custom_compose.write_text("version: '3'\n", encoding="utf-8")

        with patch.dict(os.environ, {"AMIL_COMPOSE_FILE": str(custom_compose)}):
            result = get_compose_file()

        assert result == custom_compose

    def test_env_var_returns_exact_path(self, tmp_path: Path) -> None:
        """Env var path is returned as-is (no modification)."""
        custom_path = tmp_path / "my-compose.yml"
        custom_path.write_text("version: '3'\n", encoding="utf-8")

        with patch.dict(os.environ, {"AMIL_COMPOSE_FILE": str(custom_path)}):
            result = get_compose_file()

        assert str(result) == str(custom_path)


class TestGetComposeFileNoParentTraversal:
    """get_compose_file must NOT use Path(__file__).parent pattern."""

    def test_no_parent_traversal_in_source(self) -> None:
        """Source code of get_compose_file does not use .parent.parent traversal."""
        source_path = (
            Path(__file__).parent.parent
            / "src"
            / "amil_utils"
            / "validation"
            / "docker_runner.py"
        )
        source = source_path.read_text(encoding="utf-8")

        # Check that no .parent.parent chain exists in the file
        assert ".parent.parent" not in source, (
            "docker_runner.py still uses .parent.parent traversal"
        )

    def test_uses_importlib_resources(self) -> None:
        """Source code imports and uses importlib.resources."""
        source_path = (
            Path(__file__).parent.parent
            / "src"
            / "amil_utils"
            / "validation"
            / "docker_runner.py"
        )
        source = source_path.read_text(encoding="utf-8")

        assert "importlib.resources" in source, (
            "docker_runner.py should use importlib.resources"
        )
