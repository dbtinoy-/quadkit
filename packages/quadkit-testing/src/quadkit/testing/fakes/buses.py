"""Fake command and query buses for test-time dispatch assertions."""

from __future__ import annotations

from typing import Any, TypeVar

__all__ = ["FakeCommandBus", "FakeQueryBus"]

T = TypeVar("T")


class FakeCommandBus:
    """Records dispatched commands for test assertions.

    Satisfies a ``CommandBusProtocol`` interface: ``register()`` + ``dispatch()``.

    Example::

        bus = FakeCommandBus()
        await bus.dispatch(CreateUser(email="a@example.com"))
        bus.assert_dispatched(CreateUser, count=1)
    """

    def __init__(self) -> None:
        self._dispatched: list[Any] = []
        self._handlers: dict[type, Any] = {}

    def register(self, command_type: type, handler: Any) -> None:
        """Register *handler* for *command_type*."""
        self._handlers[command_type] = handler

    async def dispatch(self, command: Any) -> Any:
        """Record *command* and invoke any registered handler."""
        self._dispatched.append(command)
        handler = self._handlers.get(type(command))
        if handler is not None:
            return await handler.handle(command)
        return None

    @property
    def dispatched(self) -> list[Any]:
        """All dispatched commands."""
        return list(self._dispatched)

    def dispatched_of_type(self, command_type: type[T]) -> list[T]:
        """Return dispatched commands of *command_type*."""
        return [c for c in self._dispatched if isinstance(c, command_type)]

    def assert_dispatched(
        self,
        command_type: type[T],
        count: int | None = None,
    ) -> None:
        """Assert *command_type* was dispatched, optionally *count* times."""
        matching: list[T] = self.dispatched_of_type(command_type)
        if not matching:
            msg = f"Expected {command_type.__name__} to be dispatched but found none"
            raise AssertionError(msg)
        if count is not None and len(matching) != count:
            msg = (
                f"Expected {count} {command_type.__name__} dispatch(es) "
                f"but found {len(matching)}"
            )
            raise AssertionError(msg)

    def assert_not_dispatched(self, command_type: type[T]) -> None:
        """Assert *command_type* was NOT dispatched."""
        matching: list[T] = self.dispatched_of_type(command_type)
        if matching:
            msg = (
                f"Expected {command_type.__name__} to NOT be dispatched "
                f"but found {len(matching)}"
            )
            raise AssertionError(msg)

    def clear(self) -> None:
        """Reset all recorded dispatches."""
        self._dispatched.clear()


class FakeQueryBus:
    """Records executed queries and returns configured canned results.

    Example::

        bus = FakeQueryBus()
        bus.when(GetUser, return_value=user)
        result = await bus.execute(GetUser(user_id="123"))
        assert result == user
    """

    def __init__(self) -> None:
        self._executed: list[Any] = []
        self._handlers: dict[type, Any] = {}
        self._canned: dict[type, Any] = {}

    def register(self, query_type: type, handler: Any) -> None:
        """Register *handler* for *query_type*."""
        self._handlers[query_type] = handler

    def when(self, query_type: type, return_value: Any) -> None:
        """Configure a canned response to return for *query_type*."""
        self._canned[query_type] = return_value

    async def execute(self, query: Any) -> Any:
        """Record and execute *query*, returning canned results first."""
        self._executed.append(query)
        qt = type(query)
        if qt in self._canned:
            return self._canned[qt]
        handler = self._handlers.get(qt)
        if handler is not None:
            return await handler.handle(query)
        return None

    @property
    def executed(self) -> list[Any]:
        """All executed queries."""
        return list(self._executed)

    def executed_of_type(self, query_type: type[T]) -> list[T]:
        """Return executed queries of *query_type*."""
        return [q for q in self._executed if isinstance(q, query_type)]

    def clear(self) -> None:
        """Reset all recorded executions."""
        self._executed.clear()
