"""Supervisor strategy for multi-agent orchestration.

Implements a delegation-based reasoning loop where a supervisor LLM
decides which specialized sub-agent should handle each part of a task:

    1. **ASSESS** — The supervisor LLM receives the objective and a
       list of available sub-agents (presented as tools).
    2. **DELEGATE** — The supervisor selects a sub-agent and provides
       a sub-task message.
    3. **REVIEW** — The sub-agent's response is fed back to the
       supervisor as an observation.
    4. **DECIDE** — The supervisor either delegates again, or produces
       a final synthesized answer.

This strategy replaces CrewAI's hierarchical process and AutoGen's
conversation patterns with a clean, contract-based implementation.

Example::

    from quadkit.ai.agents.strategies import SupervisorStrategy

    supervisor_strategy = SupervisorStrategy(
        sub_agents={"billing": billing_agent, "technical": tech_agent},
        executor=executor,
        max_delegations=5,
    )
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, cast

from quadkit.ai.agents.delegation.agent_tool import AgentAsToolAdapter
from quadkit.ai.agents.strategies.base import AbstractStrategy
from quadkit.ai.agents.strategies.token_utils import TokenAccumulator
from quadkit.ai.agents.types import ReasoningStep, ToolExecutionRecord
from quadkit.contracts.ai.agents import AgentError, AgentResponse
from quadkit.contracts.ai.llm import ChatMessage, Role
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.ai.agents import (
        AgentExecutorProtocol,
        AgentProtocol,
        ToolProtocol,
    )
    from quadkit.contracts.ai.llm import CompletionProtocol, LLMClientProtocol

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SUPERVISOR_SYSTEM = """
You are a supervisor agent that delegates tasks to specialized sub-agents.

## Your Role
- Analyze the user's request and decide which sub-agent is best suited.
- Delegate tasks by calling the appropriate agent tool.
- Review sub-agent responses and decide: delegate again or provide a final answer.
- You may delegate to multiple agents sequentially if the task requires it.

## Output Format

### Option A — Delegate to a sub-agent
```
THOUGHT: <your reasoning about which agent to use and why>
ACTION: delegate_to_<agent_name>
ACTION_INPUT: {{"message": "<the sub-task to delegate>"}}
```

### Option B — Final Answer (after reviewing sub-agent responses)
```
THOUGHT: <your reasoning about why you have enough information>
FINAL_ANSWER: <your complete, synthesized answer>
```

## Rules
- Always start with THOUGHT.
- Delegate ONE task at a time.
- After receiving an observation, decide whether to delegate again or answer.
- Synthesize information from multiple agents if needed.
- When you have a complete answer, use FINAL_ANSWER.

