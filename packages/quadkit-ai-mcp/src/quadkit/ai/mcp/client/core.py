"""MCPClient — connect to external MCP servers as a client.

Provides a high-level :class:`MCPClient` that handles the MCP JSON-RPC handshake
and exposes ``list_tools()``, ``call_tool()``, ``list_resources()``, and
``list_prompts()`` against any external MCP server.

Two transport implementations are provided:

- :class:`StdioClientTransport` — spawns an external process and communicates
  via its stdin/stdout.  Ideal for locally installed MCP tools (e.g. Claude Desktop
  servers, CLI MCP utilities).
- :class:`SSEClientTransport` — connects to an HTTP+SSE MCP server via POST
  requests.  Requires the ``aiohttp`` package (``pip install aiohttp``).

Example (stdio)::

    from quadkit.ai.mcp.client.core import MCPClient, StdioClientTransport

    transport = StdioClientTransport(["uvx", "mcp-server-git", "--repository", "/repo"])
    async with MCPClient(transport) as client:
        tools = await client.list_tools()
        result = await client.call_tool("git_log", {"max_count": 5})

Example (SSE)::

    from quadkit.ai.mcp.client.core import MCPClient, SSEClientTransport

    transport = SSEClientTransport("http://localhost:8080/mcp")
    async with MCPClient(transport) as client:
        tools = await client.list_tools()
"""

from __future__ import annotations

import asyncio
import itertools
from typing import Any, Self

from quadkit.ai.mcp.client._transports import (
    MCPClientTransport,
    SSEClientTransport,
    StdioClientTransport,
)
from quadkit.ai.mcp.exceptions import (
    MCPInitializationError,
    MCPMethodNotFoundError,
    MCPProtocolError,
    MCPToolCallError,
    MCPTransportError,
)
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

_JSONRPC_VERSION = "2.0"
_MCP_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_NAME = "the optional provider"
_CLIENT_VERSION = "1.0.0"

__all__ = [
    "MCPClient",
    "MCPClientTransport",
    "SSEClientTransport",
    "StdioClientTransport",
]


# ---------------------------------------------------------------------------
# Transport protocol
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# MCPClient
# ---------------------------------------------------------------------------


