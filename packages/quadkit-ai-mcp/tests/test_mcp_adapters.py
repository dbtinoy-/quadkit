"""Tests for MCP adapters."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestToolRegistryAdapter:
    """Tests for ToolRegistryAdapter."""

    def test_constructor(self) -> None:
        from quadkit.ai.mcp.adapters.tool_adapter import ToolRegistryAdapter

        adapter = ToolRegistryAdapter()
        assert adapter._registry is None

    def test_constructor_with_registry(self) -> None:
        from quadkit.ai.mcp.adapters.tool_adapter import ToolRegistryAdapter

        registry = MagicMock()
        adapter = ToolRegistryAdapter(tool_registry=registry)
        assert adapter._registry is registry

    @pytest.mark.asyncio
    async def test_list_tools_no_registry(self) -> None:
        from quadkit.ai.mcp.adapters.tool_adapter import ToolRegistryAdapter

        adapter = ToolRegistryAdapter()
        result = await adapter.list_tools()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_tools_with_registry(self) -> None:
        from quadkit.ai.mcp.adapters.tool_adapter import ToolRegistryAdapter

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.parameters_schema = {"type": "object"}

        registry = MagicMock()
        registry.list_tools = MagicMock(return_value=[mock_tool])
        adapter = ToolRegistryAdapter(tool_registry=registry)
        result = await adapter.list_tools()

        assert len(result) == 1
        assert result[0]["name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_list_tools_error_handling(self) -> None:
        from quadkit.ai.mcp.adapters.tool_adapter import ToolRegistryAdapter

        registry = MagicMock()
        registry.list_tools = MagicMock(side_effect=RuntimeError("error"))
        adapter = ToolRegistryAdapter(tool_registry=registry)
        result = await adapter.list_tools()

        assert result == []

    @pytest.mark.asyncio
    async def test_call_tool_no_registry(self) -> None:
        from quadkit.ai.mcp.adapters.tool_adapter import ToolRegistryAdapter

        adapter = ToolRegistryAdapter()
        with pytest.raises(RuntimeError, match="No tool registry configured"):
            await adapter.call_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self) -> None:
        from quadkit.ai.mcp.adapters.tool_adapter import ToolRegistryAdapter

        registry = MagicMock()
        registry.get = MagicMock(return_value=None)
        adapter = ToolRegistryAdapter(tool_registry=registry)

        with pytest.raises(ValueError, match="Tool not found"):
            await adapter.call_tool("missing_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_success(self) -> None:
        from quadkit.ai.mcp.adapters.tool_adapter import ToolRegistryAdapter

        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="result")

        registry = MagicMock()
        registry.get = MagicMock(return_value=mock_tool)
        adapter = ToolRegistryAdapter(tool_registry=registry)
        result = await adapter.call_tool("test_tool", {"arg": "value"})

        assert result == "result"
        mock_tool.execute.assert_called_once_with(arg="value")


class TestAgentToolsAdapter:
    """Tests for agent tools adapter."""

    def test_importable(self) -> None:
        from quadkit.ai.mcp.adapters import agent_tools

        assert agent_tools is not None


class TestSkillAdapter:
    """Tests for skill adapter."""

    def test_importable(self) -> None:
        from quadkit.ai.mcp.adapters import skill_adapter

        assert skill_adapter is not None


class TestAdapterExports:
    """Tests for adapters module exports."""

    def test_all_exported(self) -> None:
        from quadkit.ai.mcp import adapters

        expected = ["agent_tools", "skill_adapter", "tool_adapter"]
        for name in expected:
            assert hasattr(adapters, name)