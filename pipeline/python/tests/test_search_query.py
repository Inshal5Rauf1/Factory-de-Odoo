"""Tests for search query: search_modules, SearchResult, result formatting, GitHub fallback."""

from __future__ import annotations

import dataclasses
import json
from unittest.mock import MagicMock, patch

import pytest

from amil_utils.search.query import (
    SearchResult,
    format_results_json,
    format_results_text,
    search_modules,
)


# ---------------------------------------------------------------------------
# SearchResult frozen dataclass
# ---------------------------------------------------------------------------


class TestSearchResult:
    """SearchResult has all required fields and is frozen."""

    def test_search_result_has_all_fields(self) -> None:
        result = SearchResult(
            module_id="oca/sale-workflow/sale_order_type",
            module_name="sale_order_type",
            repo_name="sale-workflow",
            org="OCA",
            summary="Manage sale order types",
            category="Sales",
            depends=("sale", "account"),
            url="https://github.com/OCA/sale-workflow",
            relevance_score=0.85,
            document_text="Sale Order Type | Manage sale order types | Sales",
        )
        assert result.module_id == "oca/sale-workflow/sale_order_type"
        assert result.module_name == "sale_order_type"
        assert result.repo_name == "sale-workflow"
        assert result.org == "OCA"
        assert result.summary == "Manage sale order types"
        assert result.category == "Sales"
        assert result.depends == ("sale", "account")
        assert result.url == "https://github.com/OCA/sale-workflow"
        assert result.relevance_score == 0.85
        assert result.document_text == "Sale Order Type | Manage sale order types | Sales"

    def test_search_result_is_frozen(self) -> None:
        result = SearchResult(
            module_id="id",
            module_name="m",
            repo_name="r",
            org="OCA",
            summary="s",
            category="c",
            depends=(),
            url="u",
            relevance_score=0.5,
            document_text="d",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.module_name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# search_modules — sorted results
# ---------------------------------------------------------------------------


class TestSearchModulesSorted:
    """search_modules returns tuple of SearchResult sorted by relevance_score descending."""

    @patch("amil_utils.search.query.chromadb")
    def test_returns_sorted_by_relevance_descending(self, mock_chromadb: MagicMock) -> None:
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["oca/sale-workflow/mod_a", "oca/sale-workflow/mod_b", "oca/sale-workflow/mod_c"]],
            "documents": [["doc A", "doc B", "doc C"]],
            "metadatas": [[
                {"module_name": "mod_a", "oca_repo": "sale-workflow", "org": "OCA", "summary": "A", "category": "Sales", "depends": "sale", "url": "https://github.com/OCA/sale-workflow", "stars": 10, "last_pushed": "2026-01-01"},
                {"module_name": "mod_b", "oca_repo": "sale-workflow", "org": "OCA", "summary": "B", "category": "Sales", "depends": "sale", "url": "https://github.com/OCA/sale-workflow", "stars": 20, "last_pushed": "2026-01-02"},
                {"module_name": "mod_c", "oca_repo": "sale-workflow", "org": "OCA", "summary": "C", "category": "Sales", "depends": "sale", "url": "https://github.com/OCA/sale-workflow", "stars": 30, "last_pushed": "2026-01-03"},
            ]],
            "distances": [[0.4, 0.1, 0.6]],  # lower distance = higher similarity
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        results = search_modules("sale order", db_path="/tmp/test_db")
        assert isinstance(results, tuple)
        assert len(results) == 3
        # mod_b has lowest distance (0.1) = highest score, mod_c has highest distance (0.6) = lowest score
        assert results[0].module_name == "mod_b"
        assert results[1].module_name == "mod_a"
        assert results[2].module_name == "mod_c"
        # Scores should be descending
        assert results[0].relevance_score >= results[1].relevance_score >= results[2].relevance_score


# ---------------------------------------------------------------------------
# search_modules — n_results limit
# ---------------------------------------------------------------------------


