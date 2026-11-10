"""Tests for MCP exceptions."""

from __future__ import annotations

import pytest


class TestMCPExceptions:
    """Tests for MCP exceptions."""

    def test_mcp_error_exists(self) -> None:
        from quadkit.ai.mcp.exceptions import MCPError

        assert MCPError is not None

    def test_mcp_initialization_error_exists(self) -> None:
        from quadkit.ai.mcp.exceptions import MCPInitializationError

        assert MCPInitializationError is not None

    def test_mcp_method_not_found_error_exists(self) -> None:
        from quadkit.ai.mcp.exceptions import MCPMethodNotFoundError

        assert MCPMethodNotFoundError is not None

    def test_mcp_prompt_error_exists(self) -> None:
        from quadkit.ai.mcp.exceptions import MCPPromptError

        assert MCPPromptError is not None

    def test_mcp_protocol_error_exists(self) -> None:
        from quadkit.ai.mcp.exceptions import MCPProtocolError

        assert MCPProtocolError is not None

    def test_mcp_resource_error_exists(self) -> None:
        from quadkit.ai.mcp.exceptions import MCPResourceError

        assert MCPResourceError is not None

    def test_mcp_tool_call_error_exists(self) -> None:
        from quadkit.ai.mcp.exceptions import MCPToolCallError

        assert MCPToolCallError is not None

    def test_mcp_transport_error_exists(self) -> None:
        from quadkit.ai.mcp.exceptions import MCPTransportError

        assert MCPTransportError is not None

    def test_all_exports(self) -> None:
        from quadkit.ai.mcp import exceptions

        expected = [
            "MCPError",
            "MCPInitializationError",
            "MCPMethodNotFoundError",
            "MCPPromptError",
            "MCPProtocolError",
            "MCPResourceError",
            "MCPToolCallError",
            "MCPTransportError",
        ]
        for name in expected:
            assert hasattr(exceptions, name)