"""Slack connector — read channels, post messages, search history via MCP.

Tools exposed:
- ``slack_list_channels``   — List public channels in the workspace
- ``slack_get_history``     — Read recent messages from a channel
- ``slack_post_message``    — Send a message to a channel or user
- ``slack_search_messages`` — Search message history (requires search scope)

Resources exposed:
- ``slack://channels``          — All channels
- ``slack://channel/{channel}`` — Channel history

All Slack API calls use HTTPS with the provided Bot OAuth token (*xoxb-…*).
"""

from __future__ import annotations

from typing import Any

from quadkit.ai.mcp.types import MCPResource, MCPToolDefinition, MCPToolResult
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str

logger = get_logger(__name__)

_SLACK_API = "https://slack.com/api"


class SlackConnector:
    """Slack workspace access via MCP tools and resources.

    Requires a Slack Bot OAuth token with appropriate scopes:
    - ``channels:read``, ``channels:history``  — for reading channels
    - ``chat:write``                            — for posting messages
    - ``search:read``                           — for searching messages

    Example::

        connector = SlackConnector(bot_token="xoxb-xxxx", max_messages=50)
    """

    def __init__(
        self,
        bot_token: str,
        *,
        max_messages: int = 100,
    ) -> None:
        """Initialize the Slack connector.

        Args:
            bot_token: Slack Bot OAuth token (xoxb-...).
            max_messages: Maximum messages to return per history request.

        Raises:
            ValueError: If ``bot_token`` is empty.
        """
        if not bot_token:
            raise ValueError("SlackConnector requires a non-empty bot_token")
        self._token = bot_token
        self._max_messages = max_messages

    # ------------------------------------------------------------------
    # MCPToolProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions."""
        return [
            MCPToolDefinition(
                name="slack_list_channels",
                description="List public channels in the Slack workspace",
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum channels to return",
                            "default": 100,
                        }
                    },
                },
            ).to_dict(),
            MCPToolDefinition(
                name="slack_get_history",
                description="Read recent messages from a Slack channel",
                input_schema={
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Channel ID or name (e.g. C123456 or #general)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of messages to return",
                            "default": 20,
                        },
                    },
                    "required": ["channel"],
                },
            ).to_dict(),
            MCPToolDefinition(
                name="slack_post_message",
                description="Send a message to a Slack channel or user",
                input_schema={
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Channel ID or user ID",
                        },
                        "text": {
                            "type": "string",
                            "description": "Message text (Markdown supported)",
                        },
                    },
                    "required": ["channel", "text"],
                },
            ).to_dict(),
            MCPToolDefinition(
                name="slack_search_messages",
                description="Search Slack message history (requires search:read scope)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Maximum results",
                            "default": 20,
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
            MCPToolResult with JSON data or error.
        """
        from quadkit.contracts.mcp.exceptions import MCPToolCallError

        dispatch = {
            "slack_list_channels": self._list_channels,
            "slack_get_history": self._get_history,
            "slack_post_message": self._post_message,
            "slack_search_messages": self._search_messages,
        }
        handler = dispatch.get(name)
        if handler is None:
            raise MCPToolCallError(
                message=f"Unknown Slack tool: {name}", tool_name=name
            )
        return await handler(arguments)

    # ------------------------------------------------------------------
    # MCPResourceProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_resources(self) -> list[dict[str, Any]]:
        """Return the channel history resource.

        Resource *listing* is static — the URI is fixed; the content is
        fetched on demand by :meth:`read_resource` (a network round-trip
        here would slow tool discovery and burn rate limit).
        """
        return [
            MCPResource(
                uri="slack://channels",
                name="Slack Channels",
                description="All public channels",
                mime_type="application/json",
            ).to_dict()
        ]

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a Slack resource by URI.

        Args:
            uri: ``slack://channels`` or ``slack://channel/{id}``

        Returns:
            MCP resource content dict.
        """
        if uri == "slack://channels":
            result = await self._list_channels({})
        else:
            channel_id = uri.removeprefix("slack://channel/")
            result = await self._get_history({"channel": channel_id})
        text = result.content[0]["text"] if result.content else "[]"
        return {
            "contents": [{"uri": uri, "mimeType": "application/json", "text": text}]
        }

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _list_channels(self, arguments: dict[str, Any]) -> MCPToolResult:
        limit = min(int(arguments.get("limit") or 100), 1000)
        data = await self._api_get(
            "conversations.list",
            {"limit": limit, "types": "public_channel"},
        )
        if not data.get("ok"):
            return MCPToolResult.error("Slack API request failed")
        channels = [
            {
                "id": c["id"],
                "name": c["name"],
                "topic": c.get("topic", {}).get("value", ""),
            }
            for c in data.get("channels", [])
        ]
        return MCPToolResult.text(dumps_str(channels))

    async def _get_history(self, arguments: dict[str, Any]) -> MCPToolResult:
        channel = arguments.get("channel", "")
        limit = min(int(arguments.get("limit") or 20), self._max_messages)
        if not channel:
            return MCPToolResult.error("'channel' argument is required")
        # Strip # prefix if present
        if channel.startswith("#"):
            channel = channel[1:]
        data = await self._api_get(
            "conversations.history",
            {"channel": channel, "limit": limit},
        )
        if not data.get("ok"):
            return MCPToolResult.error("Slack API request failed")
        messages = [
            {"ts": m["ts"], "user": m.get("user", ""), "text": m.get("text", "")}
            for m in data.get("messages", [])
        ]
        return MCPToolResult.text(dumps_str(messages))

    async def _post_message(self, arguments: dict[str, Any]) -> MCPToolResult:
        channel = arguments.get("channel", "")
        text = arguments.get("text", "")
        if not channel or not text:
            return MCPToolResult.error("'channel' and 'text' are required")
        data = await self._api_post(
            "chat.postMessage",
            {"channel": channel, "text": text},
        )
        if not data.get("ok"):
            return MCPToolResult.error("Slack API request failed")
        return MCPToolResult.text(
            dumps_str({"ts": data.get("ts"), "channel": data.get("channel")})
        )

    async def _search_messages(self, arguments: dict[str, Any]) -> MCPToolResult:
        query = arguments.get("query", "")
        count = min(int(arguments.get("count") or 20), 100)
        if not query:
            return MCPToolResult.error("'query' argument is required")
        data = await self._api_get(
            "search.messages",
            {"query": query, "count": count},
        )
        if not data.get("ok"):
            return MCPToolResult.error("Slack API request failed")
        matches = [
            {
                "channel": m.get("channel", {}).get("name", ""),
                "text": m.get("text", ""),
                "ts": m.get("ts", ""),
                "permalink": m.get("permalink", ""),
            }
            for m in data.get("messages", {}).get("matches", [])
        ]
        return MCPToolResult.text(dumps_str(matches))

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _api_get(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            import aiohttp
        except ImportError:
            return {"ok": False, "error": "aiohttp is required for SlackConnector"}
        url = f"{_SLACK_API}/{method}"
        try:
            async with aiohttp.ClientSession(headers=self._headers()) as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    result: dict[str, Any] = await resp.json(content_type=None)
                    return result
        except Exception as exc:  # noqa: BLE001 — external Slack API boundary
            error_type = type(exc).__name__
            logger.warning("slack_get_failed", method=method, error_type=error_type)
            return {"ok": False, "error": f"Slack request failed ({error_type})"}

    async def _api_post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            import aiohttp
        except ImportError:
            return {"ok": False, "error": "aiohttp is required for SlackConnector"}
        url = f"{_SLACK_API}/{method}"
        try:
            async with aiohttp.ClientSession(headers=self._headers()) as session:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    result: dict[str, Any] = await resp.json(content_type=None)
                    return result
        except Exception as exc:  # noqa: BLE001 — external Slack API boundary
            error_type = type(exc).__name__
            logger.warning("slack_post_failed", method=method, error_type=error_type)
            return {"ok": False, "error": f"Slack request failed ({error_type})"}


__all__ = ["SlackConnector"]
