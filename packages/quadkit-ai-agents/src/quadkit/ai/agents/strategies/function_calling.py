"""Native function-calling strategy for agent reasoning.

Drives the LLM through its native tool-calling interface: ``ToolDefinition``
schemas are sent to ``complete(..., tools=...)`` and the tool calls returned
by the model are executed directly, with results fed back as ``tool`` role
messages.  A text-marker fallback (``ACTION:`` / ``FINAL_ANSWER:``) keeps the
strategy working with models or providers that do not honour native schemas.

This is the strategy that consumes tool schemas from
``ToolRegistry.list_tool_schemas()``, so the schema path is exercised end to
end rather than existing as dead code.

Termination:
    - The model returns no tool calls (its message is the final answer).
    - A text-marker ``FINAL_ANSWER:`` is parsed from the content.
    - The maximum iteration count is reached.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, cast

from quadkit.ai.agents.strategies.base import AbstractStrategy
from quadkit.ai.agents.strategies.function_calling_support import (
    _SYSTEM_SUFFIX,
    execute_tool_with_retry,
    finalize_observation,
    get_memory_context,
    handle_text_tool,
    parse_tool_args,
)
from quadkit.ai.agents.strategies.parsing import (
    build_chat_messages_from_dict,
    extract_final_answer,
    extract_tool_call,
)
from quadkit.ai.agents.strategies.token_utils import count_tokens, token_split
from quadkit.ai.agents.types import ReasoningStep, ToolExecutionRecord
from quadkit.contracts.ai.agents import (
    AgentError,
    AgentResponse,
    ToolDefinition,
    ToolProtocol,
)
from quadkit.contracts.ai.llm import ChatMessage, Role
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.ai.llm import CompletionProtocol, LLMClientProtocol

logger = get_logger(__name__)


class FunctionCallingStrategy(AbstractStrategy):
    """Native tool-calling reasoning strategy.

    Sends function schemas to the LLM and executes the tool calls the model
    returns.  Falls back to text-marker action parsing for providers without
    native tool-calling support.

    Example::

        from quadkit.ai.agents import Agent
        from quadkit.ai.agents.strategies import FunctionCallingStrategy

        agent = Agent(
            llm=my_llm_client,
            strategy=FunctionCallingStrategy(max_iterations=10),
        )
    """

    def __init__(
        self,
        max_iterations: int = 10,
        tool_timeout: float = 30.0,
        observation_max_chars: int = 10_000,
        timeout: float = 120.0,
        tool_max_retries: int = 3,
    ) -> None:
        """Initialise the function-calling strategy.

        Args:
            max_iterations: Maximum number of tool-call rounds.
            tool_timeout: Per-tool execution timeout in seconds.
            observation_max_chars: Maximum characters for tool output before
                truncation.
            timeout: Per-LLM-call timeout in seconds.
            tool_max_retries: Retry attempts for transient tool errors
                (``ConnectionError``, ``OSError``).
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
        """Execute the function-calling loop.

        Args:
            message: The user's input message.
            tools: Tools available to the agent.
            history: Conversation history as ChatMessage objects.
            llm: LLM client implementing ``LLMClientProtocol``.
            **kwargs: Additional parameters:
                - ``system_prompt`` (str): Optional system prompt prefix.
                - ``memory``: Optional memory backend for context retrieval.
                - ``tool_registry``: Optional tool registry whose
                  ``list_tool_schemas()`` output is merged into the schemas
                  sent to the model.

        Returns:
            Ok(AgentResponse) with the final answer and reasoning trace, or
            Err(AgentError) on unrecoverable failure.
        """
        system_prompt: str = kwargs.get("system_prompt", "")
        memory = kwargs.get("memory")
        tool_registry = kwargs.get("tool_registry")
        guard_pipeline = kwargs.get("guard_pipeline")

        steps: list[ReasoningStep] = []
        tool_records: list[ToolExecutionRecord] = []
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        start_time = time.monotonic()

        tool_map: dict[str, ToolProtocol] = {t.name: t for t in tools}
        schemas = self._build_schemas(tools, tool_registry)

        memory_context = await get_memory_context(memory)
        full_system = system_prompt + memory_context + _SYSTEM_SUFFIX
        messages = build_chat_messages_from_dict(message, history, full_system)

        for iteration in range(1, self.max_iterations + 1):
            completion = await self._call_llm(llm, messages, schemas)
            if completion is None:
                return Err(AgentError(f"LLM failed at iteration {iteration}"))

            step_prompt, step_completion = token_split(completion)
            prompt_tokens += step_prompt
            completion_tokens += step_completion
            total_tokens += count_tokens(completion)

            native_calls = getattr(completion, "tool_calls", None) or []
            if native_calls:
                if await self._handle_native_calls(
                    completion,
                    iteration,
                    messages,
                    steps,
                    tool_records,
                    tool_map,
                    guard_pipeline=guard_pipeline,
                ):
                    continue

            content = getattr(completion, "content", None) or ""
            if not content.strip():
                steps.append(
                    ReasoningStep(
                        step_number=iteration,
                        thought=content,
                        action=None,
                        observation="[No valid tool call returned — retrying]",
                    )
                )
                messages.append(
                    ChatMessage(
                        role=Role.ASSISTANT,
                        content=content or "",
                        tool_calls=native_calls or None,
                    )
                )
                messages.append(
                    ChatMessage(
                        role=Role.USER,
                        content=(
                            "Your previous response contained no tool calls or "
                            "final answer. Either call a tool natively or "
                            "answer the user directly."
                        ),
                    )
                )
                continue

            final_answer = extract_final_answer(content)
            if final_answer is not None:
                final = final_answer
            else:
                tool_name, tool_args = extract_tool_call(content)
                if tool_name is not None:
                    logger.debug(
                        "function_calling_text_fallback",
                        iteration=iteration,
                    )
                    await handle_text_tool(
                        self,
                        tool_name,
                        tool_args,
                        content,
                        iteration,
                        messages,
                        steps,
                        tool_records,
                        tool_map,
                        guard_pipeline=guard_pipeline,
                    )
                    continue
                final = content

            steps.append(
                ReasoningStep(
                    step_number=iteration,
                    thought=content,
                    action="final_answer",
                    observation=final,
                )
            )
            elapsed = (time.monotonic() - start_time) * 1000
            return Ok(
                AgentResponse(
                    message=final,
                    steps=steps,
                    tool_calls=tool_records,
                    total_tokens=total_tokens,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    duration_ms=elapsed,
                    metadata={
                        "strategy": "function_calling",
                        "iterations": iteration,
                    },
                )
            )

        elapsed = (time.monotonic() - start_time) * 1000
        last_obs = steps[-1].observation if steps else "No response generated"
        return Ok(
            AgentResponse(
                message=f"[Max iterations reached] {last_obs}",
                steps=steps,
                tool_calls=tool_records,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=elapsed,
                metadata={
                    "strategy": "function_calling",
                    "iterations": self.max_iterations,
                    "max_iterations_reached": True,
                },
            )
        )

    # ------------------------------------------------------------------
    # Schema building
    # ------------------------------------------------------------------

    def _build_schemas(
        self,
        tools: list[ToolProtocol],
        tool_registry: Any,
    ) -> list[ToolDefinition]:
        """Build the native tool schema list sent to the LLM.

        Merges per-tool schemas with any schemas exposed by ``tool_registry``
        (``list_tool_schemas``), wiring the registry schema builder into the
        live tool-calling path.

        Args:
            tools: Executable tools to describe.
            tool_registry: Optional tool registry.

        Returns:
            List of ``ToolDefinition`` schemas.
        """
        schemas = [
            ToolDefinition(
                name=t.name,
                description=t.description,
                parameters=t.parameters_schema,
            )
            for t in tools
        ]
        present = {s.name for s in schemas}
        list_schemas = getattr(tool_registry, "list_tool_schemas", None)
        if list_schemas is not None:
            for raw in list_schemas():
                function = raw.get("function", {})
                name = function.get("name")
                if name and name not in present:
                    schemas.append(
                        ToolDefinition(
                            name=name,
                            description=function.get("description", ""),
                            parameters=function.get("parameters", {}),
                        )
                    )
                    present.add(name)
        return schemas

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        llm: LLMClientProtocol,
        messages: list[ChatMessage],
        schemas: list[ToolDefinition],
    ) -> CompletionProtocol | None:
        """Call the LLM with tool schemas and return the completion.

        Args:
            llm: LLM client implementing ``LLMClientProtocol``.
            messages: Chat message history.
            schemas: Native tool schemas to advertise to the model.

        Returns:
            The completion object, or ``None`` when the call failed.
        """
        try:
            result = await asyncio.wait_for(
                llm.complete(
                    cast("list[Any]", messages),
                    tools=schemas or None,
                ),
                timeout=self.timeout,
            )
        except TimeoutError:
            logger.warning("function_calling_llm_timeout", timeout=self.timeout)
            return None
        except Exception as exc:  # noqa: BLE001 — LLM failures degrade the strategy, never crash it
            logger.warning(
                "function_calling_llm_error",
                error_type=type(exc).__name__,
            )
            return None

        if not result.is_ok():
            llm_error = result.unwrap_err()
            logger.warning(
                "function_calling_llm_err_result",
                error_type=type(llm_error).__name__,
            )
            return None
        return result.unwrap()

    # ------------------------------------------------------------------
    # Native tool loop
    # ------------------------------------------------------------------

    async def _handle_native_calls(
        self,
        completion: CompletionProtocol,
        iteration: int,
        messages: list[ChatMessage],
        steps: list[ReasoningStep],
        tool_records: list[ToolExecutionRecord],
        tool_map: dict[str, ToolProtocol],
        guard_pipeline: Any = None,
    ) -> bool:
        """Execute native tool calls and feed results back as tool messages.

        The assistant message carrying the native calls is inserted before the
        matching ``tool`` role responses so the provider can re-emit the full
        round trip.

        Returns:
            ``True`` when at least one tool call was executed (loop continues),
            ``False`` when there was nothing executable.
        """
        native_calls = getattr(completion, "tool_calls", None) or []
        if not native_calls:
            return False

        assistant_idx = len(messages)
        executed = False
        for native_call in native_calls:
            function = getattr(native_call, "function", None)
            if function is None:
                continue
            tool_name = function.name
            tool_args = parse_tool_args(getattr(function, "arguments", {}))
            record = await execute_tool_with_retry(
                tool_name,
                tool_args,
                tool_map,
                tool_timeout=self.tool_timeout,
                tool_max_retries=self.tool_max_retries,
            )
            tool_records.append(record)
            executed = True

            observation = (
                str(record.result) if record.succeeded else f"Error: {record.error}"
            )
            # Guard before truncation so detectors see the full content
            observation = await finalize_observation(
                guard_pipeline,
                observation,
                tool_name=tool_name,
                max_chars=self.observation_max_chars,
            )

            steps.append(
                ReasoningStep(
                    step_number=iteration,
                    thought=getattr(completion, "content", None) or "",
                    action=tool_name,
                    tool_call=record,
                    observation=observation,
                )
            )
            messages.append(
                ChatMessage(
                    role=Role.TOOL,
                    content=observation,
                    tool_call_id=native_call.id,
                )
            )

        if executed:
            messages.insert(
                assistant_idx,
                ChatMessage(
                    role=Role.ASSISTANT,
                    content=getattr(completion, "content", None) or "",
                    tool_calls=list(native_calls),
                ),
            )
        return executed


__all__ = ["FunctionCallingStrategy"]
