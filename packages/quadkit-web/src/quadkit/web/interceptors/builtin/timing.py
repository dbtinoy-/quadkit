"""Timing interceptor for performance measurement.

Adds Server-Timing header with handler execution time.
"""

from __future__ import annotations

from typing import Any

from quadkit.primitives import clock as ambient_clock
from quadkit.web.protocols import (
    CallHandlerProtocol,
    ExecutionContextProtocol,
    WebInterceptorProtocol,
)


class HandlerTimingInterceptor(WebInterceptorProtocol):
    """Interceptor that measures and reports request handling time.

    Adds Server-Timing header with the handler execution duration,
    useful for performance debugging and client-side profiling.

    Example:
        ```python
        # Add to global interceptors
        router.add_interceptor(HandlerTimingInterceptor())
        ```

    The Server-Timing header format:
        Server-Timing: handler;dur=12.5
    """

    def __init__(
        self,
        metric_name: str = "handler",
        precision: int = 1,
    ):
        """Initialize the timing interceptor.

        Args:
            metric_name: Name for the timing metric in Server-Timing header.
            precision: Number of decimal places for timing (default 1).
        """
        self._metric_name = metric_name
        self._precision = precision

    async def intercept(
        self,
        context: ExecutionContextProtocol,
        next_handler: CallHandlerProtocol,
    ) -> Any:
        """Intercept and measure handler execution time.

        Args:
            context: The execution context.
            next_handler: The next handler in the chain.

        Returns:
            The response from the handler, with timing header added.
        """
        start = ambient_clock.monotonic()

        try:
            result = await next_handler.handle()
        finally:
            elapsed = ambient_clock.monotonic() - start
            duration_ms = elapsed * 1000

            # Add Server-Timing header to response
            if result is not None:
                timing_value = (
                    f"{self._metric_name};dur={duration_ms:.{self._precision}f}"
                )

                # Add header to response if it has headers
                if hasattr(result, "headers"):
                    # Use a setdefault to avoid overwriting existing headers
                    if "server-timing" not in result.headers:
                        result.headers["Server-Timing"] = timing_value
                elif hasattr(result, "add_header"):
                    result.add_header("Server-Timing", timing_value)

        return result


__all__ = ["HandlerTimingInterceptor"]
