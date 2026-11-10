"""Shared guard hook for tool observations entering the LLM context (D3).

Called by every strategy at the OBSERVE boundary: the point a tool result
becomes a message the model will read. Content is checked with the input
side of the guard pipeline; a block aborts the run (fail-closed), redaction
is applied, and guard infrastructure errors are raised, never swallowed.

The executor passes its effectively-resolved pipeline to ``strategy.execute``
as a ``guard_pipeline`` kwarg; strategies hand it to :func:`guard_observation`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.ai.agents.exceptions import AgentExecutionError

if TYPE_CHECKING:
    from quadkit.contracts.ai.guards import GuardPipelineProtocol


class ToolObservationBlockedError(AgentExecutionError):
    """A guard blocked tool output from entering the model context."""

    _code = "QK_ERR_AGT_012"


class ToolObservationGuardError(AgentExecutionError):
    """The guard pipeline failed while checking tool output."""

    _code = "QK_ERR_AGT_013"


async def guard_observation(
    pipeline: GuardPipelineProtocol | None,
    content: str,
    *,
    tool_name: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Check *content* (a tool observation) against the pipeline's input guards.

    Args:
        pipeline: The effective guard pipeline (may be ``None`` for no-op).
        content: The raw tool result text about to enter the model context.
        tool_name: Name of the tool that produced the result (for metadata).
        metadata: Extra metadata merged under ``source=tool_observation``.

    Returns:
        The (possibly redacted) content to write into context.

    Raises:
        ToolObservationBlockedError: If a guard blocks the content.
        ToolObservationGuardError: If the pipeline itself fails — fail-closed.

    Example:
        ```python
        obs = await guard_observation(pipeline, obs_text, tool_name="web_fetch")
        messages.append(ChatMessage(role=Role.USER, content=_OBSERVATION_TEMPLATE.format(observation=obs)))
        ```
    """
    if pipeline is None:
        return content

    scope = {"source": "tool_observation", "tool_name": tool_name}
    if metadata:
        scope.update(metadata)

    try:
        result = await pipeline.check_input(content=content, metadata=scope)
    except Exception as exc:  # noqa: BLE001 — guard failures become ToolObservationGuardError
        raise ToolObservationGuardError(
            "Guard evaluation failed on tool observation",
            details={"error_type": type(exc).__name__},
        ) from None

    if result.is_err():
        guard_error = result.unwrap_err()
        raise ToolObservationGuardError(
            "Guard pipeline failed on tool observation",
            details={"error_type": type(guard_error).__name__},
        ) from None

    agg = result.unwrap()
    action = str(getattr(agg, "action", "pass"))
    blocked = bool(getattr(agg, "blocked", False)) or action == "block"
    if blocked:
        raise ToolObservationBlockedError("Tool output blocked by guards")
    if action not in {"pass", "warn", "redact"}:
        raise ToolObservationGuardError(
            "Guard pipeline returned an unknown action",
            details={"error_type": "UnknownGuardAction"},
        )

    final = getattr(agg, "final_content", content)
    if action == "redact" and not isinstance(final, str):
        raise ToolObservationGuardError(
            "Guard pipeline did not provide redacted tool content",
            details={"error_type": "MissingRedactedContent"},
        )
    if final is None:
        return content
    if not isinstance(final, str):
        raise ToolObservationGuardError(
            "Guard pipeline returned invalid tool content",
            details={"error_type": "InvalidGuardContent"},
        )
    return final
