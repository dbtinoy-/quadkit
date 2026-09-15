"""Agent protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.module import CompiledModuleGraphProtocol
    from quadkit.contracts.core.result import Result

from quadkit.contracts.ai.agents.exceptions import ToolError


@runtime_checkable
class ToolProtocol(Protocol):
    """Protocol for agent tools.

    Tools are the atomic capabilities an agent can invoke during
    reasoning.  Each tool has a name, description, JSON parameter
    schema (for LLM function calling), and an async execute method.

    Satisfied by:
    - @tool decorated functions (FunctionTool)
    - Classes extending Tool base class
    """

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description for the LLM."""
        ...

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema describing the tool's parameters.

        Auto-generated from type hints by the @tool decorator,
        or manually defined for class-based tools.

        Format follows OpenAI function calling schema::

            {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "reason": {"type": "string"}
                },
                "required": ["order_id"]
            }
        """
        ...

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the given arguments.

        Returns the tool's result.  Errors should be raised as
        exceptions — the executor wraps them in Result.
        """
        ...


@runtime_checkable
class AgentProtocol(Protocol):
    """Protocol for AI agents.

    An agent declares its identity, capabilities (tools), and
    persona (system prompt).  The AgentExecutor uses this
    protocol to drive the reasoning loop.
    """

    @property
    def name(self) -> str:
        """Unique agent identifier."""
        ...

    @property
    def tools(self) -> list[ToolProtocol]:
        """Tools available to this agent."""
        ...

    @property
    def system_prompt(self) -> str:
        """System prompt defining the agent's persona and constraints."""
        ...


@runtime_checkable
class StrategyProtocol(Protocol):
    """Protocol for agent reasoning strategies.

    A strategy implements the reasoning loop that drives an agent's
    behavior.  Built-in strategies: ReActStrategy (reason → act →
    observe) and PlanAndExecuteStrategy (plan → execute steps).
    """

    async def execute(
        self,
        message: str,
        tools: list[ToolProtocol],
        history: list[dict[str, Any]],
        llm: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute the reasoning strategy.

        Args:
            message: The user's input message.
            tools: Tools available to the agent.
            history: Conversation history as list of message dicts.
            llm: LLM client for reasoning.
            **kwargs: Additional strategy-specific parameters
                (system_prompt, temperature, tool_registry, etc.)

        Returns:
            Result[AgentResponse, Exception]
        """
        ...


@runtime_checkable
class AgentExecutorProtocol(Protocol):
    """Protocol for agent execution engines.

    The executor runs an agent with governance checks, memory
    management, and observability integration.
    """

    async def run(
        self,
        agent: AgentProtocol,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute an agent and return the response.

        Returns Result[AgentResponse, AgentError].
        """
        ...

    async def astream(
        self,
        agent: AgentProtocol,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Stream agent execution events.

        Yields AgentEvent objects as the agent executes, enabling
        real-time monitoring of thoughts, tool calls, and messages.

        Args:
            agent: The agent to execute.
            message: User's input message.
            session_id: Session ID for multi-turn memory.
            user_id: User ID for governance tracking.
            **kwargs: Additional parameters passed to the strategy.

        Yields:
            AgentEvent objects with type, data, and run_id.
        """
        ...


@runtime_checkable
class ToolRegistryProtocol(Protocol):
    """Protocol for tool registries.

    A registry stores tools by name and provides execution with
    error handling.  When module visibility is enabled, tool access
    is checked against the compiled module graph.
    """

    def register(
        self,
        tool: ToolProtocol,
        module_class: type | None = None,
    ) -> None:
        """Register a tool."""
        ...

    def get(self, name: str) -> ToolProtocol | None:
        """Get a tool by name."""
        ...

    def list_tools(self) -> list[ToolProtocol]:
        """List all registered tools."""
        ...

    def list_visible_tools(self) -> list[ToolProtocol]:
        """List tools visible to the current caller module."""
        ...

    def list_visible_tool_names(self) -> list[str]:
        """List names of tools visible to the current caller module."""
        ...

    def set_module_graph(self, graph: CompiledModuleGraphProtocol | None) -> None:
        """Set the compiled module graph for visibility enforcement."""
        ...

    def set_caller_module(self, module_class: type | None) -> None:
        """Set the calling module for visibility checks."""
        ...

    async def execute(
        self,
        name: str,
        **kwargs: Any,
    ) -> Result[Any, ToolError]:
        """Execute a tool by name.

        Returns Result[Any, ToolError].
        """
        ...


@runtime_checkable
class MemoryProtocol(Protocol):
    """Protocol for conversation memory."""

    async def add_message(self, message: Any) -> None:
        """Add a message to memory.

        Args:
            message: Message to add.
        """
        ...

    async def get_messages(self) -> list[Any]:
        """Get all messages from memory.

        Returns:
            List of messages.
        """
        ...

    async def clear(self) -> None:
        """Clear all messages from memory."""
        ...


@runtime_checkable
class AgentStrategyProtocol(Protocol):
    """Protocol for pluggable agent reasoning strategies.

    Implementations encode a particular reasoning loop (ReAct,
    Plan-and-Execute, Chain-of-Thought, Reflexion, etc.).
    """

    @property
    def name(self) -> str:
        """Human-readable strategy identifier."""
        ...

    async def run(
        self,
        objective: str,
        context: Any,
    ) -> Any:
        """Execute the reasoning loop for the given objective.

        Args:
            objective: Top-level task description.
            context: Agent execution context (tools, memory, config).

        Returns:
            Strategy-specific result object.
        """
        ...


@runtime_checkable
class SkillComposerProtocol(Protocol):
    """Protocol for composing multiple skills or tools into a pipeline."""

    async def get_tools(self) -> list[Any]:
        """Return all tools provided by composed skills."""
        ...


class RunnableAgentProtocol(Protocol):
    """Protocol for runnable agents (G-05 parity)."""

    async def plan(self, input: str) -> str:
        """Plan the next steps."""
        ...

    async def execute(self, plan: str) -> str:
        """Execute the plan."""
        ...
