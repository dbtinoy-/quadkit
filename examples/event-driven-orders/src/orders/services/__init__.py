"""Service layer for the event-driven orders demo.

Convention: the services package contains the facade that controllers
use to interact with the domain.  The facade owns the wiring between
the command bus, event bus, read model, and outbox.
"""

from __future__ import annotations

from orders.services.orders_api import OrdersApi

__all__ = ["OrdersApi"]
