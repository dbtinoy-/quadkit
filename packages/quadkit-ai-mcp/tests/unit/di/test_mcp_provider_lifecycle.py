"""Lifecycle-focused tests for MCPProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.ai.mcp.config import MCPConfig
from quadkit.ai.mcp.di.provider import MCPProvider
from quadkit.ai.mcp.server.core import MCPServer
from quadkit.ai.mcp.server.handlers import (
    LoggingHandler,
    PromptHandler,
    ResourceHandler,
    SamplingHandler,
    ToolHandler,
)
from quadkit.ai.mcp.transport import SSETransport, StdioTransport
from quadkit.contracts.mcp.protocols import MCPAuthorizerProtocol


class _ContainerStub:
    def __init__(self) -> None:
        self.bindings: dict[type, object] = {}

    def singleton(self, service_type: type, instance: object) -> None:
        self.bindings[service_type] = instance

    async def resolve(self, service_type: type) -> object:
        return self.bindings[service_type]

    async def resolve_optional(self, service_type: type) -> object | None:
        return self.bindings.get(service_type)


@pytest.mark.asyncio
async def test_shutdown_stops_managed_transports_and_disconnects_client() -> None:
    """shutdown() should stop transports and disconnect the managed MCP client."""
    provider = MCPProvider()

    transport_a = AsyncMock()
    transport_b = AsyncMock()
    client = AsyncMock()

    provider._managed_transports = [transport_a, transport_b]
    provider._managed_client = client

    await provider.shutdown()

    transport_a.stop.assert_awaited_once()
    transport_b.stop.assert_awaited_once()
    client.disconnect.assert_awaited_once()


def test_boot_transports_registers_concrete_transport_instances() -> None:
    """_boot_transports() should bind each concrete transport type correctly."""
    provider = MCPProvider(config=MCPConfig(stdio_mode=False))
    container = _ContainerStub()

    provider._boot_transports(container)

    assert isinstance(container.bindings[SSETransport], SSETransport)
    assert isinstance(container.bindings[StdioTransport], StdioTransport)


def _handler_stubs() -> dict[type, object]:
    return {
        ToolHandler: AsyncMock(),
        ResourceHandler: AsyncMock(),
        PromptHandler: AsyncMock(),
        SamplingHandler: AsyncMock(),
        LoggingHandler: AsyncMock(),
    }


async def _boot_server_with(
    container: _ContainerStub, config: MCPConfig | None = None
) -> MCPProvider:
    provider = MCPProvider(config=config or MCPConfig())
    container.bindings.update(_handler_stubs())
    await provider._boot_server(container)
    return provider


@pytest.mark.asyncio
async def test_boot_server_threads_bound_authorizer() -> None:
    """_boot_server() should resolve and thread a bound MCPAuthorizerProtocol."""
    container = _ContainerStub()
    sentinel = AsyncMock()
    container.bindings[MCPAuthorizerProtocol] = sentinel

    await _boot_server_with(container)

    server = container.bindings[MCPServer]
    assert isinstance(server, MCPServer)
    assert server._authorizer is sentinel
    assert server._allow_unauthenticated is False


@pytest.mark.asyncio
async def test_boot_server_fail_closed_when_unbound() -> None:
    """_boot_server() without an authorizer stays fail-closed by default."""
    container = _ContainerStub()

    await _boot_server_with(container)

    server = container.bindings[MCPServer]
    assert isinstance(server, MCPServer)
    assert server._authorizer is None
    assert server._allow_unauthenticated is False


@pytest.mark.asyncio
async def test_boot_server_threads_allow_unauthenticated_config() -> None:
    """_boot_server() should thread MCPConfig.allow_unauthenticated."""
    container = _ContainerStub()

    provider = await _boot_server_with(
        container, config=MCPConfig(allow_unauthenticated=True)
    )
    server = container.bindings[MCPServer]
    assert isinstance(server, MCPServer)
    assert server._allow_unauthenticated is True
    assert provider is not None
