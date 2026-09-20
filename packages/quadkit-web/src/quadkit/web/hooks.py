"""Root hook payload surface for quadkit-web.

Defines canonical payload dataclasses for web-related hook points. Actual
hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "WebRequestReceivedHook",
    "WebResponsePreparedHook",
    "WebServerStartedHook",
    "WebServerStoppedHook",
]


@dataclass(frozen=True, kw_only=True)
class WebRequestReceivedHook:
    """Payload fired when the ASGI server receives an incoming HTTP request.

    Attributes:
        path: URL path of the incoming request (e.g. ``"/api/users"``).
        method: HTTP verb in upper-case (e.g. ``"GET"``).
    """

    path: str
    method: str


@dataclass(frozen=True, kw_only=True)
class WebResponsePreparedHook:
    """Payload fired once a response has been assembled, before it is sent.

    Attributes:
        path: URL path the response belongs to.
        status_code: HTTP status code of the prepared response.
    """

    path: str
    status_code: int


@dataclass(frozen=True, kw_only=True)
class WebServerStartedHook:
    """Payload fired after the ASGI lifespan ``startup`` phase completes."""


@dataclass(frozen=True, kw_only=True)
class WebServerStoppedHook:
    """Payload fired after an orderly ASGI lifespan ``shutdown`` completes."""
