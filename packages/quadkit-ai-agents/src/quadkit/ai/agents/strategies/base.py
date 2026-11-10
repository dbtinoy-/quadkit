"""Base strategy class for agent reasoning strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from quadkit.contracts.ai.agents import StrategyProtocol, ToolProtocol

if TYPE_CHECKING:
    from quadkit.contracts.ai.agents import AgentError, AgentResponse
    from quadkit.contracts.ai.llm import LLMClientProtocol
    from quadkit.result import Result


class AbstractStrategy(ABC, StrategyProtocol):
    """Base class for agent reasoning strategies.

    Strategies implement the reasoning loop that drives an agent's behavior.
    """

    @abstractmethod
    async def execute(
        self,
        message: str,
        tools: list[ToolProtocol],
        history: list[dict[str, Any]],
        llm: LLMClientProtocol,
        **kwargs: Any,
    ) -> Result[AgentResponse, AgentError]:
        """Execute the reasoning strategy.

        Args:
            message: The user's input message.
            tools: Tools available to the agent.
            history: Conversation history as ChatMessage objects.
            llm: LLM client implementing LLMClientProtocol.
            **kwargs: Additional strategy-specific parameters.

        Returns:
            Ok(AgentResponse) on success, Err(AgentError) on failure.
        """
