"""Unit of Work protocol.

The Unit of Work pattern tracks changes to entities and
coordinates their persistence in a single transaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.domain.events import DomainEvent


@runtime_checkable
class UnitOfWorkProtocol(Protocol):
    """Protocol for Unit of Work pattern.

    Coordinates multiple repository operations within a single
    transaction boundary.

    Example:
        ```python
        async with uow:
            user = await uow.users.get(user_id)
            user.email = new_email
            await uow.users.save(user)
            await uow.audit_log.save(AuditEntry(...))
            await uow.commit()
        ```
    """

    async def __aenter__(self) -> Self:
        """Begin unit of work scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """End unit of work scope, rollback on exception."""
        ...

    async def commit(self) -> None:
        """Commit all changes in this unit of work."""
        ...

    async def rollback(self) -> None:
        """Rollback all changes in this unit of work."""
        ...

    # ------------------------------------------------------------------
    # Lifecycle hook API
    # ------------------------------------------------------------------

    def on_commit(self, callback: Callable[[], Any]) -> None:
        """Register a callback to run after a successful commit.

        The callback may be a plain function or a coroutine function (or a
        sync function returning an awaitable); awaitable results are awaited.
        """
        ...

    def on_rollback(self, callback: Callable[[], Any]) -> None:
        """Register a callback to run after a rollback.

        The callback may be a plain function or a coroutine function (or a
        sync function returning an awaitable); awaitable results are awaited.
        """
        ...

    def register_new(self, entity: Any) -> None:
        """Register a new entity for insertion."""
        ...

    # ------------------------------------------------------------------
    # Event collection API
    # ------------------------------------------------------------------

    def register_event(self, event: DomainEvent) -> None:
        """Register a domain event with this unit of work.

        Handlers or repositories may call this method when they detect that a
        domain event needs to be published once the transaction successfully
        commits.  The unit of work is responsible for retaining the events until
        they are gathered by the application and dispatched via an event bus.
        """
        ...

    def collect_events(self) -> list[DomainEvent]:
        """Return and clear all domain events registered with this unit of
        work.

        Calling this method yields the list of events that have been registered
        either explicitly via :meth:`register_event` or implicitly by the UoW
        when entities with ``collect_events`` semantics are registered.  The
        returned list is cleared from the unit of work; subsequent calls will
        return an empty list until more events are registered.
        """
        ...

    def register_dirty(self, entity: Any) -> None:
        """Register an entity for update."""
        ...

    def register_deleted(self, entity: Any) -> None:
        """Register an entity for deletion."""
        ...


__all__ = [
    "UnitOfWorkProtocol",
]