class TestSearchModulesLimit:
    """search_modules returns at most n_results items (default 5)."""

    @patch("amil_utils.search.query.chromadb")
    def test_default_limit_is_5(self, mock_chromadb: MagicMock) -> None:
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1", "id2", "id3", "id4", "id5"]],
            "documents": [["d1", "d2", "d3", "d4", "d5"]],
            "metadatas": [[
                {"module_name": f"mod_{i}", "oca_repo": "r", "org": "OCA", "summary": "s", "category": "c", "depends": "", "url": "u", "stars": 0, "last_pushed": ""}
                for i in range(5)
            ]],
            "distances": [[0.1, 0.2, 0.3, 0.4, 0.5]],
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        results = search_modules("test query", db_path="/tmp/test_db")
        # Verify ChromaDB was queried with n_results=5
        mock_collection.query.assert_called_once_with(
            query_texts=["test query"],
            n_results=5,
            include=["documents", "metadatas", "distances"],
        )
        assert len(results) <= 5


# ---------------------------------------------------------------------------
# search_modules — cosine distance to similarity conversion
# ---------------------------------------------------------------------------


class TestCosineConversion:
    """Cosine distance converted correctly to similarity: similarity = 1.0 - (distance / 2.0)."""

    @patch("amil_utils.search.query.chromadb")
    def test_cosine_distance_to_similarity(self, mock_chromadb: MagicMock) -> None:
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["doc1"]],
            "metadatas": [[
                {"module_name": "mod1", "oca_repo": "r", "org": "OCA", "summary": "s", "category": "c", "depends": "", "url": "u", "stars": 0, "last_pushed": ""},
            ]],
            "distances": [[0.4]],  # similarity = 1.0 - (0.4 / 2.0) = 0.8
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        results = search_modules("test", db_path="/tmp/test_db")
        assert len(results) == 1
        assert results[0].relevance_score == pytest.approx(0.8, abs=0.01)

    @patch("amil_utils.search.query.chromadb")
    def test_similarity_range_0_to_1(self, mock_chromadb: MagicMock) -> None:
        """Distance 0.0 -> score 1.0, distance 2.0 -> score 0.0."""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["doc1", "doc2"]],
            "metadatas": [[
                {"module_name": "perfect", "oca_repo": "r", "org": "OCA", "summary": "s", "category": "c", "depends": "", "url": "u", "stars": 0, "last_pushed": ""},
                {"module_name": "worst", "oca_repo": "r", "org": "OCA", "summary": "s", "category": "c", "depends": "", "url": "u", "stars": 0, "last_pushed": ""},
            ]],
            "distances": [[0.0, 2.0]],
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        results = search_modules("test", db_path="/tmp/test_db")
        assert results[0].relevance_score == pytest.approx(1.0, abs=0.01)
        assert results[1].relevance_score == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# search_modules — error when index does not exist
# ---------------------------------------------------------------------------


class TestSearchModulesIndexError:
    """search_modules raises clear error when index does not exist."""

    @patch("amil_utils.search.query.chromadb")
    def test_raises_error_when_collection_not_found(self, mock_chromadb: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = ValueError("Collection odoo_modules does not exist")
        mock_chromadb.PersistentClient.return_value = mock_client

        with pytest.raises((ValueError, SystemExit)):
            search_modules("test query", db_path="/tmp/test_db")


# ---------------------------------------------------------------------------
# search_modules — empty query
# ---------------------------------------------------------------------------


class TestSearchModulesEmptyQuery:
    """Empty query string returns empty tuple or raises ValueError."""

    def test_empty_query_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="[Qq]uery"):
            search_modules("", db_path="/tmp/test_db")

    def test_whitespace_only_query_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="[Qq]uery"):
            search_modules("   ", db_path="/tmp/test_db")


# ---------------------------------------------------------------------------
# search_modules — JSON output
# ---------------------------------------------------------------------------


class TestSearchModulesJson:
    """format_results_json returns valid JSON with all SearchResult fields."""

    def test_json_contains_all_fields(self) -> None:
        results = (
            SearchResult(
                module_id="oca/sale-workflow/sale_order_type",
                module_name="sale_order_type",
                repo_name="sale-workflow",
                org="OCA",
                summary="Manage sale order types",
                category="Sales",
                depends=("sale",),
                url="https://github.com/OCA/sale-workflow",
                relevance_score=0.85,
                document_text="doc text",
            ),
        )
        json_str = format_results_json(results)
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        item = parsed[0]
        assert item["module_id"] == "oca/sale-workflow/sale_order_type"
        assert item["module_name"] == "sale_order_type"
        assert item["repo_name"] == "sale-workflow"
        assert item["org"] == "OCA"
        assert item["summary"] == "Manage sale order types"
        assert item["category"] == "Sales"
        assert item["depends"] == ["sale"]
        assert item["url"] == "https://github.com/OCA/sale-workflow"
        assert item["relevance_score"] == 0.85
        assert item["document_text"] == "doc text"


