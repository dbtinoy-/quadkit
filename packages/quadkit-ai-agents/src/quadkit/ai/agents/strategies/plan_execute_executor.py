"""Async execution helpers for the Plan-and-Execute strategy.

Provides module-level async functions that handle all I/O-bound operations:
- Calling the LLM with timeout and error recovery.
- Running tools with timeout and error recovery.
- Executing a single plan step (tool-based or reasoning-based).
- Replanning after step failures.
- Synthesizing a final answer from all completed steps.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, cast

from quadkit.ai.agents.strategies.parsing import (
    build_chat_messages_from_dict,
    extract_tool_call,
)
from quadkit.ai.agents.strategies.plan_execute_planner import (
    extract_final_answer,
    extract_step_result,
    format_completed_steps,
    format_plan,
    parse_plan,
)
from quadkit.ai.agents.strategies.plan_execute_types import (
    EXECUTION_PROMPT,
    REPLAN_PROMPT,
    SYNTHESIS_PROMPT,
    PlanStep,
    PlanStepStatus,
)
from quadkit.ai.agents.strategies.token_utils import TokenAccumulator
from quadkit.ai.agents.types import ToolExecutionRecord
from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.contracts.ai.agents import ToolProtocol
    from quadkit.contracts.ai.llm import ChatMessage, LLMClientProtocol

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM interaction
# ---------------------------------------------------------------------------


async def call_llm(
    llm: LLMClientProtocol,
    messages: list[ChatMessage],
    *,
    timeout: float,
    usage: TokenAccumulator | None = None,
) -> str | None:
    """Call the LLM and return text content, or ``None`` on failure.

    Args:
        llm: LLM client implementing ``LLMClientProtocol``.
        messages: Chat messages to send.
        timeout: Maximum seconds to wait for a response.
        usage: Optional accumulator to count tokens from the completion.

    Returns:
        Text content of the completion, or ``None`` if the call failed.
    """
    try:
        result = await asyncio.wait_for(
            llm.complete(cast("list[Any]", messages)),
            timeout=timeout,
        )
    except TimeoutError:
        logger.warning("plan_execute_llm_timeout", timeout=timeout)
        return None
    except Exception as exc:  # noqa: BLE001 — LLM failures degrade the strategy, never crash it
        logger.warning(
            "plan_execute_llm_error",
            error_type=type(exc).__name__,
        )
        return None

    if not result.is_ok():
        llm_error = result.unwrap_err()
        logger.warning(
            "plan_execute_llm_err",
            error_type=type(llm_error).__name__,
        )
        return None

    completion = result.unwrap()
    if usage is not None:
        usage.add(completion)
    return completion.content if hasattr(completion, "content") else str(completion)


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


async def run_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_map: dict[str, ToolProtocol],
    *,
    timeout: float,
) -> ToolExecutionRecord:
    """Execute a named tool with timeout and error recovery.

    Args:
        tool_name: Name of the tool to execute.
        tool_args: Keyword arguments forwarded to ``tool.execute()``.
        tool_map: Mapping of tool names to tool instances.
        timeout: Maximum seconds to allow the tool to run.

    Returns:
        A ``ToolExecutionRecord`` capturing the outcome (success or failure).
    """
    if tool_name not in tool_map:
        return ToolExecutionRecord(
            tool_name=tool_name,
            arguments=tool_args,
            error="Unknown tool",
        )

    tool = tool_map[tool_name]
    start = time.monotonic()

    try:
        output = await asyncio.wait_for(
            tool.execute(**tool_args),
            timeout=timeout,
        )
        duration = (time.monotonic() - start) * 1000
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
            error=f"Tool execution timed out after {timeout}s",
            duration_ms=duration,
        )
    except Exception as exc:  # noqa: BLE001 — tool errors are returned without raw details
        duration = (time.monotonic() - start) * 1000
        return ToolExecutionRecord(
            tool_name=tool_name,
            arguments=tool_args,
            error=f"Tool execution failed ({type(exc).__name__})",
            duration_ms=duration,
        )


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------


async def execute_tool_step(
    llm: LLMClientProtocol,
    plan_step: PlanStep,
    plan: list[PlanStep],
    tool_map: dict[str, ToolProtocol],
    original_message: str,
    history: list[dict[str, Any]],
    system_prompt: str,
    *,
    tool_timeout: float,
    llm_timeout: float,
    observation_max_chars: int,
    usage: TokenAccumulator | None = None,
    guard_pipeline: Any = None,
) -> tuple[str, ToolExecutionRecord | None]:
    """Execute a tool-based plan step.

    Uses the LLM to determine tool arguments, then executes the tool.

    Args:
        usage: Optional accumulator to count tokens from the LLM call.

    Returns:
        A ``(result_text, tool_record)`` tuple. ``tool_record`` is ``None``
        if the tool could not be invoked.
    """
    completed = format_completed_steps(plan)
    exec_prompt = EXECUTION_PROMPT.format(
        step_number=plan_step.number,
        plan_text=format_plan(plan),
        completed_steps=completed or "(none yet)",
        step_description=plan_step.description,
    )
    messages = build_chat_messages_from_dict(
        original_message,
        history,
        system_prompt + exec_prompt,
    )

    llm_text = await call_llm(llm, messages, timeout=llm_timeout, usage=usage)
    if llm_text is None:
        plan_step.status = PlanStepStatus.FAILED
        return "LLM returned empty response", None

    # Parse tool call from LLM response
    tool_name, tool_args = extract_tool_call(llm_text)
    if tool_name is None:
        tool_name = plan_step.tool_name
    if not tool_args:
        tool_args = plan_step.tool_args or {}

    # Execute the tool
    if tool_name and tool_name in tool_map:
        record = await run_tool(tool_name, tool_args, tool_map, timeout=tool_timeout)
        if record.succeeded:
            result_text = str(record.result)
            plan_step.status = PlanStepStatus.COMPLETED
        else:
            result_text = f"Error: {record.error}"
            plan_step.status = PlanStepStatus.FAILED

        # Guard before truncation so detectors see the full content
        from quadkit.ai.agents.strategies.guard_hook import guard_observation

        result_text = await guard_observation(
            guard_pipeline, result_text, tool_name=tool_name
        )
        if len(result_text) > observation_max_chars:
            result_text = result_text[:observation_max_chars] + "\n[TRUNCATED]"
        return result_text, record

    return "Tool not found", None


async def execute_reasoning_step(
    llm: LLMClientProtocol,
    plan_step: PlanStep,
    plan: list[PlanStep],
    original_message: str,
    history: list[dict[str, Any]],
    system_prompt: str,
    *,
    llm_timeout: float,
    observation_max_chars: int,
    usage: TokenAccumulator | None = None,
    guard_pipeline: Any = None,
) -> str:
    """Execute a reasoning-only plan step via the LLM.

    Returns:
        The guarded observation text — the extracted ``STEP_RESULT:``
        value, or the raw LLM response when no marker is found — truncated
        to ``observation_max_chars``.  Args are the same as
        :func:`execute_tool_step` plus ``usage``.
    """
    completed = format_completed_steps(plan)
    exec_prompt = EXECUTION_PROMPT.format(
        step_number=plan_step.number,
        plan_text=format_plan(plan),
        completed_steps=completed or "(none yet)",
        step_description=plan_step.description,
    )
    messages = build_chat_messages_from_dict(
        original_message,
        history,
        system_prompt + exec_prompt,
    )

    llm_text = await call_llm(llm, messages, timeout=llm_timeout, usage=usage)
    if llm_text is None:
        return "(LLM returned empty response)"

    result = extract_step_result(llm_text)
    result_text = result if result else llm_text

    # Guard before truncation so detectors see the full content
    from quadkit.ai.agents.strategies.guard_hook import guard_observation

    result_text = await guard_observation(
        guard_pipeline, result_text, tool_name="reasoning"
    )
    if len(result_text) > observation_max_chars:
        result_text = result_text[:observation_max_chars]
    return result_text


# ---------------------------------------------------------------------------
# Replanning
# ---------------------------------------------------------------------------


async def replan(
    llm: LLMClientProtocol,
    plan: list[PlanStep],
    failed_step: PlanStep,
    error: str,
    original_message: str,
    history: list[dict[str, Any]],
    system_prompt: str,
    *,
    llm_timeout: float,
    usage: TokenAccumulator | None = None,
) -> list[PlanStep]:
    """Ask the LLM to replan after a step failure.

    Args:
        llm: LLM client.
        plan: The current plan (may include already-completed steps).
        failed_step: The step that failed.
        error: Opaque error text from the failed step. It is intentionally not
            interpolated into the replan prompt because it may contain private
            paths, credentials, or provider-controlled details.
        original_message: The original user message.
        history: Conversation history.
        system_prompt: System prompt to prepend.
        llm_timeout: Timeout for the LLM call.
        usage: Optional accumulator to count tokens from the LLM call.

    Returns:
        A list of new ``PlanStep`` objects renumbered from after ``failed_step``.
        Empty list if replanning failed.
    """
    completed = format_completed_steps(plan)
    remaining = "\n".join(
        f"{s.number}. {s.description}"
        for s in plan
        if s.number > failed_step.number and s.status == PlanStepStatus.PENDING
    )

    replan_text = REPLAN_PROMPT.format(
        failed_step=failed_step.number,
        plan_text=format_plan(plan),
        completed_steps=completed or "(none)",
        remaining_steps=remaining or "(none)",
    )
    messages = build_chat_messages_from_dict(
        original_message,
        history,
        system_prompt + replan_text,
    )

    llm_text = await call_llm(llm, messages, timeout=llm_timeout, usage=usage)
    if llm_text is None:
        return []

    new_steps = parse_plan(llm_text)
    # Re-number from after the failed step
    offset = failed_step.number
    for i, step in enumerate(new_steps):
        step.number = offset + i + 1

    logger.info(
        "plan_execute_replan",
        failed_step=failed_step.number,
        new_steps=len(new_steps),
    )
    return new_steps


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------


async def synthesize(
    llm: LLMClientProtocol,
    original_message: str,
    plan: list[PlanStep],
    history: list[dict[str, Any]],
    system_prompt: str,
    *,
    llm_timeout: float,
    usage: TokenAccumulator | None = None,
) -> str:
    """Synthesize a final answer from all completed step results.

    Calls the LLM with a synthesis prompt. Falls back to concatenating
    step results if the LLM call fails.  ``usage`` is an optional
    accumulator for counting tokens from the LLM call.
    """
    all_results = "\n".join(
        f"Step {s.number} ({s.status}): {s.description}\n  Result: {s.result or '(no result)'}"
        for s in plan
        if s.status != "skipped"
    )

    synthesis_prompt = SYNTHESIS_PROMPT.format(
        original_task=original_message,
        all_results=all_results,
    )
    messages = build_chat_messages_from_dict(
        original_message,
        history,
        system_prompt + synthesis_prompt,
    )

    llm_text = await call_llm(llm, messages, timeout=llm_timeout, usage=usage)
    if llm_text is None:
        return (
            "\n".join(
                s.result
                for s in plan
                if s.result and s.status == PlanStepStatus.COMPLETED
            )
            or "Unable to synthesize a final answer."
        )

    final = extract_final_answer(llm_text)
    return final if final else llm_text


__all__ = [
    "call_llm",
    "execute_reasoning_step",
    "execute_tool_step",
    "replan",
    "run_tool",
    "synthesize",
]
