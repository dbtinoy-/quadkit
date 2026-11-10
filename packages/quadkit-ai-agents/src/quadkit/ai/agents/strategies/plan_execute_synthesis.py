"""Direct-response synthesis fallback for the Plan-and-Execute strategy."""

from __future__ import annotations

import time

from quadkit.ai.agents.strategies.plan_execute_planner import extract_final_answer
from quadkit.ai.agents.strategies.token_utils import TokenAccumulator
from quadkit.ai.agents.types import ReasoningStep, ToolExecutionRecord
from quadkit.contracts.ai.agents import AgentError, AgentResponse
from quadkit.result import Ok, Result


def build_direct_response(
    initial_response: str,
    steps: list[ReasoningStep],
    tool_calls: list[ToolExecutionRecord],
    start_time: float,
    usage: TokenAccumulator,
) -> Result[AgentResponse, AgentError]:
    """Build the fallback response when no structured plan could be parsed.

    Treats the initial LLM response as the final answer and records a
    direct-response reasoning step on the trace.

    Args:
        initial_response: Raw LLM response produced during planning.
        steps: Reasoning trace to append the direct-response step to.
        tool_calls: Tool call records collected so far.
        start_time: Monotonic timestamp captured at execution start.
        usage: Token accumulator holding usage for the run.

    Returns:
        ``Ok(AgentResponse)`` carrying the direct answer and reasoning trace.
    """
    final = extract_final_answer(initial_response)
    answer = final if final else initial_response

    steps.append(
        ReasoningStep(
            step_number=1,
            thought="No structured plan generated — using direct response",
            action="direct",
            observation=answer,
        )
    )

    elapsed = (time.monotonic() - start_time) * 1000
    return Ok(
        AgentResponse(
            message=answer,
            steps=steps,
            tool_calls=tool_calls,
            total_tokens=usage.total_tokens,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            duration_ms=elapsed,
            metadata={"strategy": "plan_and_execute", "direct_response": True},
        )
    )


__all__ = ["build_direct_response"]
