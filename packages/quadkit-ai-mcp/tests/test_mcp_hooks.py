"""Tests for MCP hooks."""

from __future__ import annotations

import pytest


class TestMCPServerStartedHook:
    """Tests for MCPServerStartedHook."""

    def test_creation(self) -> None:
        from quadkit.ai.mcp.hooks import MCPServerStartedHook

        hook = MCPServerStartedHook(transport="stdio")
        assert hook.transport == "stdio"

    def test_frozen(self) -> None:
        from quadkit.ai.mcp.hooks import MCPServerStartedHook

        hook = MCPServerStartedHook(transport="sse")
        with pytest.raises(Exception):
            hook.transport = "changed"

    def test_kw_only(self) -> None:
        from quadkit.ai.mcp.hooks import MCPServerStartedHook

        with pytest.raises(TypeError):
            MCPServerStartedHook("stdio")


class TestMCPServerStoppedHook:
    """Tests for MCPServerStoppedHook."""

    def test_creation(self) -> None:
        from quadkit.ai.mcp.hooks import MCPServerStoppedHook

        hook = MCPServerStoppedHook(transport="stdio")
        assert hook.transport == "stdio"

    def test_frozen(self) -> None:
        from quadkit.ai.mcp.hooks import MCPServerStoppedHook

        hook = MCPServerStoppedHook(transport="sse")
        with pytest.raises(Exception):
            hook.transport = "changed"


class TestMCPToolInvokedHook:
    """Tests for MCPToolInvokedHook."""

    def test_creation(self) -> None:
        from quadkit.ai.mcp.hooks import MCPToolInvokedHook

        hook = MCPToolInvokedHook(tool_name="get_weather")
        assert hook.tool_name == "get_weather"

    def test_frozen(self) -> None:
        from quadkit.ai.mcp.hooks import MCPToolInvokedHook

        hook = MCPToolInvokedHook(tool_name="get_weather")
        with pytest.raises(Exception):
            hook.tool_name = "changed"


class TestHooksExports:
    """Tests for hooks module exports."""

    def test_all_exports(self) -> None:
        from quadkit.ai.mcp import hooks

        expected = ["MCPServerStartedHook", "MCPServerStoppedHook", "MCPToolInvokedHook"]
        for name in expected:
            assert hasattr(hooks, name)