"""Fake unit-of-work for tracking entity changes in tests without persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    import types

    from quadkit.testing.fakes.events import FakeEventBus

__all__ = ["FakeUnitOfWork"]


class FakeUnitOfWork:
    """Tracks entity changes and events without persistence.

    Optionally integrates with :class:`FakeEventBus` to dispatch
    collected events on commit.

    Example::

        async with FakeUnitOfWork() as uow:
            uow.register_new(user)
            uow.register_event(UserCreated(user_id=user.user_id))
        assert uow.committed
    """

    def __init__(self, event_bus: FakeEventBus | None = None) -> None:
        self.new: list[Any] = []
        self.dirty: list[Any] = []
        self.deleted: list[Any] = []
        self.events: list[Any] = []
        self.committed: bool = False
        self.rolled_back: bool = False
        self._event_bus = event_bus

    def register_new(self, entity: Any) -> None:
        """Mark *entity* as newly created."""
        self.new.append(entity)

    def register_dirty(self, entity: Any) -> None:
        """Mark *entity* as modified."""
        self.dirty.append(entity)

    def register_deleted(self, entity: Any) -> None:
        """Mark *entity* as deleted."""
        self.deleted.append(entity)

    def register_event(self, event: Any) -> None:
        """Queue *event* for dispatch on commit."""
        self.events.append(event)

    def collect_events(self) -> list[Any]:
        """Return all queued events without consuming them."""
        return list(self.events)

    async def commit(self) -> None:
        """Mark as committed and optionally publish queued events."""
        self.committed = True
        if self._event_bus is not None:
            for event in self.events:
                await self._event_bus.publish(event)

    async def rollback(self) -> None:
        """Mark as rolled back and clear all tracked changes."""
        self.rolled_back = True
        self.new.clear()
        self.dirty.clear()
        self.deleted.clear()
        self.events.clear()

    async def __aenter__(self) -> Self:
        """Enter the unit-of-work context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Commit on clean exit, rollback on exception."""
        if exc_type is not None:
            await self.rollback()
        elif not self.committed:
            await self.commit()
