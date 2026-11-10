"""Base AgentBase class for creating AI agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.ai.agents.exceptions import AgentConfigurationError
from quadkit.contracts.ai.agents import AgentProtocol, ToolProtocol

if TYPE_CHECKING:
    from quadkit.ai.agents.agent.builder import AgentBuilder
    from quadkit.contracts.ai.agents import MemoryProtocol


class AgentBase(AgentProtocol):
    """Base class for AI agents.

    Agents declare their identity, capabilities (tools), and persona
    (system prompt). The AgentExecutorImpl uses this to drive the reasoning loop.

    An optional ``memory`` object can be attached to give the agent access to
    episodic and semantic memories across conversation turns. When present it is
    passed through to the reasoning strategy so that relevant context can be
    retrieved before each LLM call.

    Example::

        from quadkit.ai.agents import AgentBase, tool

        @tool
        async def lookup_order(order_id: str) -> dict:
            \"\"\"Look up an order by its ID.\"\"\"
            return {"order_id": order_id, "status": "shipped"}

        class OrderAgent(AgentBase):
            name = "order_agent"
            system_prompt = "You are a helpful order support agent."

            @property
            def tools(self):
                return [lookup_order]
    """

    name: str = ""
    """Unique agent identifier. Must be set in subclass."""

    system_prompt: str = ""
    """System prompt defining the agent's persona and constraints."""

    @property
    def tools(self) -> list[ToolProtocol]:
        """Tools available to this agent. Must be implemented in subclass."""
        raise NotImplementedError

    def __init__(self, memory: MemoryProtocol | None = None) -> None:
        """Validate agent configuration and store optional memory.

        Args:
            memory: Optional conversation memory backend. When provided it is
                passed to the reasoning strategy so that relevant past context
                can be retrieved before each LLM call. Defaults to None
                (no memory, backward compatible).
        """
        self._memory: MemoryProtocol | None = memory
        self._validate()

    @property
    def memory(self) -> MemoryProtocol | None:
        """Optional memory backend attached to this agent.

        Returns:
            The memory backend instance, or None if no memory is configured.
        """
        return self._memory

    def _validate(self) -> None:
        """Validate agent configuration."""
        if not self.name:
            raise AgentConfigurationError(
                message="AgentBase must have a name",
                agent_name=self.name,
            )

        # tools must be a property defined by the subclass, not a plain attribute
        # Only check classes that come BEFORE AgentBase in the MRO
        mro = type(self).__mro__
        try:
            agentbase_idx = mro.index(AgentBase)
        except ValueError:
            agentbase_idx = len(mro)
        subclass_mro = mro[:agentbase_idx]

        if not any(
            isinstance(cls.__dict__.get("tools"), property)
            for cls in subclass_mro
            if "tools" in cls.__dict__
        ):
            raise AgentConfigurationError(
                message="AgentBase must define tools as a list property",
                agent_name=self.name,
            )

        try:
            tools_value = self.tools
        except NotImplementedError:
            raise AgentConfigurationError(
                message="AgentBase must define tools as a list property",
                agent_name=self.name,
            ) from None

        if not isinstance(tools_value, list):
            raise AgentConfigurationError(
                message="AgentBase must define tools as a list property",
                agent_name=self.name,
            )

    @classmethod
    def builder(cls, name: str) -> AgentBuilder:
        """Create a fluent builder for constructing an agent.

        Args:
            name: Unique agent identifier.

        Returns:
            An ``AgentBuilder`` instance pre-configured with the given name.
        """
        from quadkit.ai.agents.agent.builder import AgentBuilder

        return AgentBuilder(name)

    def __repr__(self) -> str:
        return f"AgentBase(name={self.name!r}, tools={len(self.tools)})"
