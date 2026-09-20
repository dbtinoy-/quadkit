from __future__ import annotations

from typing import Any, cast


def sse_endpoint(
    path: str,
    *,
    heartbeat_interval: int | None = None,
    retry: int | None = None,
) -> Any:
    """Decorator to mark a class as an SSE endpoint.

    This decorator registers the handler class with the router
    and configures the SSE path.

    Args:
        path: URL path for the SSE endpoint (can include path parameters)
        heartbeat_interval: Override default heartbeat interval
        retry: Override default client retry interval

    Example:
        ```python
        @sse_endpoint("/events/{channel}")
        class ChannelEventsHandler(AbstractSSEHandler):
            async def stream(self, request):
                channel = request.path_params["channel"]
                async for event in get_events(channel):
                    yield event
        ```
    """

    def decorator(cls: type) -> type:
        # Store route metadata on the class using setattr to satisfy mypy
        cast("Any", cls)._sse_path = path
        cast("Any", cls)._sse_metadata = {
            "path": path,
            "heartbeat_interval": heartbeat_interval,
            "retry": retry,
        }

        # Override class attributes if provided
        if heartbeat_interval is not None:
            cast("Any", cls).heartbeat_interval = heartbeat_interval
        if retry is not None:
            cast("Any", cls).retry = retry

        # Mark as SSE handler for router discovery
        cast("Any", cls)._is_sse_handler = True

        return cls

    return decorator


__all__ = ["sse_endpoint"]
