"""Shared bearer-token auth helpers for quadkit-monitor ASGI middleware."""

from __future__ import annotations

from collections.abc import Callable
from hmac import compare_digest


def bearer_token_from_scope(scope: dict) -> bytes | None:
    """Extract the raw bearer token from the ASGI ``Authorization`` header.

    Reads ``scope["headers"]`` (a list of ``(name, value)`` byte tuples,
    names lower-cased by convention) and returns the value of an
    ``Authorization: Bearer <token>`` header.  Scopes without a
    ``"headers"`` key (as used by some tests) yield ``None``.

    Args:
        scope: ASGI connection scope.

    Returns:
        The raw token bytes, or ``None`` when the header is missing,
        uses a different scheme, or carries no token.
    """
    headers = scope.get("headers") or []
    for name, value in headers:
        if name.lower() != b"authorization":
            continue
        scheme, _, token = value.partition(b" ")
        if scheme.lower() == b"bearer" and token:
            if not isinstance(token, bytes):
                continue
            return token
    return None


def is_authorized(scope: dict, auth_token: str | None) -> bool:
    """Check whether a request may access the protected endpoint.

    Args:
        scope: ASGI connection scope.
        auth_token: Optional shared-secret token.  When ``None`` the
            endpoint stays open (the default posture, matching k8s
            probe and Prometheus scraping within a trusted network).

    Returns:
        ``True`` when no token is configured or the request carries
        ``Authorization: Bearer <auth_token>`` (compared in constant
        time); ``False`` on wrong or missing tokens.
    """
    if auth_token is None:
        return True
    token = bearer_token_from_scope(scope)
    return token is not None and compare_digest(token, auth_token.encode("utf-8"))


async def send_unauthorized(send: Callable) -> None:
    """Send an ASGI ``401`` response with a ``WWW-Authenticate: Bearer`` header.

    Args:
        send: ASGI send callable.
    """
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"text/plain"],
                [b"www-authenticate", b"Bearer"],
            ],
        },
    )
    await send({"type": "http.response.body", "body": b"Unauthorized"})
