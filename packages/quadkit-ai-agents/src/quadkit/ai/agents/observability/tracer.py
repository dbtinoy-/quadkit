"""Agent distributed tracing for observability.

Integrates with ``quadkit-monitor`` (if available) to provide:
- Distributed tracing spans for the reasoning loop
- Per-tool call spans
- Per-LLM call spans
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from quadkit.ai.agents.constants import (
    SPAN_AGENT_EXECUTE,
    SPAN_AGENT_LLM,
    SPAN_AGENT_TOOL,
)
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.contracts.observability.tracing import TracerProtocol


class AgentTracer:
    """Distributed tracing for agent execution.

    Delegates to ``TracerProtocol`` from ``quadkit-monitor`` if
    available, otherwise operates as a no-op.
    """

    def __init__(self, tracer: TracerProtocol | None = None) -> None:
        self._tracer = tracer

    @asynccontextmanager
    async def trace_execution(
        self,
        agent_name: str,
        message: str,
        session_id: str | None = None,
    ) -> AsyncIterator[Any]:
        """Create a span for the entire agent execution."""
        if not self._tracer:
            yield None
            return

        span = self._tracer.start_span(
            f"{SPAN_AGENT_EXECUTE}.{agent_name}",
            attributes={
                "agent.name": agent_name,
                "agent.session_id": session_id or "",
                "agent.message_length": len(message),
            },
        )

        try:
            yield span
        except Exception as e:  # tracing instrumentation layer re-raises all exceptions
            if hasattr(span, "record_exception"):
                span.record_exception(e)
            if hasattr(span, "set_status"):
                span.set_status("ERROR")
            raise
        finally:
            if hasattr(span, "end"):
                span.end()

    @asynccontextmanager
    async def trace_tool_call(
        self,
        agent_name: str,
        tool_name: str,
    ) -> AsyncIterator[Any]:
        """Create a span for a tool call."""
        if not self._tracer:
            yield None
            return

        span = self._tracer.start_span(
            f"{SPAN_AGENT_TOOL}.{tool_name}",
            attributes={
                "agent.name": agent_name,
                "tool.name": tool_name,
            },
        )

        try:
            yield span
        except Exception as e:  # tracing instrumentation layer re-raises all exceptions
            if hasattr(span, "record_exception"):
                span.record_exception(e)
            raise
        finally:
            if hasattr(span, "end"):
                span.end()

    @asynccontextmanager
    async def trace_llm_call(
        self,
        agent_name: str,
        iteration: int,
    ) -> AsyncIterator[Any]:
        """Create a span for an LLM reasoning call."""
        if not self._tracer:
            yield None
            return

        span = self._tracer.start_span(
            f"{SPAN_AGENT_LLM}.{agent_name}",
            attributes={
                "agent.name": agent_name,
                "agent.iteration": iteration,
            },
        )

        try:
            yield span
        except Exception as e:  # tracing instrumentation layer re-raises all exceptions
            if hasattr(span, "record_exception"):
                span.record_exception(e)
            raise
        finally:
            if hasattr(span, "end"):
                span.end()


__all__ = ["AgentTracer"]
