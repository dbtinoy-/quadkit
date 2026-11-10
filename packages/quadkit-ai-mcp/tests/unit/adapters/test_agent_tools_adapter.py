import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.ai.mcp.client.core import MCPClient
from quadkit.ai.mcp.adapters.agent_tools import MCPToolAdapter, register_mcp_tools
from quadkit.contracts.ai.agents import ToolRegistryProtocol
from quadkit.ai.mcp.types import MCPToolResult


@pytest.fixture
def mock_mcp_client() -> AsyncMock:
    client = AsyncMock(spec=MCPClient)
    
    # Setup list_tools
    tool1 = {
        "name": "test_tool",
        "description": "A test tool",
        "inputSchema": {"type": "object", "properties": {"a": {"type": "string"}}},
    }
    client.list_tools.return_value = [tool1]
    
    # Setup call_tool
    result = MCPToolResult(
        is_error=False,
        content=[{"type": "text", "text": "Tool response"}],
    )
    client.call_tool.return_value = result
    
    return client


@pytest.fixture
def mock_registry() -> MagicMock:
    registry = MagicMock(spec=ToolRegistryProtocol)
    return registry


@pytest.mark.asyncio
async def test_mcp_tool_adapter(mock_mcp_client: AsyncMock) -> None:
    """Test MCPToolAdapter execution."""
    adapter = MCPToolAdapter(
        client=mock_mcp_client,
        name="test_tool",
        description="A test tool",
        parameters_schema={"type": "object", "properties": {"a": {"type": "string"}}},
    )
    
    assert adapter.name == "test_tool"
    assert adapter.description == "A test tool"
    assert "a" in adapter.parameters_schema["properties"]
    
    # Test execution
    result = await adapter.execute(a="value")
    
    mock_mcp_client.call_tool.assert_awaited_once_with("test_tool", {"a": "value"})
    assert result == "Tool response"


@pytest.mark.asyncio
async def test_register_mcp_tools(
    mock_mcp_client: AsyncMock,
    mock_registry: MagicMock,
) -> None:
    """Test auto-registration of MCP tools."""
    count = await register_mcp_tools(mock_mcp_client, mock_registry)
    
    mock_mcp_client.list_tools.assert_awaited_once()
    assert count == 1
    
    # Check that registry.register was called
    mock_registry.register.assert_called_once()
    
    # Verify the registered adapter
    registered_adapter = mock_registry.register.call_args[0][0]
    assert isinstance(registered_adapter, MCPToolAdapter)
    assert registered_adapter.name == "test_tool"
