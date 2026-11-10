"""Mounted leaves require the ASGI callable surface, not a router surface."""

from collections.abc import Awaitable, Callable
from typing import Any, get_type_hints

from quadkit.contracts.web import HTTPApplicationProtocol


def test_mount_accepts_an_asgi_callable_without_route_registration() -> None:
    """Keep the mount argument narrower in capability than its routing host."""
    hints = get_type_hints(
        HTTPApplicationProtocol.mount,
        localns={"Callable": Callable, "Awaitable": Awaitable},
    )
    assert hints["app"] == Callable[[dict[str, Any], Any, Any], Awaitable[None]]
