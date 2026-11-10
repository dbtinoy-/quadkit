"""ReAct (Reason + Act) strategy for agent reasoning.

Implements the Think → Act → Observe loop described in:
    Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models" (2022)

Each iteration:
    1. **Think** — The LLM reasons about the current state and decides
       whether to call a tool or produce a final answer.
    2. **Act** — If the LLM requests a tool call, the tool is executed
       with timeout and output truncation.
    3. **Observe** — The tool result (or error) is fed back as the next
       user message so the LLM can incorporate it.

The loop terminates when:
    - The LLM signals a final answer (``FINAL_ANSWER:`` prefix).
    - The maximum iteration count is reached.
    - A governance budget check fails.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, cast

from quadkit.ai.agents.strategies.base import AbstractStrategy
from quadkit.ai.agents.strategies.parsing import (
    build_chat_messages_from_dict,
    extract_final_answer,
    extract_thought,
    extract_tool_call,
)
from quadkit.ai.agents.strategies.token_utils import TokenAccumulator
from quadkit.ai.agents.types import ReasoningStep, ToolExecutionRecord
from quadkit.contracts.ai.agents import AgentError, AgentResponse
from quadkit.contracts.ai.llm import ChatMessage, Role
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.ai.agents import MemoryProtocol, ToolProtocol
    from quadkit.contracts.ai.llm import CompletionProtocol, LLMClientProtocol

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_SUFFIX = """
You are a ReAct agent. You solve problems by iterating through Think, Act, and Observe steps.

## Output Format

On each turn you MUST produce EXACTLY ONE of two outputs:

### Option A — Thinking + Tool Call
```
THOUGHT: <your step-by-step reasoning>
ACTION: <tool_name>
ACTION_INPUT: <JSON arguments for the tool>
```

### Option B — Final Answer
```
THOUGHT: <your final reasoning>
FINAL_ANSWER: <your complete answer to the user>
```

## Rules
- Always start with THOUGHT.
- Use EXACTLY one tool per turn. Do not call multiple tools at once.
- After receiving an OBSERVATION, think about what to do next.
- When you have enough information, produce FINAL_ANSWER.

