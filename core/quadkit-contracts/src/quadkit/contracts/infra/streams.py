"""Typed async stream primitives."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Generic, TypeVar, cast

from quadkit.contracts.core.result import Result

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")
F = TypeVar("F")


class _StoredStreamError(Exception, Generic[E]):
    """Internal carrier for propagating typed stream failures."""

    _code: str = "QK_ERR_INFRA_011"
    error: E

    def __init__(self, error: E) -> None:
        super().__init__(str(error))
        self.error = error


class _StreamOk(Result[T, E]):
    """Private ``Ok`` implementation for contracts-only helpers."""

    def __init__(self, value: T) -> None:
        self._value = value

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self._value

    def unwrap_err(self) -> E:
        raise ValueError("Called unwrap_err() on Ok result")

    def unwrap_or(self, default: T) -> T:
        return self._value

    def unwrap_or_else(self, op: Callable[[E], T]) -> T:
        return self._value

    def map_sync(self, op: Callable[[T], U]) -> Result[U, E]:
        return _StreamOk(op(self._value))

    def map_err(self, op: Callable[[E], F]) -> Result[T, F]:
        return cast("Result[T, F]", self)

    def and_then_sync(self, op: Callable[[T], Result[U, E]]) -> Result[U, E]:
        return op(self._value)

    def or_else_sync(self, op: Callable[[E], Result[T, F]]) -> Result[T, F]:
        return cast("Result[T, F]", self)

    def expect(self, message: str) -> T:
        return self._value

    def match(self, ok: Callable[[T], U], err: Callable[[E], U]) -> U:
        return ok(self._value)

    async def map(self, op: Callable[[T], Awaitable[U]]) -> Result[U, E]:
        return _StreamOk(await op(self._value))

    async def and_then(
        self, op: Callable[[T], Awaitable[Result[U, E]]]
    ) -> Result[U, E]:
        return await op(self._value)

    async def or_else(self, op: Callable[[E], Awaitable[Result[T, F]]]) -> Result[T, F]:
        return cast("Result[T, F]", self)

    def flatten(self) -> Result[Any, E]:
        if isinstance(self._value, Result):
            return self._value
        return cast("Result[Any, E]", self)

    def filter(self, predicate: Callable[[T], bool], error: E) -> Result[T, E]:
        return (
            self if predicate(self._value) else cast("Result[T, E]", _StreamErr(error))
        )

    def ok_or(self, default: U) -> T | U:
        return self._value


class _StreamErr(Result[T, E]):
    """Private ``Err`` implementation for contracts-only helpers."""

    def __init__(self, error: E) -> None:
        self._error = error

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> T:
        if isinstance(self._error, Exception):
            raise self._error
        raise ValueError(str(self._error))

    def unwrap_err(self) -> E:
        return self._error

    def unwrap_or(self, default: T) -> T:
        return default

    def unwrap_or_else(self, op: Callable[[E], T]) -> T:
        return op(self._error)

    def map_sync(self, op: Callable[[T], U]) -> Result[U, E]:
        return cast("Result[U, E]", self)

    def map_err(self, op: Callable[[E], F]) -> Result[T, F]:
        return _StreamErr(op(self._error))

    def and_then_sync(self, op: Callable[[T], Result[U, E]]) -> Result[U, E]:
        return cast("Result[U, E]", self)

    def or_else_sync(self, op: Callable[[E], Result[T, F]]) -> Result[T, F]:
        return op(self._error)

    def expect(self, message: str) -> T:
        raise ValueError(message)

    def match(self, ok: Callable[[T], U], err: Callable[[E], U]) -> U:
        return err(self._error)

    async def map(self, op: Callable[[T], Awaitable[U]]) -> Result[U, E]:
        return cast("Result[U, E]", self)

    async def and_then(
        self, op: Callable[[T], Awaitable[Result[U, E]]]
    ) -> Result[U, E]:
        return cast("Result[U, E]", self)

    async def or_else(self, op: Callable[[E], Awaitable[Result[T, F]]]) -> Result[T, F]:
        return await op(self._error)

    def flatten(self) -> Result[Any, E]:
        return cast("Result[Any, E]", self)

    def filter(self, predicate: Callable[[T], bool], error: E) -> Result[T, E]:
        return self

    def ok_or(self, default: U) -> T | U:
        return default


class AsyncStream(Generic[T, E]):
    """Async stream that preserves typed failures for terminal operations.

    ``AsyncStream`` is still directly iterable with ``async for``. If the
    underlying iterator fails, the stream stores the typed error, stops
    iteration, and exposes the failure through ``collect()``, ``first()``,
    ``drain()``, and the ``error`` property.
    """

    def __init__(
        self,
        iterator: AsyncIterator[T],
        *,
        error_adapter: Callable[[Exception], E],
    ) -> None:
        self._iterator = iterator
        self._error_adapter = error_adapter
        self._error: E | None = None
        self._done = False

    @property
    def error(self) -> E | None:
        """Return the stored stream error, if one occurred."""
        return self._error

    @property
    def failed(self) -> bool:
        """Return ``True`` when stream iteration ended with an error."""
        return self._error is not None

    def __aiter__(self) -> AsyncIterator[T]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[T]:
        if self._done:
            return

        while True:
            try:
                item = await anext(self._iterator)
            except StopAsyncIteration:
                self._done = True
                return
            except Exception as exc:  # noqa: BLE001
                self._done = True
                self._error = self._coerce_error(exc)
                return
            else:
                yield item

    async def collect(self) -> Result[list[T], E]:
        """Consume the entire stream into a list or return the first failure."""
        items: list[T] = []
        async for item in self:
            items.append(item)

        if self._error is not None:
            return _StreamErr(self._error)
        return _StreamOk(items)

    async def first(self) -> Result[T, E]:
        """Return the first item from the stream or the first failure.

        Raises:
            ValueError: If the stream completes with no item and no error
                (an empty stream has no ``Ok`` value and no ``E`` to return,
                so — like the standard library's ``max()``/``min()`` on an
                empty sequence — the empty case is a ``ValueError``).
        """
        async for item in self:
            return _StreamOk(item)

        if self._error is not None:
            return _StreamErr(self._error)
        raise ValueError("AsyncStream is empty")

    def map(self, fn: Callable[[T], U]) -> AsyncStream[U, E]:
        """Transform stream items lazily."""

        async def _generator() -> AsyncIterator[U]:
            async for item in self:
                yield fn(item)
            self._raise_if_failed()

        return AsyncStream(_generator(), error_adapter=self._coerce_error)

    def filter(self, predicate: Callable[[T], bool]) -> AsyncStream[T, E]:
        """Filter stream items lazily."""

        async def _generator() -> AsyncIterator[T]:
            async for item in self:
                if predicate(item):
                    yield item
            self._raise_if_failed()

        return AsyncStream(_generator(), error_adapter=self._coerce_error)

    def take(self, count: int) -> AsyncStream[T, E]:
        """Return a stream containing at most ``count`` items."""

        async def _generator() -> AsyncIterator[T]:
            if count <= 0:
                return

            remaining = count
            async for item in self:
                yield item
                remaining -= 1
                if remaining == 0:
                    return
            self._raise_if_failed()

        return AsyncStream(_generator(), error_adapter=self._coerce_error)

    async def drain(self) -> Result[None, E]:
        """Consume the stream without collecting items."""
        async for _ in self:
            continue

        if self._error is not None:
            return _StreamErr(self._error)
        return _StreamOk(None)

    def _coerce_error(self, exc: Exception) -> E:
        if isinstance(exc, _StoredStreamError):
            return cast("E", exc.error)
        return self._error_adapter(exc)

    def _raise_if_failed(self) -> None:
        if self._error is not None:
            raise _StoredStreamError(self._error)


__all__ = ["AsyncStream"]
