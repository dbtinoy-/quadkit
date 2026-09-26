"""Persistence layer for the event-driven orders demo.

Convention: the repository package contains the write-side data store
(order_repository.py) and the transactional outbox (outbox.py).  Both
are in-memory for the demo; production apps swap for database-backed
implementations.
"""

from __future__ import annotations

from orders.repository.order_repository import OrderRepository
from orders.repository.outbox import Outbox, OutboxError, OutboxRecord

__all__ = ["OrderRepository", "Outbox", "OutboxError", "OutboxRecord"]
