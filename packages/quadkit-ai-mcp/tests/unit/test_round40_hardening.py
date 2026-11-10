"""Round 40/43 hardening pins — ai-mcp: failures become responses, never raises.

Round 40 — ToolHandler.call_tool: when the tool provider fails with a
non-builtin driver error type, the call returns Err(MCPToolCallError),
never a raw raise (the MCP protocol needs a response, not a crashed
server).

Round 43 — SearchResourceProvider.read: a malformed ``?limit=`` in the
resource URI must fall back to the default limit instead of escaping
with ValueError (resource reads are "logged, never raised").

Run with: pytest tests/unit/test_round40_hardening.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.mcp.server.handlers.tools import ToolHandler

pytestmark = pytest.mark.unit


class _DriverError(Exception):
    """Stand-in for a tool provider error type (not ValueError/TypeError)."""


class TestToolHandlerCall:
    @pytest.mark.asyncio
    async def test_driver_error_becomes_err(self) -> None:
        provider = MagicMock()
        provider.call_tool = AsyncMock(side_effect=_DriverError("tool backend wedged"))

        handler = ToolHandler(tool_provider=provider)

        result = await handler.call_tool("flaky-tool", {})

        assert result.is_err()


class TestSearchResourceLimitGuard:
    """Round 43 pin — malformed ?limit= falls back, never raises."""

    @pytest.mark.asyncio
    async def test_malformed_limit_falls_back_to_default(self) -> None:
        from quadkit.ai.mcp.resources.search import SearchResourceProvider

        search = MagicMock()
        search.search = AsyncMock(return_value={"hits": []})
        provider = SearchResourceProvider(
            search_engine=search,
            indexes=["products"],  # type: ignore[arg-type]
        )

        out = await provider.read("search://products?q=shoes&limit=abc")

        assert "error" not in out
        search.search.assert_awaited_once()
        _, kwargs = search.search.call_args
        assert kwargs["limit"] == provider._default_limit

    @pytest.mark.asyncio
    async def test_negative_limit_clamped_to_one(self) -> None:
        from quadkit.ai.mcp.resources.search import SearchResourceProvider

        search = MagicMock()
        search.search = AsyncMock(return_value={"hits": []})
        provider = SearchResourceProvider(
            search_engine=search,
            indexes=["products"],  # type: ignore[arg-type]
        )

        await provider.read("search://products?q=shoes&limit=-5")

        search.search.assert_awaited_once()
        _, kwargs = search.search.call_args
        assert kwargs["limit"] == 1
