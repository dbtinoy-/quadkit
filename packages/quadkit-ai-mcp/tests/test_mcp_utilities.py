"""Additional tests for MCP utilities and features."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestDecoratorsReExports:
    """Tests that decorators are properly re-exported."""

    def test_tool_decorator_re_exported(self) -> None:
        from quadkit.ai.mcp import decorators

        assert hasattr(decorators, "tool")

    def test_resource_decorator_re_exported(self) -> None:
        from quadkit.ai.mcp import decorators

        assert hasattr(decorators, "resource")

    def test_prompt_decorator_re_exported(self) -> None:
        from quadkit.ai.mcp import decorators

        assert hasattr(decorators, "prompt")


class TestModuleConfig:
    """Tests for MCP module configuration."""

    def test_module_importable(self) -> None:
        from quadkit.ai.mcp import module

        assert module is not None


class TestClientModuleExports:
    """Tests for client module exports."""

    def test_mcp_client_class(self) -> None:
        from quadkit.ai.mcp.client import MCPClient

        assert MCPClient is not None

    def test_stdio_transport_class(self) -> None:
        from quadkit.ai.mcp.client import StdioClientTransport

        assert StdioClientTransport is not None

    def test_sse_transport_class(self) -> None:
        from quadkit.ai.mcp.client import SSEClientTransport

        assert SSEClientTransport is not None


class TestServerHostExports:
    """Tests for server host exports."""

    def test_import_host(self) -> None:
        from quadkit.ai.mcp.server import host

        assert host is not None


class TestResourceClasses:
    """Tests for resource classes."""

    def test_import_database_resource(self) -> None:
        from quadkit.ai.mcp.resources import database

        assert database is not None

    def test_import_search_resource(self) -> None:
        from quadkit.ai.mcp.resources import search

        assert search is not None


class TestTransportClasses:
    """Tests for transport classes."""

    def test_import_sse_transport(self) -> None:
        from quadkit.ai.mcp.transport import sse

        assert sse is not None

    def test_import_stdio_transport(self) -> None:
        from quadkit.ai.mcp.transport import stdio

        assert stdio is not None


class TestDIProviders:
    """Tests for DI providers."""

    def test_import_di_provider(self) -> None:
        from quadkit.ai.mcp.di import provider

        assert provider is not None


class TestEventsExports:
    """Tests for events exports."""

    def test_events_module_importable(self) -> None:
        from quadkit.ai.mcp import events

        assert events is not None


class TestControllersExports:
    """Tests for controllers exports."""

    def test_controllers_importable(self) -> None:
        from quadkit.ai.mcp import controllers

        assert controllers is not None


class TestAdaptersReExports:
    """Tests for adapter re-exports."""

    def test_import_tool_adapter(self) -> None:
        from quadkit.ai.mcp.adapters import tool_adapter

        assert tool_adapter is not None


class TestClientExports2:
    """Additional client module tests."""

    def test_client_module_has_core(self) -> None:
        from quadkit.ai.mcp import client

        assert hasattr(client, "core")


class TestServerHandlersExports2:
    """Additional handler export tests."""

    def test_handlers_importable_via_subpackage(self) -> None:
        from quadkit.ai.mcp.server.handlers import tools as tools_handler

        assert tools_handler is not None


class TestTransportProtocol:
    """Additional transport tests."""

    def test_protocol_methods_exist(self) -> None:
        from quadkit.ai.mcp.client._transports import MCPClientTransport

        assert hasattr(MCPClientTransport, "connect")
        assert hasattr(MCPClientTransport, "disconnect")
        assert hasattr(MCPClientTransport, "send")
        assert hasattr(MCPClientTransport, "receive")


class TestServerHandlerProtocols:
    """Tests for handler protocols."""

    def test_tool_handler_class(self) -> None:
        from quadkit.ai.mcp.server.handlers import ToolHandler

        assert ToolHandler is not None