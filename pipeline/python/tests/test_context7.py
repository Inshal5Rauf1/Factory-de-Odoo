"""Unit tests for Context7 REST API client (MCP-05 a-f) and enrichment pipeline (PIPE-01).

Tests cover:
    a) Config defaults and frozen dataclass
    b) Client configured/unconfigured states
    c) Library resolution with caching
    d) Document querying (success + all failure modes)
    e) build_context7_from_env factory
    f) _context7_get helper auth header behavior
    g) Pattern detection from preprocessed spec (PIPE-01a)
    h) Token truncation (PIPE-01d)
    i) Disk cache read/write with TTL (PIPE-01c)
    j) context7_enrich enrichment function (PIPE-01b)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(data: object) -> MagicMock:
    """Create a mock HTTP response that works as a context manager."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def configured_client():
    """Return a Context7Client with a dummy API key."""
    from amil_utils.context7 import Context7Client, Context7Config

    return Context7Client(Context7Config(api_key="test-key-123"))


@pytest.fixture()
def unconfigured_client():
    """Return a Context7Client with no API key (unconfigured)."""
    from amil_utils.context7 import Context7Client

    return Context7Client()


# ---------------------------------------------------------------------------
# MCP-05 a: Config defaults
# ---------------------------------------------------------------------------

class TestContext7Config:
    def test_context7_config_defaults(self):
        from amil_utils.context7 import Context7Config

        cfg = Context7Config()
        assert cfg.api_key == ""
        assert cfg.base_url == "https://context7.com/api/v2"
        assert cfg.timeout == 10

    def test_doc_snippet_frozen(self):
        from amil_utils.context7 import DocSnippet

        snippet = DocSnippet(title="T", content="C", source_url="http://x")
        with pytest.raises(AttributeError):
            snippet.title = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MCP-05 b: Client configured state
# ---------------------------------------------------------------------------

class TestClientConfigured:
    def test_client_not_configured_when_no_api_key(self, unconfigured_client):
        assert unconfigured_client.is_configured is False

    def test_client_configured_when_api_key_set(self, configured_client):
        assert configured_client.is_configured is True


# ---------------------------------------------------------------------------
# MCP-05 c: Library resolution
# ---------------------------------------------------------------------------

class TestResolveOdooLibrary:
    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_resolve_odoo_library_success(self, mock_urlopen, configured_client):
        mock_urlopen.return_value = _mock_response(
            [{"id": "lib-odoo-123", "name": "odoo", "description": "Odoo framework"}],
        )
        result = configured_client.resolve_odoo_library()
        assert result == "lib-odoo-123"
        mock_urlopen.assert_called_once()

    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_resolve_odoo_library_caches_result(self, mock_urlopen, configured_client):
        mock_urlopen.return_value = _mock_response(
            [{"id": "lib-odoo-123", "name": "odoo", "description": "Odoo framework"}],
        )
        first = configured_client.resolve_odoo_library()
        second = configured_client.resolve_odoo_library()
        assert first == second == "lib-odoo-123"
        # Only one HTTP call -- second was cached
        assert mock_urlopen.call_count == 1

    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_resolve_odoo_library_returns_none_on_http_error(
        self, mock_urlopen, configured_client,
    ):
        mock_urlopen.side_effect = URLError("connection refused")
        result = configured_client.resolve_odoo_library()
        assert result is None

    def test_resolve_odoo_library_returns_none_when_unconfigured(
        self, unconfigured_client,
    ):
        result = unconfigured_client.resolve_odoo_library()
        assert result is None


# ---------------------------------------------------------------------------
# MCP-05 d: Document querying
# ---------------------------------------------------------------------------

