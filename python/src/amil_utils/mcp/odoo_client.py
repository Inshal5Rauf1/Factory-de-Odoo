"""Odoo XML-RPC client wrapper for MCP server.

Provides OdooClient, a clean abstraction over xmlrpc.client.ServerProxy
for authenticating with and querying a live Odoo instance. This class
is the single mock boundary used by unit tests.
"""
from __future__ import annotations

import xmlrpc.client
from dataclasses import dataclass


@dataclass(frozen=True)
class OdooConfig:
    """Odoo connection configuration from environment variables.

    All fields are immutable strings. Construct from os.environ at startup.
    """

    url: str
    db: str
    username: str
    api_key: str


class OdooClient:
    """XML-RPC client for Odoo introspection.

    Wraps xmlrpc.client.ServerProxy for /xmlrpc/2/common and /xmlrpc/2/object.

    Authentication is lazy: uid is cached after first authenticate() call.
    The uid property triggers authentication automatically on first access.
    """

    def __init__(self, config: OdooConfig) -> None:
        self._config = config
        self._uid: int | None = None
        self._common = xmlrpc.client.ServerProxy(
            f"{config.url}/xmlrpc/2/common"
        )
        self._models = xmlrpc.client.ServerProxy(
            f"{config.url}/xmlrpc/2/object"
        )

    def authenticate(self) -> int:
        """Authenticate with Odoo and cache the user id.

        Calls /xmlrpc/2/common authenticate() and caches the returned uid.

        Returns:
            The authenticated user id (integer).

        Raises:
            ConnectionError: If authentication fails (falsy uid returned).
        """
        uid = self._common.authenticate(
            self._config.db,
            self._config.username,
            self._config.api_key,
            {},
        )
        if not uid:
            msg = (
                f"Authentication failed for {self._config.username}"
                f"@{self._config.db}"
            )
            raise ConnectionError(msg)
        self._uid = uid
        return uid

    @property
    def uid(self) -> int:
        """Return cached uid, authenticating lazily on first access."""
        if self._uid is None:
            self.authenticate()
        assert self._uid is not None
        return self._uid

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list,
        kwargs: dict | None = None,
    ) -> object:
        """Call execute_kw on the Odoo object endpoint.

        Args:
            model: Technical model name (e.g. 'res.partner').
            method: Method name (e.g. 'search_read', 'fields_get').
            args: Positional arguments list.
            kwargs: Keyword arguments dict (optional).

        Returns:
            The raw XML-RPC response (usually a list or dict).
        """
        return self._models.execute_kw(
            self._config.db,
            self.uid,
            self._config.api_key,
            model,
            method,
            args,
            kwargs or {},
        )

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list[str],
        limit: int = 0,
    ) -> list[dict]:
        """Convenience wrapper for Odoo search_read.

        Args:
            model: Technical model name (e.g. 'ir.model').
            domain: Odoo domain filter list (e.g. [['state', '=', 'installed']]).
            fields: List of field names to return.
            limit: Maximum records to return (0 means no limit).

        Returns:
            List of dicts, each representing one record.
        """
        kw: dict = {"fields": fields}
        if limit:
            kw["limit"] = limit
        return self.execute_kw(model, "search_read", [domain], kw)
