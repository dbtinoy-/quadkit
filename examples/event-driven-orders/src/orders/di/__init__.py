"""DI package for the event-driven orders demo.

Convention: the DI package contains the Provider that wires the
bounded context's services into the container.  One Provider per
bounded context; register() binds, boot() initializes.
"""

from __future__ import annotations

from orders.di.provider import OrdersProvider

__all__ = ["OrdersProvider"]
