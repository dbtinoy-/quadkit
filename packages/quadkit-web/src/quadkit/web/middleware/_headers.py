"""Shared header-lookup helpers for the ASGI middleware stack.

Middleware that needs one or two headers per request must not materialise
a ``dict(scope["headers"])`` — that allocates on every request.  These
helpers scan the raw ASGI header list linearly instead.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.types import Scope

__all__ = ["get_header", "sanitize_request_id"]


def get_header(scope: Scope, name: bytes) -> bytes | None:
    """Return the first value for *name* from the raw ASGI header list.

    Args:
        scope: The ASGI connection scope.
        name: Lowercase header name (ASGI headers are always lowercase).

    Returns:
        The first matching raw header value, or ``None`` when absent.
    """
    for key, value in scope.get("headers") or ():
        if key == name:
            return value
    return None

_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


def sanitize_request_id(value: str | None) -> str | None:
    """Return *value* when it is a safe inbound request id, else ``None``.

    Inbound request ids are client-controlled (plans/09172026 H-01): accept
    only short tokens of URL-safe characters so log streams cannot be
    injected with newlines or control characters and response headers cannot
    be padded with oversized or hostile values. Callers fall back to a
    generated id when this returns ``None``; the rejected value is never
    echoed anywhere.

    Args:
        value: Decoded inbound request id (``None`` when absent).

    Returns:
        The value unchanged when safe, otherwise ``None``.
    """
    if value is None or not 1 <= len(value) <= 64:
        return None
    if _REQUEST_ID_RE.fullmatch(value):
        return value
    return None
