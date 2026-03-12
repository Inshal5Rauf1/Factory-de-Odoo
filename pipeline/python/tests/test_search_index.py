"""Tests for search index: build_oca_index, get_index_status, types, manifest parsing."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from amil_utils.search.types import IndexEntry, IndexStatus
from amil_utils.search.index import (
    DEFAULT_DB_PATH,
    _build_document_text,
    _check_rate_limit,
    _parse_manifest_safe,
    _retry_on_rate_limit,
    build_oca_index,
    get_github_token,
    get_index_status,
)


# ---------------------------------------------------------------------------
# IndexEntry frozen dataclass
# ---------------------------------------------------------------------------

class TestIndexEntry:
    """IndexEntry has all required metadata fields and is frozen."""

    def test_index_entry_has_all_fields(self) -> None:
        entry = IndexEntry(
            module_name="sale_order_type",
            display_name="Sale Order Type",
            summary="Manage sale order types",
            description="Allows to define types of sale orders.",
            depends=("sale", "account"),
            category="Sales",
            oca_repo="sale-workflow",
            github_url="https://github.com/OCA/sale-workflow",
            stars=120,
            last_pushed="2026-01-15T10:00:00Z",
        )
        assert entry.module_name == "sale_order_type"
        assert entry.display_name == "Sale Order Type"
        assert entry.summary == "Manage sale order types"
        assert entry.description == "Allows to define types of sale orders."
        assert entry.depends == ("sale", "account")
        assert entry.category == "Sales"
        assert entry.oca_repo == "sale-workflow"
        assert entry.github_url == "https://github.com/OCA/sale-workflow"
        assert entry.stars == 120
        assert entry.last_pushed == "2026-01-15T10:00:00Z"

    def test_index_entry_is_frozen(self) -> None:
        entry = IndexEntry(
            module_name="m",
            display_name="M",
            summary="s",
            description="d",
            depends=(),
            category="c",
            oca_repo="r",
            github_url="u",
            stars=0,
            last_pushed="",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.module_name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _parse_manifest_safe
# ---------------------------------------------------------------------------

class TestParseManifestSafe:
    """Manifest parsing uses ast.literal_eval, never eval()."""

    def test_valid_manifest(self) -> None:
        content = """{
    'name': 'Sale Order Type',
    'version': '17.0.1.0.0',
    'depends': ['sale', 'account'],
    'installable': True,
    'category': 'Sales',
    'summary': 'Manage sale order types',
}"""
        result = _parse_manifest_safe(content)
        assert isinstance(result, dict)
        assert result["name"] == "Sale Order Type"
        assert result["depends"] == ["sale", "account"]
        assert result["installable"] is True

    def test_invalid_manifest_returns_none(self) -> None:
        result = _parse_manifest_safe("this is not valid python")
        assert result is None

    def test_malicious_manifest_returns_none(self) -> None:
        # This would be dangerous with eval() but safe with ast.literal_eval
        result = _parse_manifest_safe("__import__('os').system('rm -rf /')")
        assert result is None

    def test_non_dict_returns_none(self) -> None:
        result = _parse_manifest_safe("[1, 2, 3]")
        assert result is None


# ---------------------------------------------------------------------------
# _build_document_text
# ---------------------------------------------------------------------------

class TestBuildDocumentText:
    """Document text concatenates display_name, summary, description, category, depends."""

    def test_concatenates_fields(self) -> None:
        manifest = {
            "name": "Sale Order Type",
            "summary": "Manage sale order types",
            "description": "Allows to define types of sale orders for better categorization.",
            "category": "Sales",
            "depends": ["sale", "account"],
        }
        result = _build_document_text(manifest, "sale_order_type")
        assert "Sale Order Type" in result
        assert "Manage sale order types" in result
        assert "Allows to define types" in result
        assert "Sales" in result
        assert "sale" in result
        assert "account" in result

    def test_handles_missing_fields(self) -> None:
        manifest = {"name": "Minimal"}
        result = _build_document_text(manifest, "minimal_module")
        assert "Minimal" in result


# ---------------------------------------------------------------------------
# get_index_status
# ---------------------------------------------------------------------------

class TestGetIndexStatus:
    """get_index_status returns IndexStatus reflecting current index state."""

    @patch("amil_utils.search.index.chromadb")
    def test_no_index_returns_zero_count(self, mock_chromadb: MagicMock, tmp_path) -> None:
        db_path = str(tmp_path / "nonexistent_chromadb")
        status = get_index_status(db_path)
        assert isinstance(status, IndexStatus)
        assert status.module_count == 0
        assert status.exists is False

    @patch("amil_utils.search.index.chromadb")
    def test_existing_index_returns_correct_count(self, mock_chromadb: MagicMock, tmp_path) -> None:
        db_path = str(tmp_path / "chromadb_test")
        # Create directory so exists check passes
        (tmp_path / "chromadb_test").mkdir()

        mock_collection = MagicMock()
        mock_collection.count.return_value = 42
        mock_collection.metadata = {"last_built": "2026-01-15T10:00:00Z"}
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        status = get_index_status(db_path)
        assert status.exists is True
        assert status.module_count == 42
        assert status.last_built == "2026-01-15T10:00:00Z"


# ---------------------------------------------------------------------------
# get_github_token
# ---------------------------------------------------------------------------

class TestGetGithubToken:
    """get_github_token checks env var, then gh CLI."""

    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token-123"})
    def test_returns_env_var_token(self) -> None:
        token = get_github_token()
        assert token == "test-token-123"

    @patch.dict("os.environ", {}, clear=True)
    @patch("amil_utils.search.index.subprocess.run")
    def test_returns_gh_cli_token(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="gh-token-456\n")
        # Clear GITHUB_TOKEN from env to avoid interference
        import os
        os.environ.pop("GITHUB_TOKEN", None)
        token = get_github_token()
        assert token == "gh-token-456"

    @patch.dict("os.environ", {}, clear=True)
    @patch("amil_utils.search.index.subprocess.run")
    def test_returns_none_when_no_token(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        import os
        os.environ.pop("GITHUB_TOKEN", None)
        token = get_github_token()
        assert token is None


# ---------------------------------------------------------------------------
# build_oca_index
# ---------------------------------------------------------------------------

def _make_mock_repo(
    name: str,
    has_17_branch: bool = True,
    modules: dict | None = None,
    stars: int = 10,
    pushed_at: str = "2026-01-01T00:00:00Z",
) -> MagicMock:
    """Create a mock PyGithub Repository object."""
    repo = MagicMock()
    repo.name = name
    repo.full_name = f"OCA/{name}"
    repo.html_url = f"https://github.com/OCA/{name}"
    repo.stargazers_count = stars
    repo.pushed_at = pushed_at

    if has_17_branch:
        branch = MagicMock()
        branch.name = "17.0"
        repo.get_branch.return_value = branch
    else:
        pytest.importorskip("github", reason="PyGithub not installed")
        from github import GithubException

        repo.get_branch.side_effect = GithubException(404, {"message": "Branch not found"}, None)

    if modules:
        contents = []
        for mod_name, manifest_content in modules.items():
            mod_dir = MagicMock()
            mod_dir.name = mod_name
            mod_dir.type = "dir"
            mod_dir.path = mod_name

            manifest_file = MagicMock()
            manifest_file.name = "__manifest__.py"
            manifest_file.decoded_content = manifest_content.encode()

            repo.get_contents.side_effect = _make_get_contents_side_effect(
                {name: contents, mod_name: [manifest_file]},
                contents,
            )
            contents.append(mod_dir)
    else:
        repo.get_contents.return_value = []

    return repo


def _make_get_contents_side_effect(
    mapping: dict,
    root_contents: list,
) -> callable:
    """Build a side_effect function for repo.get_contents()."""

    def _side_effect(path: str, ref: str = "17.0") -> list | MagicMock:
        if path == "":
            return root_contents
        # Check for __manifest__.py in module dir
        mod_name = path.split("/")[0] if "/" not in path else path.rsplit("/", 1)[0]
        if path.endswith("__manifest__.py"):
            for key, val in mapping.items():
                if key == mod_name or path.startswith(key):
                    if isinstance(val, list) and val and hasattr(val[0], "decoded_content"):
                        return val[0]
            raise Exception(f"Not found: {path}")
        # Return dir contents
        return mapping.get(path, [])

    return _side_effect


class TestBuildOcaIndex:
    """build_oca_index crawls OCA repos via mocked PyGithub and upserts to mocked ChromaDB."""

    @patch("amil_utils.search.index.chromadb")
    @patch("amil_utils.search.index.Github")
    def test_indexes_correct_module_count(self, mock_github_cls: MagicMock, mock_chromadb: MagicMock) -> None:
        manifest = """{
    'name': 'Sale Order Type',
    'version': '17.0.1.0.0',
    'depends': ['sale'],
    'installable': True,
    'summary': 'Sale types',
    'category': 'Sales',
}"""
        repo = _make_mock_repo("sale-workflow", modules={"sale_order_type": manifest})

        mock_org = MagicMock()
        mock_org.get_repos.return_value = [repo]
        mock_gh = MagicMock()
        mock_gh.get_organization.return_value = mock_org
        mock_github_cls.return_value = mock_gh

        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        count = build_oca_index("fake-token", "/tmp/test_db")
        assert count == 1
        mock_collection.upsert.assert_called_once()

    @patch("amil_utils.search.index.chromadb")
    @patch("amil_utils.search.index.Github")
    def test_skips_repos_without_17_branch(self, mock_github_cls: MagicMock, mock_chromadb: MagicMock) -> None:
        repo_no_branch = _make_mock_repo("old-repo", has_17_branch=False)
        repo_with_branch = _make_mock_repo("sale-workflow", modules={})

        mock_org = MagicMock()
        mock_org.get_repos.return_value = [repo_no_branch, repo_with_branch]
        mock_gh = MagicMock()
        mock_gh.get_organization.return_value = mock_org
        mock_github_cls.return_value = mock_gh

        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        count = build_oca_index("fake-token", "/tmp/test_db")
        assert count == 0  # no modules indexed since second repo has no modules

    @patch("amil_utils.search.index.chromadb")
    @patch("amil_utils.search.index.Github")
    def test_skips_non_installable_modules(self, mock_github_cls: MagicMock, mock_chromadb: MagicMock) -> None:
        manifest = """{
    'name': 'Disabled Module',
    'version': '17.0.1.0.0',
    'depends': ['base'],
    'installable': False,
    'summary': 'Not installable',
    'category': 'Technical',
}"""
        repo = _make_mock_repo("test-repo", modules={"disabled_mod": manifest})

        mock_org = MagicMock()
        mock_org.get_repos.return_value = [repo]
        mock_gh = MagicMock()
        mock_gh.get_organization.return_value = mock_org
        mock_github_cls.return_value = mock_gh

        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        count = build_oca_index("fake-token", "/tmp/test_db")
        assert count == 0
        mock_collection.upsert.assert_not_called()

    def test_raises_system_exit_when_no_token(self) -> None:
        with pytest.raises(SystemExit, match="GitHub token required"):
            build_oca_index("", "/tmp/test_db")


# ---------------------------------------------------------------------------
# _check_rate_limit tests
# ---------------------------------------------------------------------------


class TestCheckRateLimit:
    """_check_rate_limit sleeps when rate.remaining is low."""

    @patch("amil_utils.search.index.time")
    def test_sleeps_when_remaining_low(self, mock_time: MagicMock) -> None:
        """_check_rate_limit sleeps when rate.remaining < min_remaining."""
        mock_time.time.return_value = 1000.0

        mock_rate = MagicMock()
        mock_rate.remaining = 5
        mock_rate.limit = 5000
        # Reset is 60 seconds in the future
        reset_dt = datetime.fromtimestamp(1060.0, tz=timezone.utc)
        mock_rate.reset = reset_dt

        mock_rate_limit = MagicMock()
        mock_rate_limit.core = mock_rate

        mock_gh = MagicMock()
        mock_gh.get_rate_limit.return_value = mock_rate_limit

        _check_rate_limit(mock_gh, min_remaining=10)

        mock_time.sleep.assert_called_once()
        sleep_seconds = mock_time.sleep.call_args[0][0]
        assert sleep_seconds > 0

    @patch("amil_utils.search.index.time")
    def test_does_nothing_when_remaining_sufficient(self, mock_time: MagicMock) -> None:
        """_check_rate_limit does nothing when rate.remaining >= min_remaining."""
        mock_rate = MagicMock()
        mock_rate.remaining = 100
        mock_rate.limit = 5000

        mock_rate_limit = MagicMock()
        mock_rate_limit.core = mock_rate

        mock_gh = MagicMock()
        mock_gh.get_rate_limit.return_value = mock_rate_limit

        _check_rate_limit(mock_gh, min_remaining=10)

        mock_time.sleep.assert_not_called()


# ---------------------------------------------------------------------------
# _retry_on_rate_limit tests
# ---------------------------------------------------------------------------


class TestRetryOnRateLimit:
    """_retry_on_rate_limit retries with exponential backoff on RateLimitExceededException."""

    @patch("amil_utils.search.index.time")
    def test_retries_with_exponential_backoff(self, mock_time: MagicMock) -> None:
        """Retries on RateLimitExceededException with 1s, 2s delays."""
        pytest.importorskip("github", reason="PyGithub not installed")
        from github import RateLimitExceededException

        mock_func = MagicMock()
        mock_func.side_effect = [
            RateLimitExceededException(403, {"message": "rate limit"}, None),
            RateLimitExceededException(403, {"message": "rate limit"}, None),
            "success_result",
        ]

        result = _retry_on_rate_limit(mock_func, "arg1", max_retries=3)

        assert result == "success_result"
        assert mock_func.call_count == 3
        # Backoff: 2^0=1, 2^1=2
        sleep_calls = mock_time.sleep.call_args_list
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == call(1)
        assert sleep_calls[1] == call(2)

    @patch("amil_utils.search.index.time")
    def test_reraises_after_max_retries(self, mock_time: MagicMock) -> None:
        """Re-raises RateLimitExceededException after max_retries exhausted."""
        pytest.importorskip("github", reason="PyGithub not installed")
        from github import RateLimitExceededException

        exc = RateLimitExceededException(403, {"message": "rate limit"}, None)
        mock_func = MagicMock(side_effect=exc)

        with pytest.raises(RateLimitExceededException):
            _retry_on_rate_limit(mock_func, max_retries=3)

        assert mock_func.call_count == 4  # initial + 3 retries

    @patch("amil_utils.search.index.time")
    def test_returns_result_on_success(self, mock_time: MagicMock) -> None:
        """Returns result immediately on success (no exception)."""
        mock_func = MagicMock(return_value="immediate_result")

        result = _retry_on_rate_limit(mock_func, "arg1", "arg2", max_retries=3)

        assert result == "immediate_result"
        mock_func.assert_called_once_with("arg1", "arg2")
        mock_time.sleep.assert_not_called()


# ---------------------------------------------------------------------------
# build_oca_index rate limit integration tests
# ---------------------------------------------------------------------------


class TestBuildOcaIndexRateLimit:
    """build_oca_index calls _check_rate_limit periodically during crawl."""

    @patch("amil_utils.search.index._check_rate_limit")
    @patch("amil_utils.search.index.chromadb")
    @patch("amil_utils.search.index.Github")
    def test_calls_check_rate_limit_every_10_repos(
        self,
        mock_github_cls: MagicMock,
        mock_chromadb: MagicMock,
        mock_check_rl: MagicMock,
    ) -> None:
        """build_oca_index calls _check_rate_limit at least once for 15+ repos."""
        pytest.importorskip("github", reason="PyGithub not installed")
        from github import GithubException

        # Create 15 repos with no 17.0 branch (simplest mock)
        repos = []
        for i in range(15):
            repo = MagicMock()
            repo.name = f"repo-{i}"
            repo.get_branch.side_effect = GithubException(404, {"message": "Not found"}, None)
            repos.append(repo)

        mock_org = MagicMock()
        mock_org.get_repos.return_value = repos
        mock_gh = MagicMock()
        mock_gh.get_organization.return_value = mock_org
        mock_github_cls.return_value = mock_gh

        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        build_oca_index("fake-token", "/tmp/test_db")

        # _check_rate_limit should have been called at idx=10 (at least once)
        assert mock_check_rl.call_count >= 1

    @patch("amil_utils.search.index._check_rate_limit")
    @patch("amil_utils.search.index.chromadb")
    @patch("amil_utils.search.index.Github")
    def test_retries_get_branch_on_rate_limit(
        self,
        mock_github_cls: MagicMock,
        mock_chromadb: MagicMock,
        mock_check_rl: MagicMock,
    ) -> None:
        """build_oca_index catches RateLimitExceededException on get_branch and retries."""
        pytest.importorskip("github", reason="PyGithub not installed")
        from github import RateLimitExceededException

        repo = MagicMock()
        repo.name = "test-repo"
        repo.html_url = "https://github.com/OCA/test-repo"
        repo.stargazers_count = 5
        repo.pushed_at = "2026-01-01"
        # First call raises rate limit, second succeeds
        branch = MagicMock()
        branch.name = "17.0"
        repo.get_branch.side_effect = [
            RateLimitExceededException(403, {"message": "rate limit"}, None),
            branch,
        ]
        repo.get_contents.return_value = []

        mock_org = MagicMock()
        mock_org.get_repos.return_value = [repo]
        mock_gh = MagicMock()
        mock_gh.get_organization.return_value = mock_org
        mock_github_cls.return_value = mock_gh

        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        build_oca_index("fake-token", "/tmp/test_db")

        # get_branch should have been called twice (original + retry)
        assert repo.get_branch.call_count == 2
