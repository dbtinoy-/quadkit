"""Abstract Unit of Work base class.

Provides the full Unit-of-Work implementation: entity tracking, domain-event
collection, and commit/rollback lifecycle hooks.  Concrete subclasses only
need to override :meth:`_flush` to persist tracked changes.

This base is deliberately storage-agnostic -- it imports no database driver --
so in-memory and SQL implementations can share it:

- ``quadkit.testing.memory.uow.InMemoryUnitOfWork`` supplies a no-op flush.
- ``quadkit-sql``'s ``SQLUnitOfWork`` flushes through the active session.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Self

from quadkit.contracts.data.outbox import OutboxStoreProtocol
from quadkit.contracts.data.sql.unit_of_work import UnitOfWorkProtocol
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from quadkit.contracts.domain.events import DomainEvent
    from quadkit.contracts.events import EventBusProtocol

logger = get_logger(__name__)


async def run_lifecycle_hooks(hooks: Sequence[Callable[[], Any]]) -> None:
    """Run lifecycle *hooks*, awaiting any awaitable results.

    Handles all callback styles uniformly: sync functions, coroutine
    functions, and sync functions returning an awaitable.
    """
    for hook in hooks:
        result = hook()
        if result is not None:
            await result


class AbstractUnitOfWork(UnitOfWorkProtocol):
    """Full Unit of Work implementation with pluggable flush semantics.

    Tracks entity changes (:meth:`register_new`, :meth:`register_dirty`,
    :meth:`register_deleted`) and domain events (:meth:`register_event`).
    On :meth:`commit`, outstanding changes are flushed via :meth:`_flush`,
    collected events are published via the optional ``event_bus``, and all
    tracking state is reset.  :meth:`rollback` discards state without
    flushing.

    Subclasses must override :meth:`_flush` to persist tracked changes to
    their storage backend.

    Args:
        event_bus: Optional event bus for publishing domain events on commit.

    Example::

        class SQLUnitOfWork(AbstractUnitOfWork):
            async def _flush(self) -> None:
                await self._session.flush()

        async with SQLUnitOfWork(event_bus=bus) as uow:
            uow.register_new(user)
            await uow.commit()
    """

    def __init__(
        self,
        event_bus: EventBusProtocol | None = None,
        outbox_store: OutboxStoreProtocol | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._outbox_store = outbox_store
        self._new: list[Any] = []
        self._dirty: list[Any] = []
        self._deleted: list[Any] = []
        self._events: list[DomainEvent] = []
        self._commit_hooks: list[Callable[[], Any]] = []
        self._rollback_hooks: list[Callable[[], Any]] = []
        self._committed = False

    # ------------------------------------------------------------------
    # Entity tracking
    # ------------------------------------------------------------------

    def register_new(self, entity: Any) -> None:
        """Track *entity* as newly created (to be inserted).

        Args:
            entity: The entity to mark as new.
        """
        self._new.append(entity)

    def register_dirty(self, entity: Any) -> None:
        """Track *entity* as modified in this unit of work.

        Args:
            entity: The entity to mark as dirty.
        """
        self._dirty.append(entity)

    def register_deleted(self, entity: Any) -> None:
        """Track *entity* as removed from this unit of work.

        Args:
            entity: The entity to mark as deleted.
        """
        self._deleted.append(entity)

    # ------------------------------------------------------------------
    # Event collection
    # ------------------------------------------------------------------

    def register_event(self, event: DomainEvent) -> None:
        """Collect a domain event to be published on :meth:`commit`.

        Args:
            event: The domain event to buffer.
        """
        self._events.append(event)

    def collect_events(self) -> list[DomainEvent]:
        """Return all collected events and those pulled from aggregate roots.

        Entities that expose a ``pull_events()`` method (e.g. aggregate roots)
        are harvested automatically.  The internal event list is **not** cleared
        here; it is cleared by :meth:`_clear` at the end of :meth:`commit` or
        :meth:`rollback`.

        Returns:
            All pending domain events.
        """
        events = list(self._events)
        for entity in (*self._new, *self._dirty):
            if hasattr(entity, "pull_events"):
                events.extend(entity.pull_events())
        return events

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_commit(self, callback: Callable[[], Any]) -> None:
        """Register a callback to run after a successful commit.

        The callback may be a plain function or a coroutine function (or a
        sync function returning an awaitable); awaitable results are awaited.
        """
        self._commit_hooks.append(callback)

    def on_rollback(self, callback: Callable[[], Any]) -> None:
        """Register a callback to run after a rollback.

        The callback may be a plain function or a coroutine function (or a
        sync function returning an awaitable); awaitable results are awaited.
        """
        self._rollback_hooks.append(callback)

    # ------------------------------------------------------------------
    # Commit / Rollback
    # ------------------------------------------------------------------

    async def commit(self) -> None:
        """Flush tracked changes and write domain events atomically to the outbox.

        If an outbox store is configured, events are written inside the same
        transaction as the business data (via :meth:`_flush`), eliminating the
        crash window between DB commit and event publish.  When no outbox store
        is present the legacy in-process publish path is used as a fallback.
        """
        events = self.collect_events()
        await self._flush()
        if events and self._outbox_store is not None:
            await self._outbox_store.append_batch(events)
        elif events:
            await self._publish_events(events)
        self._clear()
        self._committed = True
        logger.debug(
            "uow_committed",
            new=len(self._new),
            dirty=len(self._dirty),
            deleted=len(self._deleted),
            events=len(events),
        )
        await run_lifecycle_hooks(self._commit_hooks)

    async def rollback(self) -> None:
        """Discard all tracked changes and events without flushing."""
        count = len(self._new) + len(self._dirty) + len(self._deleted)
        self._clear()
        logger.debug("uow_rolled_back", discarded_entities=count)
        await run_lifecycle_hooks(self._rollback_hooks)

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        """Begin unit of work scope."""
        self._committed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Commit on success, roll back on exception."""
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()

    # ------------------------------------------------------------------
    # Extension point
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def _flush(self) -> None:
        """Persist all tracked entity changes to the backing store.

        The in-memory implementation is a no-op.  Database backends override
        this to flush to SQL/NoSQL storage.
        """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _publish_events(self, events: list[DomainEvent]) -> None:
        """Publish *events* via the configured event bus (if any).

        Args:
            events: Domain events to dispatch.
        """
        if self._event_bus is None:
            return
        for event in events:
            await self._event_bus.publish(event)

    def _clear(self) -> None:
        """Reset all entity-tracking and event-collection state."""
        self._new.clear()
        self._dirty.clear()
        self._deleted.clear()
        self._events.clear()


__all__ = ["AbstractUnitOfWork", "run_lifecycle_hooks"]
