"""Agent construction and the API-facing facade.

This module has two jobs:

1. **Agent assembly** — ``build_support_agent()`` uses the framework's
   ``AgentBuilder`` to declare the agent's name, system prompt, tools,
   and strategy.  The builder produces an ``AgentProtocol`` — a pure
   data object with no I/O.

2. **Facade** — ``SupportAgent`` wraps the executor and agent into a
   single ``ask()`` method that the controller calls.  It records the
   last response for debugging and logs token/timing metadata.

The agent uses the **ReAct** strategy: the LLM emits
``THOUGHT / ACTION / ACTION_INPUT / FINAL_ANSWER`` markers that the
strategy parser drives in a loop, calling tools between steps.
"""

from __future__ import annotations

from quadkit.ai.agents import AgentBuilder
from quadkit.contracts.ai.agents import (
    AgentError,
    AgentExecutorProtocol,
    AgentProtocol,
    AgentResponse,
)
from quadkit.logging import get_logger
from quadkit.result import Result
from support_agent.tools import SUPPORT_TOOLS

logger = get_logger(__name__)


SYSTEM_PROMPT = (
    "You are support-agent, a customer support assistant for an online "
    "store. Use the provided tools to look up orders, compute refunds, "
    "and search the knowledge base before answering. Be precise."
)


def build_support_agent() -> AgentProtocol:
    """Assemble the support-desk agent with its three tools.

    The builder is a fluent API — each ``.with_*()`` call returns self
    so calls chain naturally.  ``.build()`` freezes the configuration
    into an immutable ``AgentProtocol``.
    """
    return (
        AgentBuilder("support-agent")
        .with_system_prompt(SYSTEM_PROMPT)
        .with_tools(*SUPPORT_TOOLS.values())
        .with_strategy("react", max_iterations=5)
        .build()
    )


class SupportAgent:
    """Concrete facade: one question in, one traced response out.

    The facade does not own the executor or agent — it receives them
    via constructor injection, making it easy to swap implementations
    in tests (inject a mock executor) or in production (inject a real
    LLM-backed executor).
    """

    def __init__(self, executor: AgentExecutorProtocol, agent: AgentProtocol) -> None:
        self._executor = executor
        self._agent = agent
        self.last_response: AgentResponse | None = None

    async def ask(self, question: str) -> Result[AgentResponse, AgentError]:
        """Run one ReAct turn against the scripted LLM.

        Returns ``Ok(response)`` on success, ``Err(AgentError)`` on failure.
        Infrastructure errors (e.g. container not booted) propagate as
        exceptions — they are not wrapped in Result.
        """
        result: Result[AgentResponse, AgentError] = await self._executor.run(
            agent=self._agent,
            message=question,
        )
        if result.is_ok():
            self.last_response = result.unwrap()
            logger.info(
                "agent_ask_complete",
                tool_calls=self.last_response.tool_call_count,
                tokens=self.last_response.total_tokens,
            )
        return result
