"""Convention followed: **Controller pattern** — thin HTTP adapters returning
plain payloads or ``Result`` values that QuadKit maps to RFC-9457
``ProblemDetail`` responses automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.exceptions import NotFoundError
from quadkit.result import Result
from quadkit.web import Controller, Request, get, post

if TYPE_CHECKING:
    from mcp_side.services.bridge import MCPBridgeService


class MCPBridgeController(Controller):
    """Expose the ``quadkit-ai-mcp`` server over inspectable HTTP endpoints."""

    prefix = "/"

    def __init__(self, service: MCPBridgeService | None = None) -> None:
        self._service = service

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe the MCP Server demo surface."""
        return {
            "demo": "mcp-server",
            "summary": "Model Context Protocol tools, resources, and prompts via quadkit-ai-mcp.",
            "endpoints": [
                "GET /mcp/capabilities",
                "POST /mcp/tools/{name}",
                "POST /mcp/rpc",
            ],
        }

    @get("/mcp/capabilities")
    async def capabilities(self) -> dict[str, Any]:
        """List registered MCP tools, resource templates, and prompts."""
        assert self._service is not None
        return await self._service.capabilities()

    @post("/mcp/tools/{name}")
    async def call_tool(
        self, request: Request, name: str
    ) -> Result[dict[str, Any], NotFoundError]:
        """Call a registered MCP tool by name with a JSON argument object."""
        assert self._service is not None
        body = await request.json() if await request.body() else {}
        arguments = body if isinstance(body, dict) else {}
        return await self._service.call_tool(name, arguments)

    @post("/mcp/rpc")
    async def rpc(self, request: Request) -> dict[str, Any]:
        """Dispatch a raw JSON-RPC 2.0 message to ``MCPServer``."""
        assert self._service is not None
        payload = await request.json()
        response = await self._service.dispatch_rpc(payload)
        return response if response is not None else {"acknowledged": True}


__all__ = ["MCPBridgeController"]