# ---------------------------------------------------------------------------
# search_modules — GitHub fallback
# ---------------------------------------------------------------------------


class TestGitHubFallback:
    """search_modules with github_fallback=True calls `gh search repos` when OCA results empty."""

    @patch("amil_utils.search.query.subprocess")
    @patch("amil_utils.search.query.chromadb")
    def test_github_fallback_when_oca_empty(self, mock_chromadb: MagicMock, mock_subprocess: MagicMock) -> None:
        # OCA returns empty results
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        # GitHub fallback returns results
        gh_output = json.dumps([
            {
                "name": "odoo-inventory-tracker",
                "description": "Odoo module for inventory tracking",
                "url": "https://github.com/user/odoo-inventory-tracker",
                "stargazerCount": 42,
            },
            {
                "name": "odoo-stock-ext",
                "description": "Stock extension for Odoo",
                "url": "https://github.com/user/odoo-stock-ext",
                "stargazerCount": 15,
            },
        ])
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout=gh_output,
        )

        results = search_modules("inventory tracking", db_path="/tmp/test_db", github_fallback=True)
        assert len(results) == 2
        # Verify gh search repos was called
        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args
        assert "gh" in call_args[0][0]
        assert "search" in call_args[0][0]
        assert "repos" in call_args[0][0]

    @patch("amil_utils.search.query.subprocess")
    @patch("amil_utils.search.query.chromadb")
    def test_github_fallback_results_have_org_github(self, mock_chromadb: MagicMock, mock_subprocess: MagicMock) -> None:
        # OCA returns empty results
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        # GitHub fallback returns one result
        gh_output = json.dumps([
            {
                "name": "odoo-hr-module",
                "description": "HR module for Odoo 17",
                "url": "https://github.com/someone/odoo-hr-module",
                "stargazerCount": 10,
            },
        ])
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout=gh_output,
        )

        results = search_modules("hr management", db_path="/tmp/test_db", github_fallback=True)
        assert len(results) == 1
        assert results[0].org == "GitHub"
        assert results[0].relevance_score == 0.5
        assert results[0].repo_name == "odoo-hr-module"
        assert results[0].url == "https://github.com/someone/odoo-hr-module"
        assert results[0].summary == "HR module for Odoo 17"

    @patch("amil_utils.search.query.chromadb")
    def test_no_github_fallback_when_oca_has_results(self, mock_chromadb: MagicMock) -> None:
        """When OCA returns results, GitHub fallback is NOT called even if flag is set."""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["doc1"]],
            "metadatas": [[
                {"module_name": "mod1", "oca_repo": "r", "org": "OCA", "summary": "s", "category": "c", "depends": "", "url": "u", "stars": 0, "last_pushed": ""},
            ]],
            "distances": [[0.3]],
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        results = search_modules("test", db_path="/tmp/test_db", github_fallback=True)
        assert len(results) == 1
        assert results[0].org == "OCA"


# ---------------------------------------------------------------------------
# format_results_text
# ---------------------------------------------------------------------------


class TestFormatResultsText:
    """format_results_text produces human-readable output."""

    def test_includes_score_and_badge(self) -> None:
        results = (
            SearchResult(
                module_id="oca/sale-workflow/sale_order_type",
                module_name="sale_order_type",
                repo_name="sale-workflow",
                org="OCA",
                summary="Manage sale order types",
                category="Sales",
                depends=("sale",),
                url="https://github.com/OCA/sale-workflow",
                relevance_score=0.85,
                document_text="doc",
            ),
            SearchResult(
                module_id="github/user/some_repo",
                module_name="some_module",
                repo_name="some_repo",
                org="GitHub",
                summary="GitHub module",
                category="Technical",
                depends=(),
                url="https://github.com/user/some_repo",
                relevance_score=0.5,
                document_text="doc",
            ),
        )
        text = format_results_text(results)
        assert "85%" in text
        assert "OCA" in text
        assert "sale_order_type" in text
        assert "GitHub" in text
        assert "50%" in text
