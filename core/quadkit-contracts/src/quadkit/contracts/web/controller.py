"""Web framework controller protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ControllerProtocol(Protocol):
    """Structural protocol for controller objects.

    Defines the minimum surface expected of any controller: the ability
    to enumerate its declared routes.  Type-check against this protocol
    instead of the concrete ``Controller`` base class where possible.
    """

    @classmethod
    def collect_routes(cls) -> list[dict[str, Any]]:
        """Return route-definition dictionaries declared on this controller."""
        ...


__all__ = ["ControllerProtocol"]
