"""Observable MCP handler wrappers — wire MCP operations to AIMetrics.

Wraps :class:`~quadkit.ai.mcp.server.handlers.tools.ToolHandler` and
:class:`~quadkit.ai.mcp.server.handlers.resources.ResourceHandler` to record
metrics for every tool call and resource read using
:class:`~the optional provider module`.

Metrics tracked:
- ``mcp_tool_calls_total``         — counter keyed by tool name + status
- ``mcp_tool_call_duration_seconds`` — histogram
- ``mcp_resource_reads_total``     — counter keyed by URI prefix + status
- ``mcp_errors_total``             — counter keyed by operation + error type

These are registered on the ``AIMetrics`` collector and follow the same naming
conventions as the rest of the optional provider.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from quadkit.contracts.mcp.exceptions import MCPError
from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.ai.mcp.server.handlers.resources import ResourceHandler
    from quadkit.ai.mcp.server.handlers.tools import ToolHandler
    from quadkit.contracts.observability.ai import AIMetricsProtocol
    from quadkit.result import Result

logger = get_logger(__name__)


class ObservableToolHandler:
    """Delegates to an inner ``ToolHandler`` while recording metrics.

    Example::

        handler = ObservableToolHandler(tool_handler, metrics)
        result = await handler.call_tool("my_tool", {"arg": 1})
    """

    def __init__(self, inner: ToolHandler, metrics: AIMetricsProtocol) -> None:
        """Initialize the observable wrapper.

        Args:
            inner: The delegate tool handler.
            metrics: AIMetrics instance for recording observations.
        """
        self._inner = inner
        self._metrics = metrics
        self._tool_calls_total = metrics._collector.create_counter(  # type: ignore[attr-defined]
            name="mcp_tool_calls_total",
            description="Total MCP tool calls by name and status",
        )
        self._tool_duration = metrics._collector.create_histogram(  # type: ignore[attr-defined]
            name="mcp_tool_call_duration_seconds",
            description="MCP tool call duration in seconds",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )
        self._errors_total = metrics._collector.create_counter(  # type: ignore[attr-defined]
            name="mcp_errors_total",
            description="Total MCP errors by operation",
        )

    async def list_tools(self) -> dict[str, Any]:
        """Delegate to inner handler."""
        return await self._inner.list_tools()  # type: ignore[return-value]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Result[dict[str, Any], MCPError]:
        """Observe call_tool and delegate.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            Result from the inner handler.
        """
        start = time.monotonic()
        result = await self._inner.call_tool(name, arguments)
        elapsed = time.monotonic() - start

        status = "success" if result.is_ok() else "error"
        self._tool_calls_total.increment(labels={"tool": name, "status": status})
        self._tool_duration.observe(value=elapsed, labels={"tool": name})

        if result.is_err():
            error = result.unwrap_err()
            self._errors_total.increment(
                labels={
                    "operation": "tool_call",
                    "error_type": type(error).__name__,
                }
            )
            logger.debug(
                "mcp_tool_call_observed",
                tool=name,
                status=status,
                duration=elapsed,
                error_type=type(error).__name__,
            )
        else:
            logger.debug(
                "mcp_tool_call_observed",
                tool=name,
                status=status,
                duration=elapsed,
            )

        return result


class ObservableResourceHandler:
    """Delegates to an inner ``ResourceHandler`` while recording metrics.

    Example::

        handler = ObservableResourceHandler(resource_handler, metrics)
        data = await handler.read_resource("file://path/to/file")
    """

    def __init__(self, inner: ResourceHandler, metrics: AIMetricsProtocol) -> None:
        """Initialize the observable wrapper.

        Args:
            inner: The delegate resource handler.
            metrics: AIMetrics instance for recording observations.
        """
        self._inner = inner
        self._metrics = metrics
        self._resource_reads_total = metrics._collector.create_counter(  # type: ignore[attr-defined]
            name="mcp_resource_reads_total",
            description="Total MCP resource reads by URI scheme and status",
        )
        self._errors_total = metrics._collector.create_counter(  # type: ignore[attr-defined]
            name="mcp_errors_total",
            description="Total MCP errors by operation",
        )

    async def list_resources(self) -> dict[str, Any]:
        """Delegate to inner handler."""
        return await self._inner.list_resources()  # type: ignore[return-value]

    async def list_templates(self) -> dict[str, Any]:
        """Delegate to inner handler."""
        return await self._inner.list_templates()  # type: ignore[return-value]

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Observe read_resource and delegate.

        Args:
            uri: Resource URI.

        Returns:
            Resource content dict from the inner handler.
        """
        scheme = uri.split("://", maxsplit=1)[0] if "://" in uri else "unknown"
        try:
            result = await self._inner.read_resource(uri)
            self._resource_reads_total.increment(
                labels={"scheme": scheme, "status": "success"}
            )
            return result  # type: ignore[return-value]
        except Exception as exc:  # noqa: BLE001 — metric recording is best-effort
            self._resource_reads_total.increment(
                labels={"scheme": scheme, "status": "error"}
            )
            self._errors_total.increment(
                labels={
                    "operation": "resource_read",
                    "error_type": type(exc).__name__,
                }
            )
            logger.debug(
                "mcp_resource_read_error",
                scheme=scheme,
                error_type=type(exc).__name__,
            )
            raise


__all__ = ["ObservableResourceHandler", "ObservableToolHandler"]
