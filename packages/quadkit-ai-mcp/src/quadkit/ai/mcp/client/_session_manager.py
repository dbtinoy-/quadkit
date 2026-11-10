"""Session-state helpers for the MCP client."""

from __future__ import annotations

from quadkit.ai.mcp.exceptions import MCPInitializationError


def require_initialized(initialized: bool) -> None:
    """Raise when a client has not completed MCP initialization."""
    if not initialized:
        raise MCPInitializationError(
            message=(
                "MCPClient is not initialized. "
                "Call connect() or use the async context manager first."
            ),
        )


def initialize_payload(
    *,
    protocol_version: str,
    client_name: str,
    client_version: str,
) -> dict[str, object]:
    """Build the MCP initialize payload."""
    return {
        "protocolVersion": protocol_version,
        "capabilities": {},
        "clientInfo": {
            "name": client_name,
            "version": client_version,
        },
    }
