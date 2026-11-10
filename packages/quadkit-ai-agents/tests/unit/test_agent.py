"""Unit tests for quadkit-ai-agents AgentBase class."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from quadkit.ai.agents import AgentBase, tool
from quadkit.ai.agents.exceptions import AgentConfigurationError


class TestAgentBase:
    """Tests for the base AgentBase class."""

    def test_agent_requires_name(self) -> None:
        """Test that AgentBase raises error without name."""

        class UnnamedAgent(AgentBase):
            @property
            def tools(self):
                return []

        with pytest.raises(AgentConfigurationError, match="must have a name"):
            UnnamedAgent()

    def test_agent_requires_tools_property(self) -> None:
        """Test that AgentBase raises error without tools property."""

        class NoToolsAgent(AgentBase):
            name = "test_agent"

        with pytest.raises(AgentConfigurationError, match="must define tools"):
            NoToolsAgent()

    def test_agent_valid_configuration(self) -> None:
        """Test AgentBase accepts valid configuration."""

        @tool
        async def dummy_tool() -> None:
            """A dummy tool."""
            pass

        class ValidAgent(AgentBase):
            name = "valid_agent"
            system_prompt = "You are a helpful assistant."

            @property
            def tools(self):
                return [dummy_tool]

        agent = ValidAgent()
        assert agent.name == "valid_agent"
        assert agent.system_prompt == "You are a helpful assistant."
        assert len(agent.tools) == 1

    def test_agent_repr(self) -> None:
        """Test AgentBase string representation."""

        @tool
        async def my_tool() -> None:
            """A tool."""
            pass

        class MyAgent(AgentBase):
            name = "my_agent"

            @property
            def tools(self):
                return [my_tool]

        agent = MyAgent()
        assert "my_agent" in repr(agent)
        assert "1" in repr(agent)  # 1 tool

    def test_agent_system_prompt_default(self) -> None:
        """Test AgentBase has empty system prompt by default."""

        @tool
        async def tool_a() -> None:
            pass

        class MinimalAgent(AgentBase):
            name = "minimal"

            @property
            def tools(self):
                return [tool_a]

        agent = MinimalAgent()
        assert agent.system_prompt == ""


class TestAgentWithTools:
    """Tests for AgentBase with various tool configurations."""

    def test_agent_with_no_tools(self) -> None:
        """Test AgentBase with empty tools list."""

        class EmptyAgent(AgentBase):
            name = "empty_agent"

            @property
            def tools(self):
                return []

        agent = EmptyAgent()
        assert len(agent.tools) == 0

    def test_agent_with_multiple_tools(self) -> None:
        """Test AgentBase with multiple tools."""

        @tool
        async def search(query: str) -> list:
            """Search."""
            return []

        @tool
        async def save(data: dict) -> None:
            """Save data."""
            pass

        @tool
        async def delete(item_id: str) -> bool:
            """Delete item."""
            return True

        class MultiToolAgent(AgentBase):
            name = "multi_tool"

            @property
            def tools(self):
                return [search, save, delete]

        agent = MultiToolAgent()
        assert len(agent.tools) == 3
        tool_names = [t.name for t in agent.tools]
        assert "search" in tool_names
        assert "save" in tool_names
        assert "delete" in tool_names


class TestAgentSubclass:
    """Tests demonstrating proper AgentBase subclassing."""

    def test_order_support_agent(self) -> None:
        """Test example: Order support agent."""

        @tool
        async def lookup_order(order_id: str) -> dict:
            """Look up an order by its ID."""
            return {"order_id": order_id, "status": "shipped"}

        @tool
        async def cancel_order(order_id: str, reason: str) -> dict:
            """Cancel an order."""
            return {"order_id": order_id, "status": "cancelled", "reason": reason}

        class OrderAgent(AgentBase):
            name = "order_support"
            system_prompt = (
                "You are a helpful order support agent. "
                "Use available tools to help customers with their orders."
            )

            @property
            def tools(self):
                return [lookup_order, cancel_order]

        agent = OrderAgent()
        assert agent.name == "order_support"
        assert "order support" in agent.system_prompt.lower()
        assert len(agent.tools) == 2

    def test_agent_inherits_tools_from_parent(self) -> None:
        """Test that agent tools can be inherited."""

        @tool
        async def base_tool() -> None:
            """Base tool."""
            pass

        class BaseAgent(AgentBase):
            name = "base"

            @property
            def tools(self):
                return [base_tool]

        class ExtendedAgent(BaseAgent):
            @property
            def tools(self):
                return [*super().tools]

        agent = ExtendedAgent()
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "base_tool"


class TestAgentValidation:
    """Tests for AgentBase configuration validation."""

    def test_name_must_be_non_empty_string(self) -> None:
        """Test that empty name raises error."""

        class EmptyNameAgent(AgentBase):
            name = ""

            @property
            def tools(self):
                return []

        with pytest.raises(AgentConfigurationError):
            EmptyNameAgent()

    def test_tools_must_be_list(self) -> None:
        """Test that tools must be a list, not a single item."""

        @tool
        async def single_tool() -> None:
            pass

        class WrongToolsAgent(AgentBase):
            name = "wrong_tools"
            # This should be a list but is returning a single item
            @property
            def tools(self):
                return single_tool

        with pytest.raises(AgentConfigurationError):
            WrongToolsAgent()

    def test_tools_property_must_be_property(self) -> None:
        """Test that tools must be a property, not a regular attribute."""

        class NotAPropertyAgent(AgentBase):
            name = "not_property"
            tools = []  # This should be a property

        with pytest.raises(AgentConfigurationError):
            NotAPropertyAgent()