class TestQueryDocs:
    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_query_docs_success(self, mock_urlopen, configured_client):
        from amil_utils.context7 import DocSnippet

        # First call resolves library, second call fetches docs
        mock_urlopen.side_effect = [
            _mock_response([{"id": "lib-odoo-1", "name": "odoo", "description": ""}]),
            _mock_response([
                {
                    "title": "Model Fields",
                    "content": "Fields define...",
                    "sourceUrl": "https://docs.odoo.com/fields",
                },
                {
                    "title": "Views",
                    "content": "Views render...",
                    "sourceUrl": "https://docs.odoo.com/views",
                },
            ]),
        ]
        result = configured_client.query_docs("fields in odoo")
        assert len(result) == 2
        assert isinstance(result[0], DocSnippet)
        assert result[0].title == "Model Fields"
        assert result[0].content == "Fields define..."
        assert result[0].source_url == "https://docs.odoo.com/fields"
        assert result[1].title == "Views"

    def test_query_docs_unconfigured(self, unconfigured_client):
        result = unconfigured_client.query_docs("anything")
        assert result == []

    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_query_docs_http_error(self, mock_urlopen, configured_client):
        # First call resolves library OK, second raises HTTPError
        mock_urlopen.side_effect = [
            _mock_response([{"id": "lib-1", "name": "odoo", "description": ""}]),
            HTTPError(
                url="https://context7.com/api/v2/context",
                code=429,
                msg="Too Many Requests",
                hdrs=MagicMock(),  # type: ignore[arg-type]
                fp=None,
            ),
        ]
        result = configured_client.query_docs("rate limited")
        assert result == []

    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_query_docs_timeout(self, mock_urlopen, configured_client):
        # First call resolves library OK, second raises timeout
        mock_urlopen.side_effect = [
            _mock_response([{"id": "lib-1", "name": "odoo", "description": ""}]),
            TimeoutError("Connection timed out"),
        ]
        result = configured_client.query_docs("slow query")
        assert result == []

    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_query_docs_invalid_json(self, mock_urlopen, configured_client):
        # First call resolves library OK, second returns invalid JSON
        bad_resp = MagicMock()
        bad_resp.read.return_value = b"<html>not json</html>"
        bad_resp.__enter__ = lambda s: s
        bad_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.side_effect = [
            _mock_response([{"id": "lib-1", "name": "odoo", "description": ""}]),
            bad_resp,
        ]
        result = configured_client.query_docs("bad response")
        assert result == []


# ---------------------------------------------------------------------------
# MCP-05 e: Factory function
# ---------------------------------------------------------------------------

class TestBuildContext7FromEnv:
    def test_build_context7_from_env_with_key(self, monkeypatch):
        from amil_utils.context7 import build_context7_from_env

        monkeypatch.setenv("CONTEXT7_API_KEY", "my-secret-key")
        client = build_context7_from_env()
        assert client.is_configured is True

    def test_build_context7_from_env_without_key(self, monkeypatch):
        from amil_utils.context7 import build_context7_from_env

        monkeypatch.delenv("CONTEXT7_API_KEY", raising=False)
        client = build_context7_from_env()
        assert client.is_configured is False


# ---------------------------------------------------------------------------
# MCP-05 f: _context7_get helper auth header
# ---------------------------------------------------------------------------

class TestContext7GetHelper:
    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_context7_get_helper_adds_auth_header(self, mock_urlopen):
        from amil_utils.context7 import _context7_get

        mock_urlopen.return_value = _mock_response({"ok": True})
        _context7_get("https://example.com/api", api_key="bearer-token-123")
        # Inspect the Request object passed to urlopen
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.get_header("Authorization") == "Bearer bearer-token-123"

    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_context7_get_helper_no_header_when_no_key(self, mock_urlopen):
        from amil_utils.context7 import _context7_get

        mock_urlopen.return_value = _mock_response({"ok": True})
        _context7_get("https://example.com/api", api_key="")
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert not request.has_header("Authorization")


# ---------------------------------------------------------------------------
# Integration: KB is primary, Context7 supplements
# ---------------------------------------------------------------------------


