"""Search resource provider — exposes search indexes as MCP resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.ai.mcp.types import MCPResource
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str

logger = get_logger(__name__)

if TYPE_CHECKING:
    from quadkit.contracts.search import SearchEngineProtocol


class SearchResourceProvider:
    """Exposes search indexes as MCP resources.

    MCP clients can search indexed content by providing a query
    in the URI.

    Usage::

        provider = SearchResourceProvider(
            search_engine=search,
            indexes=["products", "services"],
        )
        registry.register(provider)

    URIs: ``search://products?q=headphones``
    """

    name = "search"
    description = "Search indexes"
    mime_type = "application/json"

    def __init__(
        self,
        search_engine: SearchEngineProtocol,
        indexes: list[str] | None = None,
        uri_prefix: str = "search",
        default_limit: int = 10,
    ) -> None:
        self._search = search_engine
        self._indexes = indexes or []
        self._uri_prefix = uri_prefix
        self._default_limit = default_limit

    @property
    def uri_template(self) -> str:
        return f"{self._uri_prefix}://{{index}}?q={{query}}"

    def can_handle(self, uri: str) -> bool:
        return uri.startswith(f"{self._uri_prefix}://")

    async def list(self) -> list[MCPResource]:
        """List available search indexes."""
        return [
            MCPResource(
                uri=f"{self._uri_prefix}://{index}",
                name=f"Search: {index}",
                description=f"Full-text search in {index} index",
                mime_type="application/json",
            )
            for index in self._indexes
        ]

    async def read(self, uri: str) -> str:
        """Execute a search query.

        URI format: ``search://products?q=headphones&limit=5``
        """
        clean = uri.replace(f"{self._uri_prefix}://", "")

        # Parse index and query params
        if "?" in clean:
            index, params_str = clean.split("?", 1)
            params = dict(p.split("=", 1) for p in params_str.split("&") if "=" in p)
        else:
            index = clean
            params = {}

        query = params.get("q", "*")
        try:
            limit = int(params.get("limit", str(self._default_limit)))
            limit = max(1, limit)
        except (TypeError, ValueError):
            # Malformed ?limit= must not escape — resource reads follow the
            # framework pagination guard pattern (fall back, never raise).
            limit = self._default_limit

        try:
            result = await self._search.search(  # type: ignore[call-arg]
                index=index,
                query=query,
                limit=limit,
            )
            if hasattr(result, "is_ok"):
                if result.is_ok():
                    return dumps_str(result.unwrap())  # type: ignore[attr-defined]
                error = result.unwrap_err()  # type: ignore[attr-defined]
                return dumps_str({"error": f"Search failed ({type(error).__name__})"})
            return dumps_str(result)
        except Exception as exc:  # noqa: BLE001 — resource read failures are logged, never raised
            error_type = type(exc).__name__
            logger.error("search_resource_error", error_type=error_type)
            return dumps_str({"error": f"Search failed ({error_type})"})