## Available Agents
{agent_descriptions}
"""

_OBSERVATION_TEMPLATE = "OBSERVATION from {agent_name}: {observation}"


class SupervisorStrategy(AbstractStrategy):
    """Supervisor strategy that orchestrates multiple sub-agents.

    The supervisor uses an LLM to decide which sub-agent should handle
    each part of a task. Sub-agents are exposed as tools using
    ``AgentAsToolAdapter``, allowing the supervisor to delegate via
    the standard tool-calling mechanism.

    This enables hierarchical multi-agent patterns:
    - Customer support routing (classify → specialist agent)
    - Research tasks (delegate to searcher, analyzer, summarizer)
    - Quality assurance (generate → review → revise)

    Example::

        strategy = SupervisorStrategy(
            sub_agents={"research": research_agent, "writing": writing_agent},
            executor=executor,
        )
        result = await strategy.execute(
            message="Write a report about quantum computing",
            tools=[],  # supervisor uses sub-agents, not tools
            history=[],
            llm=llm_client,
        )
    """

    def __init__(
        self,
        sub_agents: dict[str, AgentProtocol],
        executor: AgentExecutorProtocol,
        *,
        max_delegations: int = 5,
        llm_timeout: float = 120.0,
    ) -> None:
        """Initialize the supervisor strategy.

        Args:
            sub_agents: Named sub-agents available for delegation.
            executor: Agent executor used to run sub-agents.
            max_delegations: Maximum number of delegation rounds.
            llm_timeout: Timeout per LLM call in seconds.
        """
        self._sub_agents = sub_agents
        self._executor = executor
        self.max_delegations = max_delegations
        self.llm_timeout = llm_timeout

        # Build agent tools
        self._agent_tools: dict[str, AgentAsToolAdapter] = {
            name: AgentAsToolAdapter(agent=agent, executor=executor)
            for name, agent in sub_agents.items()
        }

    async def execute(
        self,
        message: str,
        tools: list[ToolProtocol],
        history: list[dict[str, Any]],
        llm: LLMClientProtocol,
        **kwargs: Any,
    ) -> Result[AgentResponse, AgentError]:
        """Execute the supervisor delegation loop.

        Args:
            message: The user's input message.
            tools: Additional tools (merged with agent-as-tool adapters).
            history: Conversation history as list of message dicts.
            llm: LLM client implementing ``LLMClientProtocol``.
            **kwargs: Additional parameters (system_prompt, etc.).

        Returns:
            ``Ok(AgentResponse)`` with the supervisor's final answer
            and full delegation trace. ``Err(AgentError)`` on failure.
        """
        system_prompt: str = kwargs.get("system_prompt", "")
        guard_pipeline = kwargs.get("guard_pipeline")
        steps: list[ReasoningStep] = []
        tool_calls: list[ToolExecutionRecord] = []
        usage = TokenAccumulator()
        start_time = time.monotonic()

        # Build combined tool map: agent tools + any extra tools
        all_tools: dict[str, ToolProtocol] = {}
        for adapter in self._agent_tools.values():
            all_tools[adapter.name] = adapter
        for t in tools:
            all_tools[t.name] = t

        # Build agent descriptions for system prompt
        agent_descriptions = "\n".join(
            f"- **{adapter.name}**: {adapter.description}"
            for adapter in self._agent_tools.values()
        )

        full_system = system_prompt + _SUPERVISOR_SYSTEM.format(
            agent_descriptions=agent_descriptions
        )

        messages = self._build_messages(message, history, full_system)

        for delegation in range(1, self.max_delegations + 1):
            # Ask supervisor LLM what to do
            completion = await self._call_llm(llm, messages)
            if completion is None:
                return Err(
                    AgentError(
                        f"Supervisor LLM returned empty response at delegation {delegation}"
                    )
                )
            usage.add(completion)
            llm_text = (
                completion.content
                if hasattr(completion, "content")
                else str(completion)
            )

            thought = self._extract_thought(llm_text)
            final_answer = self._extract_final_answer(llm_text)

            # Check for final answer
            if final_answer is not None:
                steps.append(
                    ReasoningStep(
                        step_number=delegation,
                        thought=thought,
                        action="final_answer",
                        observation=final_answer,
                    )
                )

                elapsed = (time.monotonic() - start_time) * 1000
                logger.info(
                    "supervisor_final_answer",
                    delegations=delegation,
                    steps=len(steps),
                )
                return Ok(
                    AgentResponse(
                        message=final_answer,
                        steps=steps,
                        tool_calls=tool_calls,
                        total_tokens=usage.total_tokens,
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        duration_ms=elapsed,
                        metadata={
                            "strategy": "supervisor",
                            "delegations": delegation,
                            "agents_used": list(
                                {
                                    s.action
                                    for s in steps
                                    if s.action and s.action.startswith("delegate_to_")
                                }
                            ),
                        },
                    )
                )

            # Parse delegation (tool call)
            tool_name, tool_args = self._extract_tool_call(llm_text)

            if tool_name is None or tool_name not in all_tools:
                # No valid delegation — nudge the LLM
                steps.append(
                    ReasoningStep(
                        step_number=delegation,
                        thought=thought,
                        action=None,
                        observation="[No valid delegation or final answer detected]",
                    )
                )
                messages.append(ChatMessage(role=Role.ASSISTANT, content=llm_text))
                messages.append(
                    ChatMessage(
                        role=Role.USER,
                        content=(
                            "Your response did not contain a valid delegation or "
                            "FINAL_ANSWER. Please:\n"
                            "- Use ACTION: delegate_to_<agent_name> to delegate, or\n"
                            "- Use FINAL_ANSWER: to provide your answer."
                        ),
                    )
                )
                continue

            # Execute delegation
            logger.info(
                "supervisor_delegation",
                delegation=delegation,
                target=tool_name,
            )

            tool = all_tools[tool_name]
            delegation_start = time.monotonic()

            try:
                result = await tool.execute(**tool_args)
                duration = (time.monotonic() - delegation_start) * 1000
                observation = str(result)

                record = ToolExecutionRecord(
                    tool_name=tool_name,
                    arguments=tool_args,
                    result=result,
                    duration_ms=duration,
                )
            except Exception as exc:  # noqa: BLE001 — delegation errors omit raw details
                duration = (time.monotonic() - delegation_start) * 1000
                error_type = type(exc).__name__
                observation = f"Delegation failed ({error_type})"
                record = ToolExecutionRecord(
                    tool_name=tool_name,
                    arguments=tool_args,
                    error=observation,
                    duration_ms=duration,
                )

            tool_calls.append(record)

            # Guard before feeding back so the raw observation never hits context
            from quadkit.ai.agents.strategies.guard_hook import guard_observation

            observation = await guard_observation(
                guard_pipeline, observation, tool_name=tool_name
            )

            # Derive agent name from tool name for the observation
            agent_display = (
                tool_name.replace("delegate_to_", "")
                if tool_name.startswith("delegate_to_")
                else tool_name
            )

            steps.append(
                ReasoningStep(
                    step_number=delegation,
                    thought=thought,
                    action=tool_name,
                    tool_call=record,
                    observation=observation,
                )
            )

            # Feed observation back
            messages.append(ChatMessage(role=Role.ASSISTANT, content=llm_text))
            messages.append(
                ChatMessage(
                    role=Role.USER,
                    content=_OBSERVATION_TEMPLATE.format(
                        agent_name=agent_display,
                        observation=observation,
                    ),
                )
            )

        # Max delegations reached
        elapsed = (time.monotonic() - start_time) * 1000
        logger.warning(
            "supervisor_max_delegations",
            max_delegations=self.max_delegations,
            steps=len(steps),
        )
        last_obs = steps[-1].observation if steps else "No response generated"
        return Ok(
            AgentResponse(
                message=f"[Max delegations reached] {last_obs}",
                steps=steps,
                tool_calls=tool_calls,
                total_tokens=usage.total_tokens,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                duration_ms=elapsed,
                metadata={
                    "strategy": "supervisor",
                    "delegations": self.max_delegations,
                    "max_delegations_reached": True,
                },
            )
        )

    # ------------------------------------------------------------------
    # LLM Interaction
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        llm: LLMClientProtocol,
        messages: list[ChatMessage],
    ) -> CompletionProtocol | None:
        """Call the LLM and return the completion, or ``None`` on failure."""
        try:
            result = await asyncio.wait_for(
                llm.complete(cast("list[Any]", messages)),
                timeout=self.llm_timeout,
            )
        except TimeoutError:
            logger.warning("supervisor_llm_timeout", timeout=self.llm_timeout)
            return None
        except Exception as exc:  # noqa: BLE001 — LLM failures degrade the strategy, never crash it
            logger.warning(
                "supervisor_llm_error",
                error_type=type(exc).__name__,
            )
            return None

        if not result.is_ok():
            llm_error = result.unwrap_err()
            logger.warning(
                "supervisor_llm_err",
                error_type=type(llm_error).__name__,
            )
            return None

        return result.unwrap()

    # ------------------------------------------------------------------
    # Parsing Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_thought(text: str) -> str:
        """Extract THOUGHT section from LLM response."""
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.upper().startswith("THOUGHT:"):
                return stripped[len("THOUGHT:") :].strip()
        return text.split("\n", maxsplit=1)[0][:200]

    @staticmethod
    def _extract_final_answer(text: str) -> str | None:
        """Extract FINAL_ANSWER if present."""
        marker = "FINAL_ANSWER:"
        upper = text.upper()
        idx = upper.find(marker)
        if idx == -1:
            return None
        return text[idx + len(marker) :].strip()

    @staticmethod
    def _extract_tool_call(text: str) -> tuple[str | None, dict[str, Any]]:
        """Extract ACTION and ACTION_INPUT from LLM response."""
        from quadkit.serialization.backends.json import JSONDecodeError, loads

        action_name: str | None = None
        action_input: dict[str, Any] = {}

        for line in text.split("\n"):
            stripped = line.strip()
            upper = stripped.upper()
            if upper.startswith("ACTION:") and not upper.startswith("ACTION_INPUT:"):
                action_name = stripped[len("ACTION:") :].strip()
            elif upper.startswith("ACTION_INPUT:"):
                raw = stripped[len("ACTION_INPUT:") :].strip()
                try:
                    action_input = loads(raw)
                except (ValueError, JSONDecodeError):
                    brace_start = raw.find("{")
                    if brace_start != -1:
                        depth = 0
                        for i, ch in enumerate(raw[brace_start:]):
                            if ch == "{":
                                depth += 1
                            elif ch == "}":
                                depth -= 1
                            if depth == 0:
                                try:
                                    action_input = loads(
                                        raw[brace_start : brace_start + i + 1]
                                    )
                                except (ValueError, JSONDecodeError):
                                    pass
                                break

        return action_name, action_input

    # ------------------------------------------------------------------
    # Message Building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(
        message: str,
        history: list[dict[str, Any]],
        system_prompt: str,
    ) -> list[ChatMessage]:
        """Convert history + new message into ChatMessage objects."""
        messages: list[ChatMessage] = []
        if system_prompt:
            messages.append(ChatMessage(role=Role.SYSTEM, content=system_prompt))
        for entry in history:
            role_str = entry.get("role", "user")
            content = entry.get("content", "")
            try:
                role = Role(role_str)
            except ValueError:
                role = Role.USER
            messages.append(ChatMessage(role=role, content=content))
        messages.append(ChatMessage(role=Role.USER, content=message))
        return messages


__all__ = ["SupervisorStrategy"]
