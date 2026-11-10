"""MCPServer — JSON-RPC message router for the Model Context Protocol."""

from __future__ import annotations

from typing import Any

from quadkit.ai.mcp.types import (
    MCPServerCapabilities,
    MCPServerInfo,
)
from quadkit.contracts.mcp.protocols import MCPAuthorizerProtocol
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Result

logger = get_logger(__name__)

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

_PRE_INIT_METHODS: frozenset[str] = frozenset(
    {"initialize", "ping", "notifications/initialized"}
)


class MCPServer:
    """Core MCP server — routes JSON-RPC messages to handlers.

    The server is transport-agnostic. It receives parsed JSON-RPC
    messages and returns JSON-RPC responses. The transport layer
    (stdio or HTTP+SSE) handles serialization and I/O.

    Usage::

        server = MCPServer(
            name="my-app",
            tool_handler=tool_handler,
            resource_handler=resource_handler,
        )
        response = await server.handle_message(request)
    """

    def __init__(
        self,
        config: Any | None = None,
        name: str | None = None,
        version: str | None = None,
        tool_handler: Any | None = None,
        resource_handler: Any | None = None,
        prompt_handler: Any | None = None,
        sampling_handler: Any | None = None,
        logging_handler: Any | None = None,
        authorizer: MCPAuthorizerProtocol | None = None,
        allow_unauthenticated: bool = False,
    ) -> None:
        """Initialize the MCP server.

        Args:
            config: Optional MCP server configuration.
            name: Server name (overrides config if provided).
            version: Server version (overrides config if provided).
            tool_handler: Handler for tool-related methods.
            resource_handler: Handler for resource-related methods.
            prompt_handler: Handler for prompt-related methods.
            sampling_handler: Handler for sampling/createMessage (optional).
            logging_handler: Handler for logging/setLevel (optional).
            authorizer: Optional authz hook consulted once per
                non-handshake request post-initialize.  ``None`` means
                requests are denied with ``-32000`` unless
                ``allow_unauthenticated`` is set.
            allow_unauthenticated: When ``True`` (and no ``authorizer``)
                restore the open posture: non-handshake methods dispatch
                without authorization.  Defaults to ``False`` (fail-closed).
        """
        if config is None:
            from quadkit.ai.mcp.config import MCPConfig

            config = MCPConfig()

        self.config = config
        self._name = name or config.server_name
        self._version = version or config.server_version
        self._tool_handler = tool_handler
        self._resource_handler = resource_handler
        self._prompt_handler = prompt_handler
        self._sampling_handler = sampling_handler
        self._logging_handler = logging_handler
        self._authorizer = authorizer
        self._allow_unauthenticated = allow_unauthenticated
        self._initialized = False
        self._client_info: dict[str, Any] = {}

        self._handlers: dict[str, Any] = {}
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register method handlers for MCP protocol methods."""
        self._handlers["initialize"] = self._handle_initialize
        self._handlers["ping"] = self._handle_ping
        self._handlers["notifications/initialized"] = (
            self._handle_initialized_notification
        )

        if self._tool_handler:
            self._handlers["tools/list"] = self._tool_handler.list_tools
            self._handlers["tools/call"] = self._tool_handler.call_tool

        if self._resource_handler:
            self._handlers["resources/list"] = self._resource_handler.list_resources
            self._handlers["resources/read"] = self._resource_handler.read_resource
            self._handlers["resources/templates/list"] = (
                self._resource_handler.list_templates
            )

        if self._prompt_handler:
            self._handlers["prompts/list"] = self._prompt_handler.list_prompts
            self._handlers["prompts/get"] = self._prompt_handler.get_prompt

        if self._sampling_handler:
            self._handlers["sampling/createMessage"] = (
                self._sampling_handler.create_message
            )

        if self._logging_handler:
            self._handlers["logging/setLevel"] = self._logging_handler.set_level

    async def handle_message(
        self,
        message: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Handle a JSON-RPC message and return the response.

        Args:
            message: Parsed JSON-RPC request message.

        Returns:
            JSON-RPC response dict, or None for notifications.
        """
        try:
            # Validate JSON-RPC structure
            if message.get("jsonrpc") != JSONRPC_VERSION:
                return self._error_response(
                    None,
                    -32600,
                    "Invalid JSON-RPC version",
                )

            method = message.get("method")
            if not method:
                return self._error_response(
                    message.get("id"),
                    -32600,
                    "Missing method",
                )

            # Check if it's a notification (no id)
            is_notification = "id" not in message
            request_id = message.get("id")

            # Handle the method
            if method not in self._handlers:
                return self._error_response(
                    request_id,
                    -32601,
                    f"Method not found: {method}",
                )

            handler = self._handlers[method]
            params = message.get("params", {})

            if method not in _PRE_INIT_METHODS:
                if not self._initialized:
                    return self._error_response(
                        request_id, -32002, "Server not initialized"
                    )
                if self._authorizer is not None:
                    allowed = await self._authorizer.authorize(
                        method=method,
                        params=params,
                        client_info=self._client_info,
                    )
                    if not allowed:
                        return self._error_response(
                            request_id, -32000, "Request not authorized"
                        )
                elif not self._allow_unauthenticated:
                    return self._error_response(
                        request_id, -32000, "Request not authorized"
                    )

            try:
                handler_result = await handler(**params) if params else await handler()

                # Handlers may return Result[T, E] (e.g. ToolHandler.call_tool).
                # Unwrap here so the transport layer always receives plain dicts.
                if isinstance(handler_result, Result):
                    if handler_result.is_ok():
                        handler_result = handler_result.unwrap()
                    else:
                        error = handler_result.unwrap_err()
                        logger.error(
                            "mcp_handler_result_error",
                            method=method,
                            error_type=type(error).__name__,
                        )
                        return self._error_response(
                            request_id,
                            -32603,
                            f"Request failed ({type(error).__name__})",
                        )

                result = handler_result

                # Notifications don't get responses
                if is_notification:
                    return None

                return self._success_response(request_id, result)

            except Exception as e:  # noqa: BLE001 — handler failures are logged, never raised
                logger.error(
                    "mcp_handler_error", method=method, error_type=type(e).__name__
                )
                return self._error_response(
                    request_id,
                    -32603,
                    f"Internal error ({type(e).__name__})",
                )

        except Exception as e:  # noqa: BLE001 — message failures are logged, never raised
            logger.error("mcp_message_error", error_type=type(e).__name__)
            return self._error_response(
                message.get("id") if isinstance(message, dict) else None,
                -32603,
                f"Internal error ({type(e).__name__})",
            )

    def _success_response(
        self,
        request_id: int | str | None,
        result: Any,
    ) -> dict[str, Any]:
        """Create a successful JSON-RPC response."""
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "result": result,
        }

    def _error_response(
        self,
        request_id: int | str | None,
        code: int,
        message: str,
    ) -> dict[str, Any]:
        """Create an error JSON-RPC response."""
        error: dict[str, Any] = {
            "code": code,
            "message": message,
        }
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "error": error,
        }

    async def _handle_initialize(
        self,
        **params: Any,
    ) -> dict[str, Any]:
        """Handle the initialize method."""
        # Client can send capabilities in params
        self._client_info = params.get("clientInfo", {})

        logger.info(
            "mcp_initialized",
            client_info=self._client_info,
            server_name=self._name,
        )

        self._initialized = True

        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": MCPServerCapabilities(
                tools=self._tool_handler is not None,
                resources=self._resource_handler is not None,
                prompts=self._prompt_handler is not None,
                logging=self._logging_handler is not None,
                sampling=self._sampling_handler is not None,
            ).to_dict(),
            "serverInfo": MCPServerInfo(
                name=self._name,
                version=self._version,
            ).to_dict(),
        }

    async def _handle_ping(self) -> dict[str, Any]:
        """Handle the ping method."""
        return {}

    async def _handle_initialized_notification(self) -> None:
        """Handle the notifications/initialized notification."""
        logger.info("mcp_client_initialized")


__all__ = ["MCPServer"]
