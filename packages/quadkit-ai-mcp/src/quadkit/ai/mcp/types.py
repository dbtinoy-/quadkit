"""MCP type definitions — data structures for the MCP protocol.

These dataclasses map directly to the MCP (Model Context Protocol) format.
They provide serialization to the JSON format expected by MCP clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPToolDefinition:
    """MCP tool definition sent to clients during tools/list.

    Maps directly to the MCP tool schema format.
    """

    name: str
    """Unique tool identifier."""

    description: str = ""
    """Human-readable description shown to the AI client."""

    input_schema: dict[str, Any] = field(default_factory=dict)
    """JSON Schema describing the tool's parameters."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MCP protocol format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class MCPToolResult:
    """Result of an MCP tool call returned to the client."""

    content: list[dict[str, Any]] = field(default_factory=list)
    """Content items (text, image, etc.)."""

    is_error: bool = False
    """Whether the tool call resulted in an error."""

    @staticmethod
    def text(text: str, is_error: bool = False) -> MCPToolResult:
        """Create a text result."""
        return MCPToolResult(
            content=[{"type": "text", "text": text}],
            is_error=is_error,
        )

    @staticmethod
    def error(message: str) -> MCPToolResult:
        """Create an error result."""
        return MCPToolResult(
            content=[{"type": "text", "text": message}],
            is_error=True,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MCP protocol format."""
        return {
            "content": self.content,
            "isError": self.is_error,
        }


@dataclass
class MCPResource:
    """An MCP resource that clients can browse and read."""

    uri: str
    """Unique resource identifier (URI)."""

    name: str
    """Human-readable resource name."""

    description: str = ""
    """Resource description."""

    mime_type: str = "text/plain"
    """MIME type of the resource content."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MCP protocol format."""
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


@dataclass
class MCPResourceContent:
    """Content of an MCP resource returned to the client."""

    uri: str
    """Resource URI."""

    mime_type: str = "text/plain"
    """Content MIME type."""

    text: str | None = None
    """Text content (for text-based resources)."""

    blob: str | None = None
    """Base64-encoded binary content."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MCP protocol format."""
        result: dict[str, Any] = {
            "uri": self.uri,
            "mimeType": self.mime_type,
        }
        if self.text is not None:
            result["text"] = self.text
        if self.blob is not None:
            result["blob"] = self.blob
        return result


@dataclass
class MCPPrompt:
    """An MCP prompt template that clients can use."""

    name: str
    """Unique prompt identifier."""

    description: str = ""
    """Prompt description."""

    arguments: list[dict[str, Any]] = field(default_factory=list)
    """Prompt arguments (name, description, required)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MCP protocol format."""
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
        }


@dataclass
class MCPPromptMessage:
    """A message in an MCP prompt response."""

    role: str
    """Message role (user, assistant, system)."""

    content: dict[str, Any] = field(default_factory=dict)
    """Message content (type + text/image/etc.)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MCP protocol format."""
        return {
            "role": self.role,
            "content": self.content,
        }


@dataclass
class MCPServerCapabilities:
    """Server capabilities sent during initialization."""

    tools: bool = True
    """Whether the server provides tools."""

    resources: bool = False
    """Whether the server provides resources."""

    prompts: bool = False
    """Whether the server provides prompts."""

    logging: bool = False
    """Whether the server supports the logging capability."""

    sampling: bool = False
    """Whether the server supports the sampling/createMessage capability."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MCP protocol format."""
        caps: dict[str, Any] = {}
        if self.tools:
            caps["tools"] = {}
        if self.resources:
            caps["resources"] = {}
        if self.prompts:
            caps["prompts"] = {}
        if self.logging:
            caps["logging"] = {}
        if self.sampling:
            caps["sampling"] = {}
        return caps


@dataclass
class MCPServerInfo:
    """Server metadata sent during initialization."""

    name: str = "the optional provider"
    """Server name."""

    version: str = "1.0.0"
    """Server version."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MCP protocol format."""
        return {
            "name": self.name,
            "version": self.version,
        }


@dataclass
class MCPInitializeResult:
    """Result of the initialize method."""

    protocol_version: str = "2024-11-05"
    """MCP protocol version."""

    capabilities: MCPServerCapabilities = field(
        default_factory=MCPServerCapabilities,
    )
    """Server capabilities."""

    server_info: MCPServerInfo = field(default_factory=MCPServerInfo)
    """Server information."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MCP protocol format."""
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": self.capabilities.to_dict(),
            "serverInfo": self.server_info.to_dict(),
        }


@dataclass
class MCPJSONRPCRequest:
    """JSON-RPC request message."""

    jsonrpc: str = "2.0"
    """JSON-RPC version."""

    id: int | str | None = None
    """Request identifier."""

    method: str = ""
    """Method name to invoke."""

    params: dict[str, Any] | None = None
    """Method parameters."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-RPC format."""
        result: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
        }
        if self.id is not None:
            result["id"] = self.id
        if self.params is not None:
            result["params"] = self.params
        return result


@dataclass
class MCPJSONRPCResponse:
    """JSON-RPC response message."""

    jsonrpc: str = "2.0"
    """JSON-RPC version."""

    id: int | str | None = None
    """Request identifier this response is for."""

    result: dict[str, Any] | None = None
    """Success result (if not error)."""

    error: dict[str, Any] | None = None
    """Error object (if error occurred)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-RPC format."""
        result: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
        }
        if self.id is not None:
            result["id"] = self.id

        # We must return either error or result
        if self.error is not None:
            result["error"] = self.error
        else:
            result["result"] = self.result if self.result is not None else {}

        return result

    @staticmethod
    def create_success(
        result: dict[str, Any],
        request_id: int | str | None = None,
    ) -> MCPJSONRPCResponse:
        """Create a success response."""
        return MCPJSONRPCResponse(
            id=request_id,
            result=result,
        )

    # the method was formerly "success" but since that's not a field we can alias it
    success = create_success

    @staticmethod
    def create_error(
        code: int,
        message: str,
        request_id: int | str | None = None,
        data: Any | None = None,
    ) -> MCPJSONRPCResponse:
        """Create an error response."""
        error_obj: dict[str, Any] = {
            "code": code,
            "message": message,
        }
        if data is not None:
            error_obj["data"] = data
        return MCPJSONRPCResponse(
            id=request_id,
            error=error_obj,
        )
