"""Tests for MCP types additional coverage."""

from __future__ import annotations

import pytest

from quadkit.ai.mcp.types import (
    MCPInitializeResult,
    MCPJSONRPCRequest,
    MCPJSONRPCResponse,
    MCPPrompt,
    MCPPromptMessage,
    MCPResource,
    MCPResourceContent,
    MCPServerCapabilities,
    MCPServerInfo,
    MCPToolDefinition,
    MCPToolResult,
)


class TestMCPToolDefinitionEdgeCases:
    """Tests for edge cases of MCPToolDefinition."""

    def test_with_complex_input_schema(self) -> None:
        tool = MCPToolDefinition(
            name="complex_tool",
            description="A tool with complex schema",
            input_schema={
                "type": "object",
                "properties": {
                    "user": {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["user"],
            },
        )
        assert tool.input_schema["type"] == "object"

    def test_to_dict_includes_all_fields(self) -> None:
        tool = MCPToolDefinition(name="full_tool", description="Full", input_schema={})
        d = tool.to_dict()
        assert "name" in d and "description" in d and "inputSchema" in d


class TestMCPToolResultEdgeCases:
    """Tests for edge cases of MCPToolResult."""

    def test_with_multiple_content_items(self) -> None:
        result = MCPToolResult(
            content=[{"type": "text", "text": "First"}, {"type": "text", "text": "Second"}],
            is_error=False,
        )
        assert len(result.content) == 2

    def test_with_image_content(self) -> None:
        result = MCPToolResult(
            content=[{"type": "image", "data": "base64data", "mimeType": "image/png"}]
        )
        assert result.content[0]["type"] == "image"

    def test_text_with_custom_content_type(self) -> None:
        result = MCPToolResult.text("Hello", is_error=True)
        assert result.is_error is True


class TestMCPResourceEdgeCases:
    """Tests for edge cases of MCPResource."""

    def test_with_all_fields(self) -> None:
        resource = MCPResource(
            uri="file://data.json",
            name="Data File",
            description="JSON data file",
            mime_type="application/json",
        )
        assert resource.uri == "file://data.json"
        assert resource.name == "Data File"

    def test_default_mime_type(self) -> None:
        resource = MCPResource(uri="file://test.txt", name="Test")
        assert resource.mime_type == "text/plain"


class TestMCPResourceContentEdgeCases:
    """Tests for edge cases of MCPResourceContent."""

    def test_with_both_text_and_blob(self) -> None:
        content = MCPResourceContent(
            uri="file://test", mime_type="text/plain", text="Hello", blob="ignored"
        )
        assert content.text is not None
        blob = content.blob

    def test_to_dict_excludes_null_fields(self) -> None:
        content = MCPResourceContent(uri="file://test", mime_type="text/plain")
        d = content.to_dict()
        assert "text" not in d and "blob" not in d


class TestMCPPromptEdgeCases:
    """Tests for edge cases of MCPPrompt."""

    def test_with_arguments(self) -> None:
        prompt = MCPPrompt(
            name="summarize",
            description="Summarizes content",
            arguments=[
                {"name": "max_length", "description": "Maximum length", "required": False},
                {"name": "style", "description": "Writing style", "required": True},
            ],
        )
        assert len(prompt.arguments) == 2


class TestMCPPromptMessageEdgeCases:
    """Tests for edge cases of MCPPromptMessage."""

    def test_with_content_dict(self) -> None:
        msg = MCPPromptMessage(
            role="user", content={"type": "text", "text": "Hello world"}
        )
        assert msg.role == "user"
        assert msg.content["type"] == "text"

    def test_to_dict_includes_all(self) -> None:
        msg = MCPPromptMessage(role="assistant", content={"type": "text", "text": "Hi"})
        d = msg.to_dict()
        assert "role" in d and "content" in d


class TestMCPServerCapabilitiesEdgeCases:
    """Tests for edge cases of MCPServerCapabilities."""

    def test_all_false_by_default(self) -> None:
        caps = MCPServerCapabilities(tools=False, resources=False, prompts=False)
        d = caps.to_dict()
        assert d == {}

    def test_all_true(self) -> None:
        caps = MCPServerCapabilities(tools=True, resources=True, prompts=True, logging=True, sampling=True)
        d = caps.to_dict()
        assert len(d) == 5

    def test_mixed(self) -> None:
        caps = MCPServerCapabilities(tools=True, resources=False, prompts=True)
        d = caps.to_dict()
        assert "tools" in d and "prompts" in d and "resources" not in d


class TestMCPServerInfoEdgeCases:
    """Tests for edge cases of MCPServerInfo."""

    def test_custom_defaults(self) -> None:
        info = MCPServerInfo(name="my-server", version="3.0.0")
        assert info.name == "my-server"
        assert info.version == "3.0.0"

    def test_to_dict_structure(self) -> None:
        info = MCPServerInfo()
        d = info.to_dict()
        assert "name" in d and "version" in d


class TestMCPInitializeResultEdgeCases:
    """Tests for edge cases of MCPInitializeResult."""

    def test_custom_capabilities(self) -> None:
        caps = MCPServerCapabilities(tools=True, resources=True)
        result = MCPInitializeResult(
            protocol_version="2024-11-05",
            capabilities=caps,
            server_info=MCPServerInfo(name="test", version="1.0"),
        )
        assert result.server_info.name == "test"

    def test_to_dict_includes_all(self) -> None:
        result = MCPInitializeResult()
        d = result.to_dict()
        assert "protocolVersion" in d and "capabilities" in d and "serverInfo" in d


class TestMCPJSONRPCRequestEdgeCases:
    """Tests for edge cases of MCPJSONRPCRequest."""

    def test_with_string_id(self) -> None:
        req = MCPJSONRPCRequest(id="abc123", method="test", params={"key": "value"})
        assert req.id == "abc123"

    def test_with_null_params(self) -> None:
        req = MCPJSONRPCRequest(id=1, method="test", params=None)
        d = req.to_dict()
        assert "params" not in d

    def test_with_no_id_for_notification(self) -> None:
        req = MCPJSONRPCRequest(method="notify")
        d = req.to_dict()
        assert "id" not in d


class TestMCPJSONRPCResponseEdgeCases:
    """Tests for edge cases of MCPJSONRPCResponse."""

    def test_create_with_string_id(self) -> None:
        resp = MCPJSONRPCResponse.create_success({"ok": True}, request_id="str_id")
        assert resp.id == "str_id"

    def test_create_error_with_data(self) -> None:
        resp = MCPJSONRPCResponse.create_error(-32600, "Error", request_id=1, data={"extra": "info"})
        assert resp.error is not None
        assert resp.error.get("data") == {"extra": "info"}

    def test_to_dict_with_error(self) -> None:
        resp = MCPJSONRPCResponse(id=1, error={"code": -32600, "message": "Error"})
        d = resp.to_dict()
        assert "error" in d and "result" not in d

    def test_to_dict_with_result_null(self) -> None:
        resp = MCPJSONRPCResponse(id=1, result=None)
        d = resp.to_dict()
        assert "result" in d and d["result"] == {}


class TestTypesModuleImports:
    """Tests for types module imports."""

    def test_import_all_from_package(self) -> None:
        from quadkit.ai.mcp import types as mcp_types
        assert hasattr(mcp_types, "MCPToolDefinition")
        assert hasattr(mcp_types, "MCPToolResult")
        assert hasattr(mcp_types, "MCPResource")
        assert hasattr(mcp_types, "MCPServerCapabilities")