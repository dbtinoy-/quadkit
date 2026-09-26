"""Root hook payload surface for quadkit-http.

Defines canonical payload dataclasses for outbound HTTP client hook points.
Actual hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "HTTPRequestSentHook",
    "HTTPResponseReceivedHook",
]


@dataclass(frozen=True, kw_only=True)
class HTTPRequestSentHook:
    """Payload fired when an outbound HTTP request is dispatched.

    Attributes:
        method: HTTP verb in upper-case (e.g. ``"GET"``).
        url: Full URL of the outbound request.
    """

    method: str
    url: str


@dataclass(frozen=True, kw_only=True)
class HTTPResponseReceivedHook:
    """Payload fired when an outbound HTTP response is received.

    Attributes:
        method: HTTP verb of the originating request.
        url: URL that was requested.
        status_code: HTTP status code of the received response.
    """

    method: str
    url: str
    status_code: int
