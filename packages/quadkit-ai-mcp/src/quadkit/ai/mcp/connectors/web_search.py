"""WebSearch connector — search the web via Brave, SerpAPI, or Google APIs.

Tools exposed:
- ``web_search`` — Search the web and return a ranked snippet list

The active provider is selected by ``provider`` in the configuration.
Each provider requires its own ``api_key``.

Supported providers:
- ``brave``   — Brave Search API (https://brave.com/search/api/)
- ``serpapi`` — SerpAPI (https://serpapi.com/)
- ``google``  — Google Custom Search JSON API (requires CX ID in the URL)
"""

from __future__ import annotations

from typing import Any

from quadkit.ai.mcp.types import MCPToolDefinition, MCPToolResult
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str

logger = get_logger(__name__)


class WebSearchConnector:
    """Web search via configurable provider (Brave, SerpAPI, Google).

    All provider calls require ``aiohttp``. Each provider has its own
    authentication mechanism configured via ``api_key``.

    Example::

        connector = WebSearchConnector(
            provider="brave",
            api_key="BSAxxxxxxxxxx",
            max_results=5,
        )
    """

    def __init__(
        self,
        provider: str = "brave",
        api_key: str = "",
        max_results: int = 10,
    ) -> None:
        """Initialize the web search connector.

        Args:
            provider: Search provider name: 'brave', 'serpapi', or 'google'.
            api_key: API key for the chosen provider.
            max_results: Maximum number of search results to return.

        Raises:
            ValueError: If an unsupported provider name is given.
        """
        supported = {"brave", "serpapi", "google"}
        if provider not in supported:
            raise ValueError(
                f"Unsupported search provider '{provider}'. "
                f"Choose from: {sorted(supported)}"
            )
        self._provider = provider
        self._api_key = api_key
        self._max_results = max_results

    # ------------------------------------------------------------------
    # MCPToolProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions."""
        return [
            MCPToolDefinition(
                name="web_search",
                description=(
                    f"Search the web using {self._provider}. "
                    "Returns ranked results with titles, URLs, and snippets."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of results to return",
                            "default": min(5, self._max_results),
                        },
                    },
                    "required": ["query"],
                },
            ).to_dict(),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Dispatch tool calls.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            MCPToolResult with search results or error.
        """
        from quadkit.contracts.mcp.exceptions import MCPToolCallError

        if name == "web_search":
            return await self._web_search(arguments)
        raise MCPToolCallError(
            message=f"Unknown web_search tool: {name}", tool_name=name
        )

    # ------------------------------------------------------------------
    # Tool implementation
    # ------------------------------------------------------------------

    async def _web_search(self, arguments: dict[str, Any]) -> MCPToolResult:
        query: str = arguments.get("query", "")
        count: int = min(
            int(arguments.get("count") or 5),
            self._max_results,
        )

        if not query:
            return MCPToolResult.error("'query' argument is required")
        if not self._api_key:
            return MCPToolResult.error(
                f"No API key configured for provider '{self._provider}'. "
                "Set api_key in the connector configuration."
            )

        try:
            import aiohttp
        except ImportError:
            return MCPToolResult.error(
                "aiohttp is required for WebSearchConnector. "
                "Install it with: pip install aiohttp"
            )

        try:
            results = await self._dispatch_search(aiohttp, query, count)
            return MCPToolResult.text(dumps_str(results))
        except Exception as exc:  # noqa: BLE001 — external search provider boundary
            error_type = type(exc).__name__
            logger.warning(
                "web_search_error",
                provider=self._provider,
                error_type=error_type,
            )
            return MCPToolResult.error(f"Search failed ({error_type})")

    async def _dispatch_search(
        self, aiohttp: Any, query: str, count: int
    ) -> list[dict[str, Any]]:
        if self._provider == "brave":
            return await self._brave_search(aiohttp, query, count)
        if self._provider == "serpapi":
            return await self._serpapi_search(aiohttp, query, count)
        return await self._google_search(aiohttp, query, count)

    async def _brave_search(
        self, aiohttp: Any, query: str, count: int
    ) -> list[dict[str, Any]]:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._api_key,
        }
        params = {"q": query, "count": count}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
        results_raw = data.get("web", {}).get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
            }
            for r in results_raw[:count]
        ]

    async def _serpapi_search(
        self, aiohttp: Any, query: str, count: int
    ) -> list[dict[str, Any]]:
        url = "https://serpapi.com/search.json"
        params = {
            "q": query,
            "num": count,
            "api_key": self._api_key,
            "engine": "google",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
        results_raw = data.get("organic_results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
            }
            for r in results_raw[:count]
        ]

    async def _google_search(
        self, aiohttp: Any, query: str, count: int
    ) -> list[dict[str, Any]]:
        # Require cx (search engine ID) in the api_key as "key:cx"
        if ":" not in self._api_key:
            return [
                {
                    "error": (
                        "Google CSE requires 'api_key' in format 'KEY:CX' "
                        "(API key and Custom Search Engine ID separated by ':')"
                    )
                }
            ]
        key, cx = self._api_key.split(":", 1)
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"q": query, "num": min(count, 10), "key": key, "cx": cx}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
        results_raw = data.get("items", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
            }
            for r in results_raw[:count]
        ]


__all__ = ["WebSearchConnector"]
