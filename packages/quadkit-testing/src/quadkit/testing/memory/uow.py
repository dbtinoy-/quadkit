"""Lightweight in-memory Unit of Work implementation.

Provides a concrete :class:`InMemoryUnitOfWork` that extends
:class:`~quadkit.domain.unit_of_work.AbstractUnitOfWork` with a no-op
:meth:`_flush` — suitable for unit tests and local development where no
database persistence is required.

For production, use a backend that overrides :meth:`_flush` to write to a
database (e.g. ``the optional provider``'s ``SQLUnitOfWork``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.domain.unit_of_work import AbstractUnitOfWork

if TYPE_CHECKING:
    from quadkit.contracts.events import EventBusProtocol


class InMemoryUnitOfWork(AbstractUnitOfWork):
    """In-memory Unit of Work with a no-op flush.

    All entity tracking, event collection, and context manager semantics are
    inherited from :class:`~quadkit.domain.unit_of_work.AbstractUnitOfWork`.
    This subclass only provides a concrete (no-op) :meth:`_flush` so the class
    is no longer abstract and can be instantiated directly.

    Args:
        event_bus: Optional event bus for publishing domain events on commit.

    Example::

        async with InMemoryUnitOfWork(event_bus=bus) as uow:
            uow.register_new(user)
            await uow.commit()
    """

    def __init__(self, event_bus: EventBusProtocol | None = None) -> None:
        super().__init__(event_bus=event_bus)

    async def _flush(self) -> None:
        """No-op flush — in-memory storage requires no persistence step."""


__all__ = ["InMemoryUnitOfWork"]
