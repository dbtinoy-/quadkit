"""Core stream primitives: EventStream, Stream, piping.

A stream is a cold, single-pass async iterable: it does no work until
iterated, but it wraps one ``AsyncIterator`` and does not restart itself
once exhausted. ``pipe`` applies operators left to right; each operator is
a function from ``EventStream`` to ``EventStream``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol, TypeVar

R_co = TypeVar("R_co", covariant=True)
T = TypeVar("T")
S = TypeVar("S")


class EventStream(Protocol[R_co]):
    """An async-iterable stream of items, composable with ``pipe``."""

    def pipe(self, *operators: Op[Any, Any]) -> EventStream[Any]:
        """Apply operators left to right, returning a new stream."""

    def __aiter__(self) -> AsyncIterator[R_co]:
        """Iterate the stream asynchronously."""


class Stream(EventStream[T]):
    """A cold stream backed by an async iterator.

    Example:
        ```python
        async def gen():
            yield 1
            yield 2

        stream: EventStream[int] = Stream(gen())
        assert [item async for item in stream] == [1, 2]
        ```

    Note:
        Single-pass: this wraps one ``AsyncIterator`` and does not restart
        it. A second full iteration of the same ``Stream`` instance yields
        nothing — construct a fresh ``Stream`` (or call the producing
        function again) to consume the same logical source twice.
    """

    def __init__(self, source: AsyncIterator[T]) -> None:
        """Initialize a stream from an async iterator.

        Args:
            source: Any async iterator (generator, another stream, channel).
        """
        self._source = source

    def pipe(self, *operators: Op[Any, Any]) -> EventStream[Any]:
        """Apply operators left to right.

        Args:
            operators: Piped operators; each transforms one stream into another.

        Returns:
            The composed stream.
        """
        result: EventStream[Any] = self
        for operator in operators:
            result = operator(result)
        return result

    def __aiter__(self) -> AsyncIterator[T]:
        """Return the underlying async iterator."""
        return self._source


# Defined after Stream for forward-reference in the protocol above.
Op = Callable[[EventStream[R_co]], EventStream[T]]


def pipe(stream: EventStream[R_co], *operators: Op[Any, Any]) -> EventStream[Any]:
    """Apply operators to a stream, left to right.

    Args:
        stream: Source stream to pipe through the operators.
        operators: Piped operators; each transforms one stream into another.

    Returns:
        The composed stream.
    """
    return stream.pipe(*operators)
