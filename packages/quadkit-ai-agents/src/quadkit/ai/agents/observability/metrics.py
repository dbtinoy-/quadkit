"""Agent metrics collection for observability.

Integrates with ``quadkit-monitor`` (if available) to provide:
- Per-agent execution metrics (duration, token usage, tool calls)
- Per-tool call metrics (duration, success/failure)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.ai.agents.constants import (
    METRIC_AGENT_EXECUTION_DURATION_MS,
    METRIC_AGENT_EXECUTION_STEPS,
    METRIC_AGENT_EXECUTION_TOKENS,
    METRIC_AGENT_EXECUTION_TOOL_CALLS,
    METRIC_AGENT_EXECUTIONS_ERRORS,
    METRIC_AGENT_EXECUTIONS_TOTAL,
    METRIC_AGENT_GOVERNANCE_DENIED,
    METRIC_AGENT_TOOL_CALL_DURATION_MS,
    METRIC_AGENT_TOOL_CALLS_FAILED,
    METRIC_AGENT_TOOL_CALLS_FAILURE,
    METRIC_AGENT_TOOL_CALLS_SUCCESS,
    METRIC_AGENT_TOOL_CALLS_TOTAL,
)
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from quadkit.ai.agents.types import ToolExecutionRecord
    from quadkit.contracts.ai.agents import AgentResponse
    from quadkit.contracts.observability.metrics import MetricsRecorderProtocol


class AgentMetrics:
    """Collects metrics for agent execution.

    Delegates to ``MetricsRecorderProtocol`` from ``quadkit-monitor`` if
    available, otherwise operates as a no-op.
    """

    def __init__(self, recorder: MetricsRecorderProtocol | None = None) -> None:
        self._recorder = recorder

    def record_execution(
        self,
        agent_name: str,
        response: AgentResponse,
    ) -> None:
        """Record metrics for a completed agent execution."""
        if not self._recorder:
            return

        tags = {"agent": agent_name}

        self._recorder.increment(METRIC_AGENT_EXECUTIONS_TOTAL, tags=tags)
        self._recorder.histogram(
            METRIC_AGENT_EXECUTION_DURATION_MS,
            response.duration_ms,
            tags=tags,
        )
        self._recorder.histogram(
            METRIC_AGENT_EXECUTION_TOKENS,
            float(response.total_tokens),
            tags=tags,
        )
        self._recorder.histogram(
            METRIC_AGENT_EXECUTION_STEPS,
            float(response.step_count),
            tags=tags,
        )
        self._recorder.histogram(
            METRIC_AGENT_EXECUTION_TOOL_CALLS,
            float(response.tool_call_count),
            tags=tags,
        )

        if response.failed_tool_calls:
            self._recorder.increment(
                METRIC_AGENT_TOOL_CALLS_FAILED,
                value=float(len(response.failed_tool_calls)),
                tags=tags,
            )

    def record_tool_call(
        self,
        agent_name: str,
        tool_call: ToolExecutionRecord,
    ) -> None:
        """Record metrics for a single tool call."""
        if not self._recorder:
            return

        tags = {"agent": agent_name, "tool": tool_call.tool_name}

        self._recorder.increment(METRIC_AGENT_TOOL_CALLS_TOTAL, tags=tags)
        self._recorder.histogram(
            METRIC_AGENT_TOOL_CALL_DURATION_MS,
            tool_call.duration_ms,
            tags=tags,
        )

        if tool_call.succeeded:
            self._recorder.increment(METRIC_AGENT_TOOL_CALLS_SUCCESS, tags=tags)
        else:
            self._recorder.increment(METRIC_AGENT_TOOL_CALLS_FAILURE, tags=tags)

    def record_error(
        self,
        agent_name: str,
        error_type: str,
    ) -> None:
        """Record an agent execution error."""
        if not self._recorder:
            return

        self._recorder.increment(
            METRIC_AGENT_EXECUTIONS_ERRORS,
            tags={"agent": agent_name, "error_type": error_type},
        )

    def record_governance_denied(self, agent_name: str) -> None:
        """Record a governance denial."""
        if not self._recorder:
            return

        self._recorder.increment(
            METRIC_AGENT_GOVERNANCE_DENIED,
            tags={"agent": agent_name},
        )


__all__ = ["AgentMetrics"]
