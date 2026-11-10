"""Support helpers for the native function-calling strategy.

Extracted from ``function_calling`` so the strategy module stays focused on
the reasoning loop: tool execution with timeout/retry, argument parsing,
guard-before-truncate observation finalization, and memory-context retrieval.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from quadkit.ai.agents.strategies.guard_hook import guard_observation
from quadkit.ai.agents.types import ReasoningStep, ToolExecutionRecord
from quadkit.contracts.ai.agents import ToolProtocol
from quadkit.contracts.ai.llm import ChatMessage, Role
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import loads_str

if TYPE_CHECKING:
    from quadkit.ai.agents.strategies.function_calling import FunctionCallingStrategy
    from quadkit.contracts.ai.agents import MemoryProtocol
    from quadkit.contracts.ai.guards import GuardPipelineProtocol

logger = get_logger(__name__)

_SYSTEM_SUFFIX = """
You are a function-calling assistant. Use the tools available to you to
complete the user's request. The tool schema is enforced by the model, so
request tools through native function calls rather than free text.

## Rules
- Call a tool when you need information you do not already have.
- Read each tool result before deciding the next step.
- Once the request is satisfied, answer the user directly in natural language.
"""

_OBSERVATION_TEMPLATE = "OBSERVATION: {observation}"


def parse_tool_args(raw: Any) -> dict[str, Any]:
    """Parse tool-call arguments that may arrive JSON-encoded or as a dict."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = loads_str(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


async def execute_tool_with_retry(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_map: dict[str, ToolProtocol],
    *,
    tool_timeout: float,
    tool_max_retries: int,
) -> ToolExecutionRecord:
    """Execute a tool with timeout and retry on transient errors."""
    if tool_name not in tool_map:
        return ToolExecutionRecord(
            tool_name=tool_name,
            arguments=tool_args,
            error="Unknown tool",
        )

    tool = tool_map[tool_name]
    start = time.monotonic()
    last_error: BaseException | None = None

    for attempt in range(tool_max_retries):
        try:
            output = await asyncio.wait_for(
                tool.execute(**tool_args),
                timeout=tool_timeout,
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
                error=f"Tool execution timed out after {tool_timeout}s",
                duration_ms=duration,
            )
        except (ConnectionError, OSError) as exc:
            last_error = exc
            logger.warning(
                "function_calling_tool_transient_error",
                attempt=attempt + 1,
                error_type=type(exc).__name__,
            )
            if attempt < tool_max_retries - 1:
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
            f"Tool execution failed after {tool_max_retries} retries "
            f"({last_error_type})"
        ),
        duration_ms=duration,
    )


async def finalize_observation(
    pipeline: GuardPipelineProtocol | None,
    observation: str,
    *,
    tool_name: str,
    max_chars: int,
) -> str:
    """Guard an observation, then truncate it to ``max_chars``."""
    observation = await guard_observation(pipeline, observation, tool_name=tool_name)
    if len(observation) > max_chars:
        observation = observation[:max_chars] + "\n[TRUNCATED]"
    return observation


async def handle_text_tool(
    strategy: FunctionCallingStrategy,
    tool_name: str,
    tool_args: dict[str, Any],
    content: str,
    iteration: int,
    messages: list[ChatMessage],
    steps: list[ReasoningStep],
    tool_records: list[ToolExecutionRecord],
    tool_map: dict[str, ToolProtocol],
    guard_pipeline: Any = None,
) -> None:
    """Execute a tool requested through text markers (fallback path)."""
    record = await execute_tool_with_retry(
        tool_name,
        tool_args,
        tool_map,
        tool_timeout=strategy.tool_timeout,
        tool_max_retries=strategy.tool_max_retries,
    )
    tool_records.append(record)

    observation = str(record.result) if record.succeeded else f"Error: {record.error}"
    # Guard before truncation so detectors see the full content
    observation = await finalize_observation(
        guard_pipeline,
        observation,
        tool_name=tool_name,
        max_chars=strategy.observation_max_chars,
    )

    steps.append(
        ReasoningStep(
            step_number=iteration,
            thought=content,
            action=tool_name,
            tool_call=record,
            observation=observation,
        )
    )
    messages.append(ChatMessage(role=Role.ASSISTANT, content=content))
    messages.append(
        ChatMessage(
            role=Role.USER,
            content=_OBSERVATION_TEMPLATE.format(observation=observation),
        )
    )


async def get_memory_context(memory: MemoryProtocol | None) -> str:
    """Retrieve context from the memory backend if available."""
    if memory is None:
        return ""
    try:
        past_messages = await memory.get_messages()
        if past_messages:
            context_str = "\n".join(str(m) for m in past_messages[-5:])
            return f"\n\nRelevant context from memory:\n{context_str}"
    except Exception:  # noqa: BLE001 — observation recording is best-effort
        pass
    return ""