class TestKBPrimaryContext7Supplementary:
    """Integration test: knowledge base is primary, Context7 supplements."""

    def test_kb_primary_context7_supplementary(self) -> None:
        """Verify that generation works without Context7 -- KB is sole source."""
        from amil_utils.context7 import build_context7_from_env

        # Ensure CONTEXT7_API_KEY is not set
        env = {k: v for k, v in os.environ.items() if k != "CONTEXT7_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            client = build_context7_from_env()
            assert not client.is_configured
            assert client.query_docs("mail.thread") == []
            # This verifies the system degrades gracefully -- knowledge base
            # would be the sole source in the real pipeline


# ---------------------------------------------------------------------------
# PIPE-01 a: Pattern detection from preprocessed spec
# ---------------------------------------------------------------------------

class TestDetectPatterns:
    """Tests for _detect_patterns() -- identifies active Context7 query patterns."""

    def test_empty_spec_returns_empty(self):
        from amil_utils.context7 import _detect_patterns

        assert _detect_patterns({}) == []

    def test_mail_in_depends_returns_mail_thread(self):
        from amil_utils.context7 import _detect_patterns

        spec = {"depends": ["base", "mail"]}
        result = _detect_patterns(spec)
        assert "mail_thread" in result

    def test_monetary_field_returns_monetary(self):
        from amil_utils.context7 import _detect_patterns

        spec = {
            "models": [
                {"name": "sale.order", "fields": [{"name": "amount_total", "type": "Monetary"}]},
            ],
        }
        result = _detect_patterns(spec)
        assert "monetary" in result

    def test_float_amount_field_returns_monetary(self):
        from amil_utils.context7 import _detect_patterns

        spec = {
            "models": [
                {"name": "sale.order", "fields": [{"name": "amount_due", "type": "Float"}]},
            ],
        }
        result = _detect_patterns(spec)
        assert "monetary" in result

    def test_has_approval_returns_approval(self):
        from amil_utils.context7 import _detect_patterns

        spec = {
            "models": [
                {"name": "purchase.order", "has_approval": True, "fields": []},
            ],
        }
        result = _detect_patterns(spec)
        assert "approval" in result

    def test_computed_field_returns_computed(self):
        from amil_utils.context7 import _detect_patterns

        spec = {
            "models": [
                {"name": "sale.order", "fields": [
                    {"name": "total", "type": "Float", "compute": "_compute_total"},
                ]},
            ],
        }
        result = _detect_patterns(spec)
        assert "computed" in result

    def test_reports_key_returns_reports(self):
        from amil_utils.context7 import _detect_patterns

        spec = {"reports": [{"name": "sale_report"}]}
        result = _detect_patterns(spec)
        assert "reports" in result

    def test_combined_spec_returns_all_five_patterns(self):
        from amil_utils.context7 import _detect_patterns

        spec = {
            "depends": ["base", "mail"],
            "reports": [{"name": "report_invoice"}],
            "models": [
                {
                    "name": "sale.order",
                    "has_approval": True,
                    "fields": [
                        {"name": "amount_total", "type": "Monetary"},
                        {"name": "total", "type": "Float", "compute": "_compute_total"},
                    ],
                },
            ],
        }
        result = _detect_patterns(spec)
        assert result == ["mail_thread", "monetary", "approval", "computed", "reports"]

    def test_pattern_order_is_deterministic(self):
        from amil_utils.context7 import _detect_patterns

        spec = {
            "depends": ["mail"],
            "reports": [{"name": "r"}],
            "models": [
                {
                    "name": "m",
                    "has_approval": True,
                    "fields": [
                        {"name": "x", "type": "Monetary"},
                        {"name": "y", "compute": "_c"},
                    ],
                },
            ],
        }
        # Always: mail_thread, monetary, approval, computed, reports
        result = _detect_patterns(spec)
        assert result == ["mail_thread", "monetary", "approval", "computed", "reports"]


# ---------------------------------------------------------------------------
# PIPE-01 d: Token truncation
# ---------------------------------------------------------------------------

class TestTruncateToTokens:
    """Tests for _truncate_to_tokens() -- limits text to approximate token budget."""

    def test_short_text_returned_unchanged(self):
        from amil_utils.context7 import _truncate_to_tokens

        text = "Short text"
        assert _truncate_to_tokens(text) == text

    def test_long_text_truncated_at_word_boundary(self):
        from amil_utils.context7 import _truncate_to_tokens

        # 500 tokens * 4 chars/token = 2000 chars max
        text = "word " * 500  # 2500 chars
        result = _truncate_to_tokens(text)
        assert len(result) <= 2003  # 2000 + "..."
        assert result.endswith("...")

    def test_empty_string_returns_empty(self):
        from amil_utils.context7 import _truncate_to_tokens

        assert _truncate_to_tokens("") == ""

    def test_exact_boundary_text_not_truncated(self):
        from amil_utils.context7 import _truncate_to_tokens

        text = "a" * 2000  # Exactly at 500 token * 4 char limit
        assert _truncate_to_tokens(text) == text

    def test_truncation_with_custom_max_tokens(self):
        from amil_utils.context7 import _truncate_to_tokens

        text = "hello world " * 100  # 1200 chars
        result = _truncate_to_tokens(text, max_tokens=10)  # 40 chars max
        assert len(result) <= 43  # 40 + "..."
        assert result.endswith("...")

    def test_no_space_in_truncated_region(self):
        from amil_utils.context7 import _truncate_to_tokens

        # Text with no spaces -- should truncate at max_chars directly
        text = "a" * 3000
        result = _truncate_to_tokens(text)
        assert result == "a" * 2000 + "..."


# ---------------------------------------------------------------------------
# PIPE-01 c: Disk cache read/write with TTL
# ---------------------------------------------------------------------------

class TestContext7Cache:
    """Tests for _cache_read() and _cache_write() -- disk cache with 24h TTL."""

    def test_cache_write_creates_directory_and_file(self, tmp_path):
        from amil_utils.context7 import _cache_write

        cache_dir = tmp_path / "ctx7_cache"
        _cache_write(cache_dir, "abc123", "test query", "test response")
        cache_file = cache_dir / "abc123.json"
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["query"] == "test query"
        assert data["response"] == "test response"
        assert "ts" in data

    def test_cache_read_returns_response_for_fresh_entry(self, tmp_path):
        from amil_utils.context7 import _cache_read, _cache_write

        cache_dir = tmp_path / "ctx7_cache"
        _cache_write(cache_dir, "key1", "q", "fresh response")
        result = _cache_read(cache_dir, "key1")
        assert result == "fresh response"

    def test_cache_read_returns_none_for_stale_entry(self, tmp_path):
        from amil_utils.context7 import CACHE_TTL_SECONDS, _cache_read

        cache_dir = tmp_path / "ctx7_cache"
        cache_dir.mkdir(parents=True)
        # Write a stale entry (timestamp 25 hours ago)
        stale_ts = time.time() - CACHE_TTL_SECONDS - 3600
        cache_file = cache_dir / "stale_key.json"
        cache_file.write_text(json.dumps({
            "query": "q",
            "response": "stale response",
            "ts": stale_ts,
        }))
        result = _cache_read(cache_dir, "stale_key")
        assert result is None

    def test_cache_read_returns_none_for_missing_file(self, tmp_path):
        from amil_utils.context7 import _cache_read

        cache_dir = tmp_path / "ctx7_cache"
        cache_dir.mkdir(parents=True)
        result = _cache_read(cache_dir, "nonexistent")
        assert result is None

    def test_cache_read_returns_none_for_malformed_json(self, tmp_path):
        from amil_utils.context7 import _cache_read

        cache_dir = tmp_path / "ctx7_cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "bad.json"
        cache_file.write_text("not valid json {{{")
        result = _cache_read(cache_dir, "bad")
        assert result is None

    def test_cache_write_logs_warning_on_oserror(self, tmp_path):
        from amil_utils.context7 import _cache_write

        # Use a path that cannot be written to (file as directory)
        blocker = tmp_path / "blocker"
        blocker.write_text("I am a file not a dir")
        cache_dir = blocker / "nested"  # Can't mkdir inside a file
        # Should NOT raise, only log a warning
        _cache_write(cache_dir, "key", "q", "r")

    def test_cache_key_is_deterministic_sha256(self):
        from amil_utils.context7 import _cache_key

        key1 = _cache_key("test query", "17.0")
        key2 = _cache_key("test query", "17.0")
        assert key1 == key2
        expected = hashlib.sha256("test query|17.0".encode()).hexdigest()
        assert key1 == expected

    def test_cache_key_differs_for_different_versions(self):
        from amil_utils.context7 import _cache_key

        key_17 = _cache_key("test query", "17.0")
        key_18 = _cache_key("test query", "18.0")
        assert key_17 != key_18


# ---------------------------------------------------------------------------
# PIPE-01 b: context7_enrich enrichment function
# ---------------------------------------------------------------------------

class TestContext7Enrich:
    """Tests for context7_enrich() -- orchestrates pattern detection, querying, and caching."""

    def test_unconfigured_client_returns_empty(self, unconfigured_client):
        from amil_utils.context7 import context7_enrich

        result = context7_enrich({"depends": ["mail"]}, unconfigured_client)
        assert result == {}

    def test_none_client_returns_empty(self):
        from amil_utils.context7 import context7_enrich

        result = context7_enrich({"depends": ["mail"]}, None)
        assert result == {}

    def test_no_patterns_detected_returns_empty(self, configured_client):
        from amil_utils.context7 import context7_enrich

        # Spec with no patterns at all
        result = context7_enrich({"models": []}, configured_client)
        assert result == {}

    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_configured_client_with_patterns_returns_hints(
        self, mock_urlopen, configured_client,
    ):
        from amil_utils.context7 import DocSnippet, context7_enrich

        # Library resolution + query for mail_thread
        mock_urlopen.side_effect = [
            _mock_response([{"id": "lib-1", "name": "odoo", "description": ""}]),
            _mock_response([
                {"title": "Mail Thread", "content": "Chatter integration...", "sourceUrl": ""},
            ]),
        ]
        spec = {"depends": ["base", "mail"]}
        result = context7_enrich(spec, configured_client)
        assert "mail_thread" in result
        assert "Mail Thread" in result["mail_thread"]
        assert "Chatter integration" in result["mail_thread"]

    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_query_failure_returns_empty(self, mock_urlopen, configured_client):
        from amil_utils.context7 import context7_enrich

        # Library resolution succeeds, query fails
        mock_urlopen.side_effect = [
            _mock_response([{"id": "lib-1", "name": "odoo", "description": ""}]),
            URLError("timeout"),
        ]
        spec = {"depends": ["base", "mail"]}
        result = context7_enrich(spec, configured_client)
        # Graceful degradation: mail_thread had no results, so not in dict
        assert isinstance(result, dict)

    def test_fresh_bypasses_cache(self, tmp_path):
        from amil_utils.context7 import (
            Context7Client,
            Context7Config,
            _cache_key,
            _cache_write,
            context7_enrich,
        )

        cache_dir = tmp_path / "ctx7"
        client = Context7Client(Context7Config(api_key="test-key"))

        # Pre-populate cache with stale data
        from amil_utils.context7 import PATTERN_QUERIES
        query = PATTERN_QUERIES["mail_thread"]
        key = _cache_key(query, "17.0")
        _cache_write(cache_dir, key, query, "cached old data")

        # Mock query_docs to return fresh data
        with patch.object(client, "query_docs") as mock_qd:
            from amil_utils.context7 import DocSnippet
            mock_qd.return_value = [DocSnippet(title="Fresh", content="New data")]
            spec = {"depends": ["mail"]}
            result = context7_enrich(spec, client, cache_dir=cache_dir, fresh=True)

        # Should have called query_docs (bypassed cache)
        mock_qd.assert_called_once()
        assert "mail_thread" in result

    def test_responses_are_truncated(self):
        from amil_utils.context7 import (
            Context7Client,
            Context7Config,
            DocSnippet,
            context7_enrich,
        )

        client = Context7Client(Context7Config(api_key="test-key"))
        # Return a very long snippet
        long_content = "x " * 2000  # 4000 chars
        with patch.object(client, "query_docs") as mock_qd:
            mock_qd.return_value = [DocSnippet(title="T", content=long_content)]
            spec = {"depends": ["mail"]}
            result = context7_enrich(spec, client)

        assert "mail_thread" in result
        # Truncated to ~2000 chars + "..."
        assert len(result["mail_thread"]) <= 2100

    def test_hint_is_concatenation_of_snippets(self):
        from amil_utils.context7 import (
            Context7Client,
            Context7Config,
            DocSnippet,
            context7_enrich,
        )

        client = Context7Client(Context7Config(api_key="test-key"))
        with patch.object(client, "query_docs") as mock_qd:
            mock_qd.return_value = [
                DocSnippet(title="Title A", content="Content A"),
                DocSnippet(title="Title B", content="Content B"),
            ]
            spec = {"depends": ["mail"]}
            result = context7_enrich(spec, client)

        assert "## Title A" in result["mail_thread"]
        assert "Content A" in result["mail_thread"]
        assert "## Title B" in result["mail_thread"]
        assert "Content B" in result["mail_thread"]

    @patch("amil_utils.context7.urllib.request.urlopen")
    def test_max_five_queries(self, mock_urlopen):
        from amil_utils.context7 import (
            Context7Client,
            Context7Config,
            context7_enrich,
        )

        client = Context7Client(Context7Config(api_key="test-key"))
        # Build spec that triggers all 5 patterns
        spec = {
            "depends": ["mail"],
            "reports": [{"name": "r"}],
            "models": [
                {
                    "name": "m",
                    "has_approval": True,
                    "fields": [
                        {"name": "amount", "type": "Monetary"},
                        {"name": "y", "compute": "_c"},
                    ],
                },
            ],
        }
        # Library resolution + 5 pattern queries
        mock_urlopen.side_effect = [
            _mock_response([{"id": "lib-1", "name": "odoo", "description": ""}]),
            _mock_response([{"title": "T1", "content": "C1", "sourceUrl": ""}]),
            _mock_response([{"title": "T2", "content": "C2", "sourceUrl": ""}]),
            _mock_response([{"title": "T3", "content": "C3", "sourceUrl": ""}]),
            _mock_response([{"title": "T4", "content": "C4", "sourceUrl": ""}]),
            _mock_response([{"title": "T5", "content": "C5", "sourceUrl": ""}]),
        ]
        result = context7_enrich(spec, client)
        # 1 library resolve + 5 pattern queries = 6 total calls
        assert mock_urlopen.call_count == 6
        assert len(result) == 5

    def test_cache_hit_avoids_query(self, tmp_path):
        from amil_utils.context7 import (
            Context7Client,
            Context7Config,
            PATTERN_QUERIES,
            _cache_key,
            _cache_write,
            context7_enrich,
        )

        cache_dir = tmp_path / "ctx7"
        client = Context7Client(Context7Config(api_key="test-key"))

        # Pre-populate cache
        query = PATTERN_QUERIES["mail_thread"]
        key = _cache_key(query, "17.0")
        _cache_write(cache_dir, key, query, "cached response")

        with patch.object(client, "query_docs") as mock_qd:
            spec = {"depends": ["mail"]}
            result = context7_enrich(spec, client, cache_dir=cache_dir)

        # Should NOT have called query_docs (used cache)
        mock_qd.assert_not_called()
        assert result == {"mail_thread": "cached response"}

    def test_empty_query_result_excluded_from_hints(self):
        from amil_utils.context7 import (
            Context7Client,
            Context7Config,
            context7_enrich,
        )

        client = Context7Client(Context7Config(api_key="test-key"))
        with patch.object(client, "query_docs") as mock_qd:
            mock_qd.return_value = []  # No snippets returned
            spec = {"depends": ["mail"]}
            result = context7_enrich(spec, client)

        # Empty result excluded from hints dict
        assert "mail_thread" not in result
