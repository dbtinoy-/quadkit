from __future__ import annotations

from collections.abc import Callable
import time

from quadkit.monitor.middleware.auth import is_authorized, send_unauthorized
from quadkit.serialization import dumps


def _http_status_for(status: str) -> int:
    """Map health status string to HTTP status code.

    Returns:
        200 for healthy, 207 for degraded, 503 for unhealthy.
    """
    if status == "healthy":
        return 200
    if status == "degraded":
        return 207
    return 503


class HealthCheckProvider:
    """ASGI middleware that exposes a ``GET /health`` liveness/readiness endpoint.

    Intercepts requests to *path* and returns a JSON health-status payload.
    All other requests are passed through with a ``404`` response (or forwarded
    to the next ASGI app when composed in a middleware stack).

    The HTTP status code reflects the overall application health:

    * ``200`` — all checks healthy
    * ``207`` — at least one check degraded
    * ``503`` — at least one check unhealthy

    To add custom checks, subclass :class:`HealthCheckProvider` and override
    :meth:`check_health`.

    Args:
        path: URL path for the health endpoint.  Defaults to ``"/health"``.
        auth_token: Optional bearer token.  When set, requests must carry
            ``Authorization: Bearer <auth_token>`` or receive ``401``.
            Defaults to ``None`` (endpoint open).

    Example::

        from quadkit.monitor.middleware import HealthCheckProvider

        app = HealthCheckProvider(path="/ready")
        # Mount *app* in your ASGI server / router.
    """

    def __init__(self, path: str = "/health", auth_token: str | None = None) -> None:
        self.path = path
        self.auth_token = auth_token

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """Handle an ASGI HTTP request.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if (
            scope["type"] == "http"
            and scope["path"] == self.path
            and scope["method"] == "GET"
        ):
            if not is_authorized(scope, self.auth_token):
                await send_unauthorized(send)
                return
            health_status = await self.check_health()
            status_code = _http_status_for(health_status.get("status", "unhealthy"))
            await send(
                {
                    "type": "http.response.start",
                    "status": status_code,
                    "headers": [[b"content-type", b"application/json"]],
                },
            )
            await send({"type": "http.response.body", "body": dumps(health_status)})
        else:
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b"Not Found"})

    async def check_health(self) -> dict:
        """Return the current application health as a serialisable mapping.

        Override this method in a subclass to perform real dependency checks
        (database ping, cache ping, etc.).

        Returns:
            A ``dict`` with at minimum a ``"status"`` key (one of
            ``"healthy"``, ``"degraded"``, or ``"unhealthy"``) and a
            ``"timestamp"`` float.  Additional ``"checks"`` entries can be
            added by subclasses.
        """
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "checks": {"application": "up"},
        }
