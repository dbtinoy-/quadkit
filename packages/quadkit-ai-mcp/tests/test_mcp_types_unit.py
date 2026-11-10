"""Unit tests for MCP types."""

from __future__ import annotations

import pytest


class TestMCPToolDefinition:
    """Test MCPToolDefinition dataclass."""

    def test_creation(self) -> None:
        """Verify MCPToolDefinition can be created."""
        from quadkit.ai.mcp.types import MCPToolDefinition

        tool = MCPToolDefinition(
            name="get_weather",
            description="Get weather for a location",
            input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
        )
        assert tool.name == "get_weather"
        assert tool.description == "Get weather for a location"

    def test_to_dict(self) -> None:
        """Verify serialization to MCP format."""
        from quadkit.ai.mcp.types import MCPToolDefinition

        tool = MCPToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
        )
        result = tool.to_dict()
        assert result["name"] == "test_tool"
        assert result["description"] == "A test tool"
        assert result["inputSchema"] == {"type": "object"}


class TestMCPToolResult:
    """Test MCPToolResult dataclass."""

    def test_creation(self) -> None:
        """Verify MCPToolResult can be created."""
        from quadkit.ai.mcp.types import MCPToolResult

        result = MCPToolResult(
            content=[{"type": "text", "text": "Hello"}],
            is_error=False,
        )
        assert len(result.content) == 1
        assert result.is_error is False

    def test_text_factory(self) -> None:
        """Verify text() factory method."""
        from quadkit.ai.mcp.types import MCPToolResult

        result = MCPToolResult.text("Hello world")
        assert result.content[0]["type"] == "text"
        assert result.content[0]["text"] == "Hello world"
        assert result.is_error is False

    def test_error_factory(self) -> None:
        """Verify error() factory method."""
        from quadkit.ai.mcp.types import MCPToolResult

        result = MCPToolResult.error("Something went wrong")
        assert result.is_error is True
        assert "Something went wrong" in result.content[0]["text"]


class TestMCPResource:
    """Test MCPResource dataclass."""

    def test_creation(self) -> None:
        """Verify MCPResource can be created."""
        from quadkit.ai.mcp.types import MCPResource

        resource = MCPResource(
            uri="file:///config.json",
            name="Config File",
            description="Application configuration",
            mime_type="application/json",
        )
        assert resource.uri == "file:///config.json"
        assert resource.mime_type == "application/json"

    def test_to_dict(self) -> None:
        """Verify serialization to MCP format."""
        from quadkit.ai.mcp.types import MCPResource

        resource = MCPResource(
            uri="test://data",
            name="Test Data",
            mime_type="text/plain",
        )
        result = resource.to_dict()
        assert result["uri"] == "test://data"
        assert result["name"] == "Test Data"
        assert result["mimeType"] == "text/plain"


class TestMCPResourceContent:
    """Test MCPResourceContent dataclass."""

    def test_creation_with_text(self) -> None:
        """Verify MCPResourceContent with text content."""
        from quadkit.ai.mcp.types import MCPResourceContent

        content = MCPResourceContent(
            uri="file:///test.txt",
            mime_type="text/plain",
            text="Hello world",
        )
        assert content.text == "Hello world"
        assert content.blob is None

    def test_creation_with_blob(self) -> None:
        """Verify MCPResourceContent with binary content."""
        from quadkit.ai.mcp.types import MCPResourceContent

        content = MCPResourceContent(
            uri="file:///image.png",
            mime_type="image/png",
            blob="base64encodeddata",
        )
        assert content.blob == "base64encodeddata"
        assert content.text is None


class TestMCPServerCapabilities:
    """Test MCPServerCapabilities dataclass."""

    def test_creation_with_defaults(self) -> None:
        """Verify MCPServerCapabilities with default values."""
        from quadkit.ai.mcp.types import MCPServerCapabilities

        caps = MCPServerCapabilities()
        assert caps.tools is True
        assert caps.resources is False
        assert caps.prompts is False

    def test_to_dict_with_all_enabled(self) -> None:
        """Verify serialization with all capabilities enabled."""
        from quadkit.ai.mcp.types import MCPServerCapabilities

        caps = MCPServerCapabilities(
            tools=True,
            resources=True,
            prompts=True,
            logging=True,
            sampling=True,
        )
        result = caps.to_dict()
        assert "tools" in result
        assert "resources" in result
        assert "prompts" in result
        assert "logging" in result
        assert "sampling" in result


class TestMCPJSONRPCRequest:
    """Test MCPJSONRPCRequest dataclass."""

    def test_creation(self) -> None:
        """Verify MCPJSONRPCRequest can be created."""
        from quadkit.ai.mcp.types import MCPJSONRPCRequest

        req = MCPJSONRPCRequest(
            id=1,
            method="tools/list",
            params={},
        )
        assert req.jsonrpc == "2.0"
        assert req.id == 1
        assert req.method == "tools/list"

    def test_to_dict(self) -> None:
        """Verify serialization to JSON-RPC format."""
        from quadkit.ai.mcp.types import MCPJSONRPCRequest

        req = MCPJSONRPCRequest(
            id="abc",
            method="test",
            params={"key": "value"},
        )
        result = req.to_dict()
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == "abc"
        assert result["method"] == "test"
        assert result["params"] == {"key": "value"}


class TestMCPJSONRPCResponse:
    """Test MCPJSONRPCResponse dataclass."""

    def test_create_success(self) -> None:
        """Verify create_success factory."""
        from quadkit.ai.mcp.types import MCPJSONRPCResponse

        resp = MCPJSONRPCResponse.create_success(
            result={"data": "test"},
            request_id=1,
        )
        assert resp.id == 1
        assert resp.result == {"data": "test"}
        assert resp.error is None

    def test_create_error(self) -> None:
        """Verify create_error factory."""
        from quadkit.ai.mcp.types import MCPJSONRPCResponse

        resp = MCPJSONRPCResponse.create_error(
            code=-32600,
            message="Invalid request",
            request_id=2,
        )
        assert resp.id == 2
        assert resp.error is not None
        assert resp.error["code"] == -32600
        assert resp.error["message"] == "Invalid request"


class TestMCPTypesExports:
    """Test that MCP types are properly exported."""

    def test_types_exported(self) -> None:
        """Verify key types are exported from the package."""
        from quadkit.ai.mcp import (
            MCPToolDefinition,
            MCPToolResult,
            MCPResource,
            MCPServerCapabilities,
            MCPJSONRPCRequest,
            MCPToolResult,
        )

        # Verify we can instantiate them
        tool = MCPToolDefinition(name="test")
        result = MCPToolResult.text("test")
        resource = MCPResource(uri="test://a", name="A")
        caps = MCPServerCapabilities()
        req = MCPJSONRPCRequest(method="test")

        assert tool.name == "test"
        assert result.content[0]["text"] == "test"
        assert resource.uri == "test://a"
        assert caps.tools is True
        assert req.method == "test"