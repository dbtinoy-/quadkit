"""Host-header validation middleware.

Rejects requests whose ``Host`` header does not match the configured
``SecurityConfig.allowed_hosts`` allowlist. Host-header poisoning enables
cache poisoning, password-reset link injection, and DNS-rebinding style
attacks — validation must fail closed.

Entries may describe a whole domain (``.example.com`` or ``*.example.com``)
so run-time-assigned hosts — platform preview domains, autoscaling fleets —
do not have to be enumerated in advance.

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

    Entries are exact hostnames unless prefixed, in which case they match a
    domain and its subdomains on a label boundary (Django ``ALLOWED_HOSTS``
    semantics — the form most deployment platforms need, where the host is
    assigned at run time and cannot be enumerated ahead of time):

    * ``api.example.com`` matches only that host.
    * ``.example.com`` matches ``example.com`` and any subdomain.
    * ``*.example.com`` matches any subdomain, but not the apex itself.

    A bare ``*`` is refused: an allowlist that permits every host provides no
    protection and silently defeats the validator, so misconfiguration fails
    at construction instead of at request time.

    Args:
        app: The ASGI application to wrap.
        allowed_hosts: Hostnames permitted (compared lower-cased, port
            stripped). An empty list rejects all hosts (fail-closed).

    Raises:
        ValueError: If an entry is a bare ``*`` or an empty suffix such as
            ``"."`` / ``"*."``.
    """

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self._app = app
        exact: set[str] = set()
        suffixes: list[tuple[str, bool]] = []
        for entry in allowed_hosts:
            host = entry.strip().lower()
            if host == "*":
                msg = (
                    "allowed_hosts entry '*' would accept every Host header; "
                    "list concrete hosts or a '.example.com' / '*.example.com' suffix"
                )
                raise ValueError(msg)
            if host.startswith("*."):
                suffix = host[2:]
                apex_allowed = False
            elif host.startswith("."):
                suffix = host[1:]
                apex_allowed = True
            else:
                exact.add(host)
                continue
            if not suffix:
                msg = f"allowed_hosts entry {entry!r} has an empty domain suffix"
                raise ValueError(msg)
            suffixes.append((suffix, apex_allowed))
        self._allowed_hosts = exact
        self._allowed_suffixes = tuple(suffixes)

    def _is_allowed(self, host: str) -> bool:
        """Return whether ``host`` matches an exact entry or a suffix entry."""
        if host in self._allowed_hosts:
            return True
        for suffix, apex_allowed in self._allowed_suffixes:
            if host == suffix:
                if apex_allowed:
                    return True
                continue
            # Label boundary: "evilexample.com" must not match "example.com".
            if host.endswith("." + suffix):
                return True
        return False

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
        if host is None or not self._is_allowed(host):
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
