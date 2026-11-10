"""Convention followed: **Provider lifecycle** — ``register()`` binds the
``MCPController``, ``MCPAuthorizerProtocol``, and HTTP controller class;
``boot()`` resolves ``MCPServer`` created by ``MCPModule`` and wires
``MCPBridgeService``.
"""

from __future__ import annotations

from mcp_side.config import McpSideConfig
from mcp_side.controllers.api import MCPBridgeController
from mcp_side.mcp.runbooks import AllowBridgeAuthorizer, RunbookMCPController
from mcp_side.services.bridge import MCPBridgeService
from quadkit.ai.mcp import MCPServer
from quadkit.contracts import ProviderPriority
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.mcp.protocols import MCPAuthorizerProtocol
from quadkit.di.provider import Provider


class McpSideProvider(Provider):
    """Wire the MCP controller, authorizer, and HTTP bridge service."""

    name = "mcp_side"
    priority = ProviderPriority.PRESENTATION
    config_key: str | None = "mcp_side"
    config_model: type | None = McpSideConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config
            if isinstance(self.config, McpSideConfig)
            else McpSideConfig()
        )
        container.singleton(McpSideConfig, config)
        container.singleton(RunbookMCPController, RunbookMCPController())
        container.singleton(
            MCPAuthorizerProtocol,
            AllowBridgeAuthorizer(expected_client=config.client_name),
        )
        container.singleton(MCPBridgeController, MCPBridgeController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        config = await container.resolve(McpSideConfig)
        server = await container.resolve(MCPServer)
        service = MCPBridgeService(server=server, client_name=config.client_name)
        container.bind(MCPBridgeController, MCPBridgeController(service=service))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        _ = timeout
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"demo": "mcp-server"},
        )


__all__ = ["McpSideProvider"]
