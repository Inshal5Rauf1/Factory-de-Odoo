"""Unit tests for mcp/odoo_client.py — OdooConfig and OdooClient.

All XML-RPC calls are mocked via MagicMock replacements of the internal
ServerProxy objects. No network or live Odoo instance is required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from amil_utils.mcp.odoo_client import OdooClient, OdooConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config() -> OdooConfig:
    """Standard test config with known values."""
    return OdooConfig(
        url="http://odoo.test:8069",
        db="test_db",
        username="testuser",
        api_key="test-api-key-123",
    )


def _make_client(
    config: OdooConfig, uid: int = 2
) -> OdooClient:
    """Create an OdooClient with mocked ServerProxy objects."""
    client = OdooClient(config)
    client._common = MagicMock()
    client._models = MagicMock()
    client._common.authenticate.return_value = uid
    return client


# ---------------------------------------------------------------------------
# OdooConfig tests
# ---------------------------------------------------------------------------


class TestOdooConfig:
    """OdooConfig is a frozen dataclass holding connection credentials."""

    def test_fields_are_stored(self, config: OdooConfig) -> None:
        assert config.url == "http://odoo.test:8069"
        assert config.db == "test_db"
        assert config.username == "testuser"
        assert config.api_key == "test-api-key-123"

    def test_frozen_immutability(self, config: OdooConfig) -> None:
        """OdooConfig instances are immutable (frozen=True)."""
        with pytest.raises(AttributeError):
            config.url = "http://other:8069"  # type: ignore[misc]

    def test_equality(self) -> None:
        """Two OdooConfigs with the same values compare equal (dataclass)."""
        a = OdooConfig(url="u", db="d", username="n", api_key="k")
        b = OdooConfig(url="u", db="d", username="n", api_key="k")
        assert a == b

    def test_inequality(self) -> None:
        a = OdooConfig(url="u", db="d1", username="n", api_key="k")
        b = OdooConfig(url="u", db="d2", username="n", api_key="k")
        assert a != b


# ---------------------------------------------------------------------------
# OdooClient — authentication
# ---------------------------------------------------------------------------


class TestOdooClientAuthenticate:
    """Test authenticate() XML-RPC calls and uid caching."""

    def test_authenticate_returns_uid(self, config: OdooConfig) -> None:
        client = _make_client(config, uid=7)
        result = client.authenticate()
        assert result == 7

    def test_authenticate_caches_uid(self, config: OdooConfig) -> None:
        client = _make_client(config, uid=7)
        client.authenticate()
        assert client._uid == 7

    def test_authenticate_calls_common_authenticate(
        self, config: OdooConfig
    ) -> None:
        client = _make_client(config, uid=3)
        client.authenticate()
        client._common.authenticate.assert_called_once_with(
            "test_db", "testuser", "test-api-key-123", {}
        )

    def test_authenticate_raises_on_falsy_uid(
        self, config: OdooConfig
    ) -> None:
        """Falsy uid (False, 0, None) raises ConnectionError."""
        for falsy_val in (False, 0, None):
            client = _make_client(config)
            client._common.authenticate.return_value = falsy_val
            with pytest.raises(ConnectionError, match="Authentication failed"):
                client.authenticate()

    def test_authenticate_error_message_includes_user_and_db(
        self, config: OdooConfig
    ) -> None:
        client = _make_client(config)
        client._common.authenticate.return_value = False
        with pytest.raises(ConnectionError, match="testuser"):
            client.authenticate()

    def test_authenticate_does_not_cache_on_failure(
        self, config: OdooConfig
    ) -> None:
        client = _make_client(config)
        client._common.authenticate.return_value = False
        with pytest.raises(ConnectionError):
            client.authenticate()
        assert client._uid is None


# ---------------------------------------------------------------------------
# OdooClient — uid property (lazy authentication)
# ---------------------------------------------------------------------------


class TestOdooClientUidProperty:
    """Test the lazy uid property that auto-authenticates."""

    def test_uid_triggers_auth_on_first_access(
        self, config: OdooConfig
    ) -> None:
        client = _make_client(config, uid=10)
        assert client._uid is None
        uid = client.uid
        assert uid == 10
        client._common.authenticate.assert_called_once()

    def test_uid_returns_cached_value(self, config: OdooConfig) -> None:
        client = _make_client(config, uid=10)
        client.authenticate()
        client._common.authenticate.reset_mock()
        uid = client.uid
        assert uid == 10
        client._common.authenticate.assert_not_called()


# ---------------------------------------------------------------------------
# OdooClient — execute_kw
# ---------------------------------------------------------------------------


class TestOdooClientExecuteKw:
    """Test execute_kw passes correct args to models proxy."""

    def test_execute_kw_basic(self, config: OdooConfig) -> None:
        client = _make_client(config, uid=2)
        client.authenticate()
        expected = [{"id": 1}]
        client._models.execute_kw.return_value = expected

        result = client.execute_kw("res.partner", "search", [[]])
        assert result == expected
        client._models.execute_kw.assert_called_once_with(
            "test_db", 2, "test-api-key-123",
            "res.partner", "search", [[]],
            {},
        )

    def test_execute_kw_with_kwargs(self, config: OdooConfig) -> None:
        client = _make_client(config, uid=2)
        client.authenticate()
        client._models.execute_kw.return_value = []

        client.execute_kw(
            "res.partner", "fields_get", [],
            kwargs={"attributes": ["string", "type"]},
        )
        client._models.execute_kw.assert_called_once_with(
            "test_db", 2, "test-api-key-123",
            "res.partner", "fields_get", [],
            {"attributes": ["string", "type"]},
        )

    def test_execute_kw_lazy_auth(self, config: OdooConfig) -> None:
        """execute_kw triggers lazy authenticate when uid is not cached."""
        client = _make_client(config, uid=4)
        client._models.execute_kw.return_value = []
        # No prior authenticate call
        client.execute_kw("res.partner", "search", [[]])
        # uid property should have triggered authenticate
        client._common.authenticate.assert_called_once()

    def test_execute_kw_none_kwargs_becomes_empty_dict(
        self, config: OdooConfig
    ) -> None:
        client = _make_client(config, uid=2)
        client.authenticate()
        client._models.execute_kw.return_value = []

        client.execute_kw("res.partner", "search", [[]], kwargs=None)
        call_args = client._models.execute_kw.call_args[0]
        assert call_args[6] == {}


# ---------------------------------------------------------------------------
# OdooClient — search_read convenience wrapper
# ---------------------------------------------------------------------------


class TestOdooClientSearchRead:
    """Test search_read builds correct execute_kw call."""

    def test_search_read_basic(self, config: OdooConfig) -> None:
        client = _make_client(config, uid=2)
        client.authenticate()
        expected = [{"id": 1, "name": "Admin"}]
        client._models.execute_kw.return_value = expected

        result = client.search_read(
            "res.partner", [["is_company", "=", True]], ["name", "email"]
        )
        assert result == expected
        client._models.execute_kw.assert_called_once_with(
            "test_db", 2, "test-api-key-123",
            "res.partner", "search_read",
            [[["is_company", "=", True]]],
            {"fields": ["name", "email"]},
        )

    def test_search_read_with_limit(self, config: OdooConfig) -> None:
        client = _make_client(config, uid=2)
        client.authenticate()
        client._models.execute_kw.return_value = []

        client.search_read("ir.model", [], ["model"], limit=5)
        call_args = client._models.execute_kw.call_args[0]
        assert call_args[6] == {"fields": ["model"], "limit": 5}

    def test_search_read_limit_zero_omitted(
        self, config: OdooConfig
    ) -> None:
        """limit=0 (default) does NOT add 'limit' key to kwargs."""
        client = _make_client(config, uid=2)
        client.authenticate()
        client._models.execute_kw.return_value = []

        client.search_read("ir.model", [], ["model"], limit=0)
        call_args = client._models.execute_kw.call_args[0]
        assert "limit" not in call_args[6]

    def test_search_read_empty_domain(self, config: OdooConfig) -> None:
        client = _make_client(config, uid=2)
        client.authenticate()
        client._models.execute_kw.return_value = []

        client.search_read("ir.model", [], ["model"])
        call_args = client._models.execute_kw.call_args[0]
        # domain is wrapped in a list
        assert call_args[5] == [[]]

    def test_search_read_returns_list_of_dicts(
        self, config: OdooConfig
    ) -> None:
        client = _make_client(config, uid=2)
        client.authenticate()
        records = [
            {"id": 1, "model": "res.partner"},
            {"id": 2, "model": "res.users"},
        ]
        client._models.execute_kw.return_value = records

        result = client.search_read("ir.model", [], ["model"])
        assert len(result) == 2
        assert all(isinstance(r, dict) for r in result)


# ---------------------------------------------------------------------------
# OdooClient — constructor wiring
# ---------------------------------------------------------------------------


class TestOdooClientConstructor:
    """Test constructor creates ServerProxy objects with correct URLs."""

    @patch("amil_utils.mcp.odoo_client.xmlrpc.client.ServerProxy")
    def test_constructor_creates_common_proxy(
        self, mock_sp: MagicMock
    ) -> None:
        cfg = OdooConfig(
            url="http://myhost:8069",
            db="d", username="u", api_key="k",
        )
        OdooClient(cfg)
        calls = [c[0][0] for c in mock_sp.call_args_list]
        assert "http://myhost:8069/xmlrpc/2/common" in calls

    @patch("amil_utils.mcp.odoo_client.xmlrpc.client.ServerProxy")
    def test_constructor_creates_models_proxy(
        self, mock_sp: MagicMock
    ) -> None:
        cfg = OdooConfig(
            url="http://myhost:8069",
            db="d", username="u", api_key="k",
        )
        OdooClient(cfg)
        calls = [c[0][0] for c in mock_sp.call_args_list]
        assert "http://myhost:8069/xmlrpc/2/object" in calls


# ---------------------------------------------------------------------------
# mcp/__main__.py — verify importability
# ---------------------------------------------------------------------------


class TestMcpMainModule:
    """Verify __main__.py imports cleanly and wires main()."""

    def test_main_function_exists(self) -> None:
        """The server module exposes a callable main()."""
        from amil_utils.mcp.server import main
        assert callable(main)

    def test_main_module_imports_main_from_server(self) -> None:
        """__main__.py re-exports main from server module."""
        import importlib
        # We can't execute __main__ directly (it calls main()),
        # but we can verify the import chain works.
        spec = importlib.util.find_spec("amil_utils.mcp.__main__")
        assert spec is not None

    def test_main_raises_without_mcp_package(self) -> None:
        """main() raises RuntimeError when mcp package is not installed."""
        from amil_utils.mcp.server import main, _HAS_MCP
        if not _HAS_MCP:
            with pytest.raises(RuntimeError, match="mcp package not installed"):
                main()
