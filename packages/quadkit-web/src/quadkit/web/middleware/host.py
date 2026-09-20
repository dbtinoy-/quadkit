"""Host-header validation middleware.

Rejects requests whose ``Host`` header does not match the configured
``SecurityConfig.allowed_hosts`` allowlist. Host-header poisoning enables
cache poisoning, password-reset link injection, and DNS-rebinding style
attacks — validation must fail closed.

An empty allowlist rejects every request, so the middleware is only wired by
``MiddlewareSetup`` when ``allowed_hosts`` is non-empty (the production
validator requires a non-empty list; in non-production deployments host
validation is opt-in via ``SecurityConfig.allowed_hosts``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class HostValidationMiddleware:
    """ASGI middleware enforcing an explicit host allowlist.

    Args:
        app: The ASGI application to wrap.
        allowed_hosts: Hostnames permitted (compared lower-cased, port
            stripped). An empty list rejects all hosts (fail-closed).
    """

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self._app = app
        self._allowed_hosts = {host.lower() for host in allowed_hosts}

    @staticmethod
    def _extract_host(scope: Scope) -> str | None:
        """Return the lower-cased hostname (port stripped) or ``None``."""
        host: str | None = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"host":
                host = value.decode("latin-1").strip().lower()
                break
        if host is None:
            return None
        if host.startswith("["):  # IPv6 literal
            if "]" in host:
                return host[1 : host.index("]")].lower()
            return None
        if ":" in host:
            candidate = host.rsplit(":", 1)
            if candidate[1].isdigit():
                return candidate[0]
        return host

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Validate the ``Host`` header before calling the wrapped app.

        Args:
            scope: The ASGI scope dictionary.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        host = self._extract_host(scope)
        if host is None or host not in self._allowed_hosts:
            await self._reject(send)
            return

        await self._app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send) -> None:
        """Send a plain 400 response."""
        body = b"400 Bad Request: invalid Host header"
        await send(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


__all__ = ["HostValidationMiddleware"]
