"""Tests for MCP module modern dynamic-module pattern."""

from __future__ import annotations

from quadkit.ai.mcp.config import MCPConfig
from quadkit.ai.mcp.di.provider import MCPProvider
from quadkit.ai.mcp.exceptions import MCPError, MCPToolCallError, MCPTransportError
from quadkit.ai.mcp.module import MCPModule
from quadkit.ai.mcp.server import MCPServer
from quadkit.di.module import DynamicModule, Module


class _DummyController:
    pass


class _DummyService:
    pass


def test_mcp_module_has_configure() -> None:
    """MCPModule must have configure() classmethod."""
    assert hasattr(MCPModule, "configure")
    assert callable(MCPModule.configure)


def test_mcp_module_configure_returns_dynamic_module() -> None:
    """MCPModule.configure() must return DynamicModule."""
    result = MCPModule.configure()
    assert isinstance(result, DynamicModule)


def test_mcp_module_uses_module_decorator() -> None:
    """MCPModule must use @module() decorator."""
    assert issubclass(MCPModule, Module)


def test_mcp_module_configure_wires_provider_and_exports() -> None:
    """configure() must wire a configured MCPProvider and export MCPServer."""
    config = MCPConfig(server_name="test-mcp")

    result = MCPModule.configure(
        config=config,
        controllers=[_DummyController],
        services=[_DummyService],
        include_methods=["search", "get_*"],
    )

    assert result.module is MCPModule
    assert result.exports == [MCPServer]
    assert len(result.providers) == 1

    provider = result.providers[0]
    assert isinstance(provider, MCPProvider)
    assert provider._config is config
    assert provider._controllers == [_DummyController]
    assert provider._services == [_DummyService]
    assert provider._include_methods == ["search", "get_*"]


def test_mcp_module_from_services_returns_dynamic_module() -> None:
    """from_services() must delegate to configure() and return DynamicModule."""
    result = MCPModule.from_services(
        services=[_DummyService],
        include_methods=["run"],
    )

    assert isinstance(result, DynamicModule)
    assert result.module is MCPModule
    assert len(result.providers) == 1

    provider = result.providers[0]
    assert isinstance(provider, MCPProvider)
    assert provider._services == [_DummyService]
    assert provider._include_methods == ["run"]