class MCPClient:
    """Client for connecting to and calling tools on external MCP servers.

    Manages the MCP protocol handshake (``initialize`` / ``initialized``
    notification) and exposes ergonomic methods for the most common MCP
    operations.  The underlying :class:`MCPClientTransport` handles the I/O;
    see :class:`StdioClientTransport` and :class:`SSEClientTransport`.

    Supports async context manager usage for automatic lifecycle management::

        async with MCPClient(transport) as client:
            tools = await client.list_tools()

    Args:
        transport: The transport to use for server communication.
        request_timeout: Per-request wait timeout in seconds.  If a response
            is not received within this window a
            :exc:`~quadkit.ai.mcp.exceptions.MCPTransportError` is raised.
    """

    def __init__(
        self,
        transport: MCPClientTransport,
        *,
        request_timeout: float = 30.0,
    ) -> None:
        self._transport = transport
        self._request_timeout = request_timeout
        self._initialized = False
        self._id_counter = itertools.count(1)
        self._server_info: dict[str, Any] = {}
        self._server_capabilities: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect the transport and perform the MCP `initialize` handshake.

        Raises:
            MCPInitializationError: If the server rejects the handshake.
            MCPTransportError: On transport-level failures.
        """
        try:
            await self._transport.connect()
        except Exception as exc:  # noqa: BLE001 — transport is an external boundary
            raise MCPTransportError(
                message=f"Failed to connect to MCP server ({type(exc).__name__})",
                transport_type="client",
            ) from None
        await self._initialize()

    async def disconnect(self) -> None:
        """Close the transport connection."""
        try:
            await self._transport.disconnect()
        except Exception as exc:  # noqa: BLE001 — transport is an external boundary
            raise MCPTransportError(
                message=f"Failed to disconnect from MCP server ({type(exc).__name__})",
                transport_type="client",
            ) from None
        finally:
            self._initialized = False

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.disconnect()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of tools exposed by the server.

        Returns:
            List of MCP tool definition dicts, each with ``name``,
            ``description``, and ``inputSchema``.
        """
        self._require_initialized()
        response = await self._request("tools/list")
        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPProtocolError(
                message="MCP server returned an invalid tools/list result"
            )
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise MCPProtocolError(message="MCP server returned an invalid tools list")
        return tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Call a tool by name on the server.

        Args:
            name: Tool name as returned by :meth:`list_tools`.
            arguments: Tool input arguments.  Pass ``None`` for tools that
                take no parameters.

        Returns:
            The ``result`` field from the server's JSON-RPC response.

        Raises:
            MCPToolCallError: If the server returns an error for the tool call.
        """
        self._require_initialized()
        response = await self._request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        error = response.get("error")
        if error:
            raise MCPToolCallError(
                message="MCP server returned a tool error",
                tool_name=name,
            )
        return response.get("result")

    async def list_resources(self) -> list[dict[str, Any]]:
        """Return the list of resources exposed by the server.

        Returns:
            List of MCP resource dicts, each with ``uri``, ``name``,
            ``description``, and ``mimeType``.
        """
        self._require_initialized()
        response = await self._request("resources/list")
        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPProtocolError(
                message="MCP server returned an invalid resources/list result"
            )
        resources = result.get("resources", [])
        if not isinstance(resources, list):
            raise MCPProtocolError(
                message="MCP server returned an invalid resource list"
            )
        return resources

    async def list_prompts(self) -> list[dict[str, Any]]:
        """Return the list of prompt templates exposed by the server.

        Returns:
            List of MCP prompt dicts, each with ``name``, ``description``,
            and ``arguments``.
        """
        self._require_initialized()
        response = await self._request("prompts/list")
        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPProtocolError(
                message="MCP server returned an invalid prompts/list result"
            )
        prompts = result.get("prompts", [])
        if not isinstance(prompts, list):
            raise MCPProtocolError(message="MCP server returned an invalid prompt list")
        return prompts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _initialize(self) -> None:
        """Perform the MCP initialize / initialized handshake."""
        response = await self._request(
            "initialize",
            {
                "protocolVersion": _MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": _CLIENT_NAME,
                    "version": _CLIENT_VERSION,
                },
            },
        )
        error = response.get("error")
        if error:
            raise MCPInitializationError(
                message="MCP server rejected initialize",
            )

        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPProtocolError(
                message="MCP server returned an invalid initialize result"
            )
        server_info = result.get("serverInfo", {})
        capabilities = result.get("capabilities", {})
        if not isinstance(server_info, dict) or not isinstance(capabilities, dict):
            raise MCPProtocolError(
                message="MCP server returned invalid initialization metadata"
            )
        self._server_info = server_info
        self._server_capabilities = capabilities

        # Send the required `initialized` notification (no response expected)
        await self._notify("notifications/initialized", {})
        self._initialized = True
        logger.info("mcp_client_initialized")

    def _next_id(self) -> int:
        return next(self._id_counter)

    def _build_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        msg: dict[str, Any] = {
            "jsonrpc": _JSONRPC_VERSION,
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        return msg

    async def _request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the response."""
        message = self._build_request(method, params)
        try:
            await asyncio.wait_for(
                self._transport.send(message),
                timeout=self._request_timeout,
            )
            response: dict[str, Any] = await asyncio.wait_for(
                self._transport.receive(),
                timeout=self._request_timeout,
            )
        except TimeoutError:
            raise MCPTransportError(
                message=f"Request timed out after {self._request_timeout}s",
                transport_type="client",
            ) from None
        except Exception as exc:  # noqa: BLE001 — transport is an external boundary
            raise MCPTransportError(
                message=f"MCP transport request failed ({type(exc).__name__})",
                transport_type="client",
            ) from None

        if not isinstance(response, dict):
            raise MCPProtocolError(message="MCP server returned an invalid response")

        rpc_error = response.get("error")
        if isinstance(rpc_error, dict) and rpc_error.get("code") == -32601:
            raise MCPMethodNotFoundError(
                message=f"Method not found on server: {method}",
            )
        if response.get("jsonrpc") != _JSONRPC_VERSION:
            raise MCPProtocolError(
                message="Unexpected JSON-RPC version in response",
            )
        return response

    async def _notify(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Send a JSON-RPC notification (no ``id`` — no response expected)."""
        message: dict[str, Any] = {
            "jsonrpc": _JSONRPC_VERSION,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        try:
            await self._transport.send(message)
        except Exception as exc:  # noqa: BLE001 — transport is an external boundary
            raise MCPTransportError(
                message=f"MCP transport notification failed ({type(exc).__name__})",
                transport_type="client",
            ) from None

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise MCPInitializationError(
                message=(
                    "MCPClient is not initialized. "
                    "Call connect() or use the async context manager first."
                ),
            )