## Available Tools
{tool_descriptions}
"""

_OBSERVATION_TEMPLATE = "OBSERVATION: {observation}"


class ReActStrategy(AbstractStrategy):
    """ReAct (Reason + Act) reasoning strategy.

    The ReAct strategy follows a Think → Act → Observe loop:

    1. **Think** — LLM reasons about the current state.
    2. **Act** — Parse and execute a tool call from the LLM response.
    3. **Observe** — Feed tool result back as an observation.
    4. **Decide** — Check if the LLM signals completion.

    This is the default strategy for Quadkit agents.

    Example::

        from quadkit.ai.agents import Agent
        from quadkit.ai.agents.strategies import ReActStrategy

        agent = Agent(
            llm=my_llm_client,
            strategy=ReActStrategy(max_iterations=10),
        )
        response = await agent.run("What's the weather?")
    """

    def __init__(
        self,
        max_iterations: int = 10,
        tool_timeout: float = 30.0,
        observation_max_chars: int = 10_000,
        timeout: float = 120.0,
        tool_max_retries: int = 3,
    ) -> None:
        """Initialise the ReAct strategy.

        Args:
            max_iterations: Maximum number of Think→Act→Observe cycles.
            tool_timeout: Per-tool execution timeout in seconds.
            observation_max_chars: Maximum characters for tool output before
                truncation.
            timeout: Per-LLM-call timeout in seconds.
            tool_max_retries: Retry attempts for transient tool errors
                (``ConnectionError``, ``OSError``).  Each retry waits
                with exponential back-off (1s, 2s, 4s, …).
        """
        self.max_iterations = max_iterations
        self.tool_timeout = tool_timeout
        self.observation_max_chars = observation_max_chars
        self.timeout = timeout
        self.tool_max_retries = tool_max_retries

    async def execute(
        self,
        message: str,
        tools: list[ToolProtocol],
        history: list[dict[str, Any]],
        llm: LLMClientProtocol,
        **kwargs: Any,
    ) -> Result[AgentResponse, AgentError]:
        """Execute the ReAct reasoning loop.

        Args:
            message: The user's input message.
            tools: Tools available to the agent.
            history: Conversation history as ChatMessage objects.
            llm: LLM client implementing ``LLMClientProtocol``.
            **kwargs: Additional parameters:
                - ``system_prompt`` (str): Optional system prompt prefix.
                - ``memory``: Optional memory backend for context retrieval.

        Returns:
            ``Ok(AgentResponse)`` with the final answer and full reasoning
            trace.  ``Err(AgentError)`` on unrecoverable failure.
        """
        system_prompt: str = kwargs.get("system_prompt", "")
        memory = kwargs.get("memory")
        guard_pipeline = kwargs.get("guard_pipeline")

        steps: list[ReasoningStep] = []
        tool_calls: list[ToolExecutionRecord] = []
        usage = TokenAccumulator()
        start_time = time.monotonic()

        # Build tool lookup
        tool_map: dict[str, ToolProtocol] = {t.name: t for t in tools}

        # Retrieve memory context
        memory_context = await self._get_memory_context(memory)

        # Build system prompt with tool descriptions
        tool_descriptions = "\n".join(
            f"- **{t.name}**: {t.description}\n  Parameters: {t.parameters_schema}"
            for t in tools
        )
        full_system = (
            system_prompt
            + memory_context
            + _SYSTEM_SUFFIX.format(tool_descriptions=tool_descriptions)
        )

        # Build messages from history
        messages = build_chat_messages_from_dict(message, history, full_system)

        for iteration in range(1, self.max_iterations + 1):
            # --- THINK: Ask LLM to reason ---
            completion = await self._call_llm(llm, messages)
            if completion is None:
                return Err(
                    AgentError(f"LLM returned empty response at iteration {iteration}")
                )
            usage.add(completion)
            llm_text = (
                completion.content
                if hasattr(completion, "content")
                else str(completion)
            )

            logger.debug(
                "react_llm_response",
                iteration=iteration,
                length=len(llm_text),
            )

            # Parse the response
            thought = extract_thought(llm_text)
            final_answer = extract_final_answer(llm_text)

            # --- DECIDE: Is this a final answer? ---
            if final_answer is not None:
                steps.append(
                    ReasoningStep(
                        step_number=iteration,
                        thought=thought,
                        action="final_answer",
                        observation=final_answer,
                    )
                )
                logger.info(
                    "react_final_answer",
                    iteration=iteration,
                    steps=len(steps),
                    tool_calls=len(tool_calls),
                )
                elapsed = (time.monotonic() - start_time) * 1000
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
                            "strategy": "react",
                            "iterations": iteration,
                        },
                    )
                )

            # --- ACT: Parse tool call ---
            tool_name, tool_args = extract_tool_call(llm_text)

            if tool_name is None:
                # No tool call and no final answer — nudge the LLM
                steps.append(
                    ReasoningStep(
                        step_number=iteration,
                        thought=thought,
                        action=None,
                        observation="[No valid action detected — retrying]",
                    )
                )
                messages.append(ChatMessage(role=Role.ASSISTANT, content=llm_text))
                messages.append(
                    ChatMessage(
                        role=Role.USER,
                        content=(
                            "Your response did not contain a valid ACTION or "
                            "FINAL_ANSWER. Please respond with either:\n"
                            "- ACTION: <tool_name> and ACTION_INPUT: <json_args>\n"
                            "- FINAL_ANSWER: <your answer>"
                        ),
                    )
                )
                continue

            # --- EXECUTE: Run tool with timeout ---
            logger.info(
                "react_tool_call",
                iteration=iteration,
            )

            tool_record = await self._execute_tool(tool_name, tool_args, tool_map)
            tool_calls.append(tool_record)

            # Build observation
            if tool_record.succeeded:
                obs_text = str(tool_record.result)
            else:
                obs_text = f"Error: {tool_record.error}"

            # Guard before truncation so detectors see the full content
            from quadkit.ai.agents.strategies.guard_hook import guard_observation

            obs_text = await guard_observation(
                guard_pipeline, obs_text, tool_name=tool_name
            )

            # Truncate large outputs
            if len(obs_text) > self.observation_max_chars:
                obs_text = obs_text[: self.observation_max_chars] + "\n[TRUNCATED]"

            steps.append(
                ReasoningStep(
                    step_number=iteration,
                    thought=thought,
                    action=tool_name,
                    tool_call=tool_record,
                    observation=obs_text,
                )
            )

            # --- OBSERVE: Feed result back ---
            messages.append(ChatMessage(role=Role.ASSISTANT, content=llm_text))
            messages.append(
                ChatMessage(
                    role=Role.USER,
                    content=_OBSERVATION_TEMPLATE.format(observation=obs_text),
                )
            )

        # Max iterations reached
        elapsed = (time.monotonic() - start_time) * 1000
        logger.warning(
            "react_max_iterations",
            max_iterations=self.max_iterations,
            steps=len(steps),
        )
        # Return the best answer we have so far
        last_obs = steps[-1].observation if steps else "No response generated"
        return Ok(
            AgentResponse(
                message=f"[Max iterations reached] {last_obs}",
                steps=steps,
                tool_calls=tool_calls,
                total_tokens=usage.total_tokens,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                duration_ms=elapsed,
                metadata={
                    "strategy": "react",
                    "iterations": self.max_iterations,
                    "max_iterations_reached": True,
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
        **kwargs: Any,
    ) -> CompletionProtocol | None:
        """Call the LLM and return the completion, or ``None`` on failure."""
        try:
            result = await asyncio.wait_for(
                llm.complete(cast("list[Any]", messages), **kwargs),
                timeout=self.timeout,
            )
        except TimeoutError:
            logger.warning("react_llm_timeout", timeout=self.timeout)
            return None
        except Exception as exc:  # noqa: BLE001 — LLM failures degrade the strategy, never crash it
            logger.warning("react_llm_error", error_type=type(exc).__name__)
            return None

        if not result.is_ok():
            llm_error = result.unwrap_err()
            logger.warning(
                "react_llm_err_result",
                error_type=type(llm_error).__name__,
            )
            return None

        return result.unwrap()

    # ------------------------------------------------------------------
    # Tool Execution
    # ------------------------------------------------------------------

    async def _execute_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_map: dict[str, ToolProtocol],
    ) -> ToolExecutionRecord:
        """Execute a tool with timeout, retry on transient errors, and recovery.

        Retries up to ``self.tool_max_retries`` times on transient infrastructure
        errors (``ConnectionError``, ``OSError``) using exponential back-off
        (1 s, 2 s, 4 s, …).  ``TimeoutError`` and non-transient exceptions
        short-circuit immediately without retrying.

        Args:
            tool_name: Name of the tool to execute.
            tool_args: Arguments to pass to the tool.
            tool_map: Mapping of tool names to tool instances.

        Returns:
            ``ToolExecutionRecord`` with the result or error details.
        """
        if tool_name not in tool_map:
            return ToolExecutionRecord(
                tool_name=tool_name,
                arguments=tool_args,
                error="Unknown tool",
            )

        tool = tool_map[tool_name]
        start = time.monotonic()
        last_error: BaseException | None = None

        for attempt in range(self.tool_max_retries):
            try:
                output = await asyncio.wait_for(
                    tool.execute(**tool_args),
                    timeout=self.tool_timeout,
                )
                duration = (time.monotonic() - start) * 1000
                if attempt > 0:
                    logger.info(
                        "react_tool_retry_succeeded",
                        attempt=attempt + 1,
                    )
                return ToolExecutionRecord(
                    tool_name=tool_name,
                    arguments=tool_args,
                    result=output,
                    duration_ms=duration,
                )
            except TimeoutError:
                duration = (time.monotonic() - start) * 1000
                return ToolExecutionRecord(
                    tool_name=tool_name,
                    arguments=tool_args,
                    error=f"Tool execution timed out after {self.tool_timeout}s",
                    duration_ms=duration,
                )
            except (ConnectionError, OSError) as exc:
                last_error = exc
                logger.warning(
                    "react_tool_transient_error",
                    attempt=attempt + 1,
                    max_retries=self.tool_max_retries,
                    error_type=type(exc).__name__,
                )
                if attempt < self.tool_max_retries - 1:
                    await asyncio.sleep(1.0 * (2**attempt))
            except Exception as exc:  # noqa: BLE001 — tool errors are returned without raw details
                duration = (time.monotonic() - start) * 1000
                return ToolExecutionRecord(
                    tool_name=tool_name,
                    arguments=tool_args,
                    error=f"Tool execution failed ({type(exc).__name__})",
                    duration_ms=duration,
                )

        duration = (time.monotonic() - start) * 1000
        last_error_type = type(last_error).__name__ if last_error else "UnknownError"
        return ToolExecutionRecord(
            tool_name=tool_name,
            arguments=tool_args,
            error=(
                f"Tool execution failed after {self.tool_max_retries} "
                f"retries ({last_error_type})"
            ),
            duration_ms=duration,
        )

    # ------------------------------------------------------------------
    # Message Building
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_memory_context(memory: MemoryProtocol | None) -> str:
        """Retrieve context from memory backend if available."""
        if memory is None:
            return ""
        try:
            past_messages = await memory.get_messages()
            if past_messages:
                context_str = "\n".join(str(m) for m in past_messages[-5:])
                return f"\n\nRelevant context from memory:\n{context_str}"
        except Exception:  # noqa: BLE001 — memory failures must not break the agent loop
            # Memory failures must not break the agent
            pass
        return ""


__all__ = ["ReActStrategy"]
