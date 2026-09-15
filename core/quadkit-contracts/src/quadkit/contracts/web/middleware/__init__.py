"""Web middleware protocols."""

from __future__ import annotations

from quadkit.contracts.web.guard import GuardProtocol
from quadkit.contracts.web.middleware.protocols import ASGIMiddlewareProtocol
from quadkit.contracts.web.middleware.registry_protocol import (
    MiddlewareRegistryProtocol,
)

__all__ = ["ASGIMiddlewareProtocol", "GuardProtocol", "MiddlewareRegistryProtocol"]
