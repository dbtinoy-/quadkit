"""AgentAsToolAdapter — wraps any agent as a ToolProtocol.

Enables hierarchical multi-agent delegation by exposing an agent as
a tool that other agents can invoke through their normal tool-calling
reasoning loop. The supervisor agent sees delegated agents as tools
with descriptive names and schemas, and the adapter transparently
routes execution through the ``AgentExecutorProtocol``.

Example::

    from quadkit.ai.agents.delegation import AgentAsToolAdapter

    billing_tool = AgentAsToolAdapter(
        agent=billing_agent,
        executor=executor,
    )
    # Use as any other tool in a supervisor's tool list
    supervisor = Agent(
        name="supervisor",
        tools=[billing_tool, technical_tool],
        strategy=ReActStrategy(),
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.contracts.ai.agents import (
        AgentExecutorProtocol,
        AgentProtocol,
    )

logger = get_logger(__name__)

_DESCRIPTION_MAX_CHARS = 200


class AgentAsToolAdapter:
    """Wraps an ``AgentProtocol`` as a ``ToolProtocol``.

    The adapter satisfies the ``ToolProtocol`` contract so that any
    agent can be injected into another agent's tool list. When
    ``execute()`` is called, the adapter delegates to the provided
    ``AgentExecutorProtocol.run()`` with the given message.

    Attributes:
        name: ``delegate_to_{agent.name}``  — uniquely identifies this
            delegation tool.
        description: Derived from the wrapped agent's system prompt,
            truncated to ``_DESCRIPTION_MAX_CHARS``.
        parameters_schema: Accepts a single ``message`` string.
    """

    def __init__(
        self,
        agent: AgentProtocol,
        executor: AgentExecutorProtocol,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Initialize the agent-to-tool adapter.

        Args:
            agent: The agent to expose as a tool.
            executor: The executor used to run the agent.
            session_id: Optional session ID to pass through to the executor.
            user_id: Optional user ID for governance tracking.
        """
        self._agent = agent
        self._executor = executor
        self._session_id = session_id
        self._user_id = user_id

    @property
    def name(self) -> str:
        """Unique tool identifier derived from the wrapped agent name."""
        return f"delegate_to_{self._agent.name}"

    @property
    def description(self) -> str:
        """Human-readable description for LLM tool selection."""
        prompt = self._agent.system_prompt or ""
        truncated = prompt[:_DESCRIPTION_MAX_CHARS]
        if len(prompt) > _DESCRIPTION_MAX_CHARS:
            truncated += "…"
        return f"Delegate task to '{self._agent.name}': {truncated}"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema for the delegation tool parameters."""
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": (
                        f"The task or question to delegate to the "
                        f"'{self._agent.name}' agent."
                    ),
                },
            },
            "required": ["message"],
        }

    async def execute(self, **kwargs: Any) -> Any:
        """Execute by delegating to the wrapped agent.

        Args:
            **kwargs: Must contain ``message`` (str) — the task to delegate.

        Returns:
            The agent's response message string on success, or an error
            description string on failure.
        """
        message = kwargs.get("message", "")
        if not message:
            return "Error: No message provided for delegation."

        logger.info(
            "agent_delegation_start",
            from_tool=self.name,
            to_agent=self._agent.name,
            message_length=len(message),
        )

        result = await self._executor.run(
            agent=self._agent,
            message=message,
            session_id=self._session_id,
            user_id=self._user_id,
        )

        if result.is_ok():
            response = result.unwrap()
            logger.info(
                "agent_delegation_complete",
                to_agent=self._agent.name,
                steps=response.step_count,
                tokens=response.total_tokens,
            )
            return response.message

        error = result.unwrap_err()
        error_type = type(error).__name__
        logger.warning(
            "agent_delegation_failed",
            to_agent=self._agent.name,
            error_type=error_type,
        )
        return f"Delegation to '{self._agent.name}' failed ({error_type})"


__all__ = ["AgentAsToolAdapter"]
