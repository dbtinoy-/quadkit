"""WebFetch connector — fetch URL content and convert HTML to text via MCP.

Tools exposed:
- ``web_fetch``     — Fetch a URL and return text/markdown content
- ``web_screenshot``— (placeholder) Not implemented; returns guidance message

All HTTP calls are made using ``aiohttp`` (required). If ``html2text`` is
available it is used for HTML→Markdown conversion; otherwise, raw HTML is
returned with a notice.
"""

from __future__ import annotations

import asyncio
from typing import Any
import urllib.parse

from quadkit.ai.mcp.types import MCPToolDefinition, MCPToolResult
from quadkit.contracts.security import is_safe_url_for_request
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

_DEFAULT_USER_AGENT = "the optional provider/1.0 (+https://github.com/quadkit)"
_DEFAULT_MAX_BYTES = 512 * 1024  # 512 KB


class WebFetchConnector:
    """Fetch arbitrary URLs and return text content via MCP tools.

    Uses ``aiohttp`` for HTTP; optionally uses ``html2text`` to convert HTML
    responses to Markdown for better readability.

    Example::

        connector = WebFetchConnector(max_content_bytes=256*1024)
    """

    def __init__(
        self,
        *,
        max_content_bytes: int = _DEFAULT_MAX_BYTES,
        user_agent: str = _DEFAULT_USER_AGENT,
    ) -> None:
        """Initialize the WebFetch connector.

        Args:
            max_content_bytes: Maximum response body size (default 512 KB).
            user_agent: HTTP User-Agent header sent with all requests.
        """
        self._max_bytes = max_content_bytes
        self._user_agent = user_agent

    # ------------------------------------------------------------------
    # MCPToolProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions."""
        return [
            MCPToolDefinition(
                name="web_fetch",
                description=(
                    "Fetch a URL and return its text content. "
                    "HTML is converted to Markdown when possible."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to fetch",
                        },
                        "timeout": {
                            "type": "number",
                            "description": "Request timeout in seconds (default 30)",
                            "default": 30,
                        },
                    },
                    "required": ["url"],
                },
            ).to_dict(),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Dispatch tool calls.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            MCPToolResult with fetched content or error.
        """
        from quadkit.contracts.mcp.exceptions import MCPToolCallError

        if name == "web_fetch":
            return await self._web_fetch(arguments)
        raise MCPToolCallError(
            message=f"Unknown web_fetch tool: {name}", tool_name=name
        )

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _web_fetch(self, arguments: dict[str, Any]) -> MCPToolResult:
        url: str = arguments.get("url", "")
        timeout: float = float(arguments.get("timeout") or 30)

        if not url:
            return MCPToolResult.error("'url' argument is required")
        if not url.startswith(("http://", "https://")):
            return MCPToolResult.error("Only http:// and https:// URLs are supported")

        if not await asyncio.to_thread(is_safe_url_for_request, url):
            return MCPToolResult.error("URL is not publicly reachable from this server")

        try:
            import aiohttp
        except ImportError:
            return MCPToolResult.error(
                "aiohttp is required for WebFetchConnector. "
                "Install it with: pip install aiohttp"
            )

        headers = {"User-Agent": self._user_agent}
        try:
            MAX_REDIRECTS = 5
            current_url = url
            request_timeout = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(headers=headers) as session:
                for _hop in range(MAX_REDIRECTS + 1):
                    if not await asyncio.to_thread(
                        is_safe_url_for_request, current_url
                    ):
                        return MCPToolResult.error(
                            "Redirect target is not publicly reachable from this server"
                        )
                    async with session.get(
                        current_url,
                        timeout=request_timeout,
                        allow_redirects=False,
                    ) as response:
                        if response.status in (301, 302, 303, 307, 308):
                            location = response.headers.get("Location", "")
                            if not location:
                                return MCPToolResult.error(
                                    "Redirect response missing Location header"
                                )
                            current_url = urllib.parse.urljoin(current_url, location)
                            continue
                        content_type = response.headers.get("Content-Type", "")
                        if response.status >= 400:
                            return MCPToolResult.error(
                                f"HTTP request failed (status {response.status})"
                            )
                        raw = await response.read()
                        if len(raw) > self._max_bytes:
                            raw = raw[: self._max_bytes]
                            truncated = True
                        else:
                            truncated = False

                        text = _decode_content(raw, content_type)
                        if truncated:
                            text += (
                                f"\n\n[Content truncated at {self._max_bytes} bytes]"
                            )
                        return MCPToolResult.text(text)
                return MCPToolResult.error("Too many redirects")
        except TimeoutError:
            return MCPToolResult.error(f"Fetch timed out after {timeout}s")
        except Exception as exc:  # noqa: BLE001 — external HTTP boundary
            error_type = type(exc).__name__
            logger.warning("web_fetch_error", error_type=error_type)
            return MCPToolResult.error(f"Fetch failed ({error_type})")


def _decode_content(raw: bytes, content_type: str) -> str:
    """Decode raw bytes to string, converting HTML when possible."""
    encoding = "utf-8"
    if "charset=" in content_type:
        try:
            encoding = (
                content_type.rsplit("charset=", maxsplit=1)[-1]
                .split(";", maxsplit=1)[0]
                .strip()
            )
        except (IndexError, AttributeError):
            encoding = "utf-8"

    text = raw.decode(encoding, errors="replace")

    if "text/html" in content_type:
        try:
            import html2text  # type: ignore[import-not-found]

            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = True
            text = converter.handle(text)
        except ImportError:
            text = (
                "[HTML content — install html2text for Markdown conversion]\n\n" + text
            )

    return text


__all__ = ["WebFetchConnector"]
