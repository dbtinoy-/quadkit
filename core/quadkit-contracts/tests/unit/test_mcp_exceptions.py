"""Tests for MCP exceptions."""

from __future__ import annotations

import pytest

from quadkit.contracts.mcp.exceptions import (
    MCPError,
    MCPInitializationError,
    MCPMethodNotFoundError,
    MCPPromptError,
    MCPProtocolError,
    MCPResourceError,
    MCPToolCallError,
    MCPTransportError,
)


class TestMCPError:
    """Tests for MCPError base exception."""

    def test_creation(self) -> None:
        """Test creating MCPError."""
        exc = MCPError("Test error")
        assert exc.message == "Test error"
        assert exc._code == "QK_ERR_MCP_001"

    def test_creation_with_details(self) -> None:
        """Test creating MCPError with details."""
        exc = MCPError("Test error", details={"key": "value"})
        assert exc.details["key"] == "value"

    def test_is_quadkit_error(self) -> None:
        """Test MCPError is a QuadkitError."""
        from quadkit.contracts.exceptions.base import QuadkitError

        exc = MCPError("Test")
        assert isinstance(exc, QuadkitError)


class TestMCPTransportError:
    """Tests for MCPTransportError."""

    def test_creation(self) -> None:
        """Test creating MCPTransportError."""
        exc = MCPTransportError("Connection failed")
        assert exc.message == "Connection failed"
        assert exc._code == "QK_ERR_MCP_002"

    def test_creation_with_transport_type(self) -> None:
        """Test creating with transport type."""
        exc = MCPTransportError("Connection failed", transport_type="stdio")
        assert exc.details["transport"] == "stdio"


class TestMCPToolCallError:
    """Tests for MCPToolCallError."""

    def test_creation(self) -> None:
        """Test creating MCPToolCallError."""
        exc = MCPToolCallError("Tool failed")
        assert exc.message == "Tool failed"
        assert exc._code == "QK_ERR_MCP_003"

    def test_creation_with_tool_name(self) -> None:
        """Test creating with tool name."""
        exc = MCPToolCallError("Tool failed", tool_name="my_tool")
        assert exc.details["tool"] == "my_tool"


class TestMCPResourceError:
    """Tests for MCPResourceError."""

    def test_creation(self) -> None:
        """Test creating MCPResourceError."""
        exc = MCPResourceError("Resource not found")
        assert exc.message == "Resource not found"
        assert exc._code == "QK_ERR_MCP_004"

    def test_creation_with_uri(self) -> None:
        """Test creating with URI."""
        exc = MCPResourceError("Resource not found", uri="file:///test.txt")
        assert exc.details["uri"] == "file:///test.txt"


class TestMCPProtocolError:
    """Tests for MCPProtocolError."""

    def test_creation(self) -> None:
        """Test creating MCPProtocolError."""
        exc = MCPProtocolError("Invalid message")
        assert exc.message == "Invalid message"
        assert exc._code == "QK_ERR_MCP_005"

    def test_creation_with_details(self) -> None:
        """Test creating with protocol details."""
        exc = MCPProtocolError("Invalid message", details={"field": "missing"})
        assert exc.details["field"] == "missing"


class TestMCPMethodNotFoundError:
    """Tests for MCPMethodNotFoundError."""

    def test_creation(self) -> None:
        """Test creating MCPMethodNotFoundError."""
        exc = MCPMethodNotFoundError("Unknown method")
        assert exc.message == "Unknown method"
        assert exc._code == "QK_ERR_MCP_006"

    def test_creation_with_method(self) -> None:
        """Test creating with method name."""
        exc = MCPMethodNotFoundError("Unknown method", method="tools/list")
        assert exc.details["method"] == "tools/list"


class TestMCPPromptError:
    """Tests for MCPPromptError."""

    def test_creation(self) -> None:
        """Test creating MCPPromptError."""
        exc = MCPPromptError("Prompt not found")
        assert exc.message == "Prompt not found"
        assert exc._code == "QK_ERR_MCP_007"

    def test_creation_with_prompt_name(self) -> None:
        """Test creating with prompt name."""
        exc = MCPPromptError("Prompt not found", prompt_name="my_prompt")
        assert exc.details["prompt"] == "my_prompt"


class TestMCPInitializationError:
    """Tests for MCPInitializationError."""

    def test_creation(self) -> None:
        """Test creating MCPInitializationError."""
        exc = MCPInitializationError("Init failed")
        assert exc.message == "Init failed"
        assert exc._code == "QK_ERR_MCP_008"

    def test_creation_with_reason(self) -> None:
        """Test creating with reason."""
        exc = MCPInitializationError("Init failed", reason="missing_handler")
        assert exc.details["reason"] == "missing_handler"


class TestMCPExceptionHierarchy:
    """Tests for MCP exception hierarchy."""

    def test_all_mcp_errors_extend_mcp_error(self) -> None:
        """Test all MCP errors extend MCPError."""
        errors = [
            MCPTransportError("test"),
            MCPToolCallError("test"),
            MCPResourceError("test"),
            MCPProtocolError("test"),
            MCPMethodNotFoundError("test"),
            MCPPromptError("test"),
            MCPInitializationError("test"),
        ]
        for exc in errors:
            assert isinstance(exc, MCPError)

    def test_error_codes_are_unique(self) -> None:
        """Test each MCP error has a unique code."""
        codes = set()
        for exc_cls in [
            MCPError,
            MCPTransportError,
            MCPToolCallError,
            MCPResourceError,
            MCPProtocolError,
            MCPMethodNotFoundError,
            MCPPromptError,
            MCPInitializationError,
        ]:
            # Get code from a sample instance
            code = exc_cls("test")._code
            assert code not in codes
            codes.add(code)


class TestMCPExceptionsIntegration:
    """Integration tests for MCP exceptions."""

    def test_can_catch_as_mcp_error(self) -> None:
        """Test can catch specific errors as base MCPError."""
        with pytest.raises(MCPError) as exc_info:
            raise MCPToolCallError("Tool failed", tool_name="test_tool")
        assert "Tool failed" in str(exc_info.value)
        assert exc_info.value.details["tool"] == "test_tool"

    def test_can_raise_transport_error(self) -> None:
        """Test raising transport error with context."""
        with pytest.raises(MCPError) as exc_info:
            raise MCPTransportError("Connection lost", transport_type="http")
        assert exc_info.value._code == "QK_ERR_MCP_002"
        assert exc_info.value.details["transport"] == "http"

    def test_exception_messages_preserved(self) -> None:
        """Test exception messages are preserved through hierarchy."""
        messages = [
            (MCPError, "base error"),
            (MCPTransportError, "transport issue"),
            (MCPToolCallError, "tool issue"),
            (MCPResourceError, "resource issue"),
            (MCPProtocolError, "protocol issue"),
            (MCPMethodNotFoundError, "method issue"),
            (MCPPromptError, "prompt issue"),
            (MCPInitializationError, "init issue"),
        ]
        for exc_cls, msg in messages:
            exc = exc_cls(msg)
            assert exc.message == msg
