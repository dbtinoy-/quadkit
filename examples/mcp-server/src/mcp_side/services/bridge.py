"""Convention followed: **Service layer** — JSON-RPC handshake and protocol
framing live in a service; HTTP controllers stay thin adapters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.exceptions import NotFoundError
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.ai.mcp import MCPServer


class MCPBridgeService:
    """Drive the real ``MCPServer`` through JSON-RPC 2.0 messages."""

    def __init__(self, *, server: MCPServer, client_name: str) -> None:
        self._server = server
        self._client_name = client_name
        self._initialized = False
        self._next_id = 1

    async def ensure_initialized(self) -> None:
        """Run the MCP ``initialize`` + ``notifications/initialized`` handshake."""
        if self._initialized:
            return
        await self._server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": self._client_name, "version": "0.1.0"},
                    "capabilities": {},
                },
            }
        )
        await self._server.handle_message(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        self._initialized = True

    async def dispatch_rpc(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Forward a JSON-RPC 2.0 payload to ``MCPServer.handle_message``."""
        await self.ensure_initialized()
        return await self._server.handle_message(payload)

    async def capabilities(self) -> dict[str, Any]:
        """Collect registered tools, resource templates, and prompts via MCP."""
        tools_resp = await self._call("tools/list", {})
        templates_resp = await self._call("resources/templates/list", {})
        prompts_resp = await self._call("prompts/list", {})
        return {
            "tools": tools_resp.get("result", {}).get("tools", []),
            "resource_templates": templates_resp.get("result", {}).get(
                "resourceTemplates", []
            ),
            "prompts": prompts_resp.get("result", {}).get("prompts", []),
        }

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> Result[dict[str, Any], NotFoundError]:
        """Invoke a named MCP tool and translate unknown-tool errors to ``Result``."""
        caps = await self.capabilities()
        known = {t["name"] for t in caps["tools"]}
        if name not in known:
            return Err(NotFoundError(resource_type="mcp_tool", resource_id=name))
        response = await self._call(
            "tools/call", {"name": name, "arguments": arguments}
        )
        return Ok({"tool": name, "result": response.get("result")})

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        await self.ensure_initialized()
        req_id = self._next_id
        self._next_id += 1
        response = await self._server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            }
        )
        return response or {}


__all__ = ["MCPBridgeService"]
