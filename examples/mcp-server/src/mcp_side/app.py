"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the MCP Server demo on ``quadkit-ai-mcp``.
"""

from __future__ import annotations

from mcp_side.controllers.api import MCPBridgeController
from mcp_side.di.provider import McpSideProvider
from mcp_side.mcp.runbooks import RunbookMCPController
from quadkit.ai.mcp import MCPConfig, MCPModule
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Compose ``MCPModule`` and ``WebModule``."""
    mcp_config = MCPConfig(
        server_name="runbook-mcp",
        server_version="0.1.0",
        enable_sse=False,
    )
    return [
        MCPModule.configure(
            config=mcp_config,
            controllers=[RunbookMCPController],
            enable_streaming=False,
        ),
        WebModule.configure(controllers=[MCPBridgeController]),
    ]


def build_providers() -> list[Provider]:
    """Build the DI providers for the MCP Server demo."""
    return [McpSideProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the MCP Server application."""
    app = Application(name="mcp-server", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
