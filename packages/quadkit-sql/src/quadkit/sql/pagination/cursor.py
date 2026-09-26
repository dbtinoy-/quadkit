"""Cursor-based pagination helper.

Wraps an async fetch function with keyset pagination logic, producing
:class:`~quadkit.contracts.domain.pagination.CursorPage` results.  Uses
:class:`~quadkit.data.query.cursor.CursorCodec` for opaque cursor encoding.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

from quadkit.contracts.domain.pagination import CursorPage
from quadkit.sql.query.cursor import CursorCodec

T = TypeVar("T")

FetchFn = Callable[..., Awaitable[list[T]]]


class CursorPaginator(Generic[T]):
    """Performs one page of cursor-based (keyset) pagination.

    The caller supplies an async ``fetch_fn`` that accepts ``after`` (a decoded
    dict of cursor values or ``None``), ``limit`` (int representing the number
    of items to fetch), and any extra keyword arguments.  ``CursorPaginator``
    fetches ``limit + 1`` items to determine whether a next page exists, then
    encodes the last-item cursor for the response.

    Args:
        fetch_fn: Async callable that returns a list of at most ``limit`` items.
            Signature: ``async def fetch(after: dict | None, limit: int, **kw)``
        key_fields: Attribute names used to build the cursor.  Defaults to
            ``("id",)``.
        codec: Codec used to encode/decode cursor strings.  If omitted, a
            default :class:`~quadkit.data.query.cursor.CursorCodec` is used.

    Example::

        async def fetch(after, limit, **kw):
            ...

        paginator = CursorPaginator(fetch_fn=fetch, key_fields=("id",))
        page = await paginator.paginate(cursor=None, size=20)
    """

    def __init__(
        self,
        *,
        fetch_fn: FetchFn[T],
        key_fields: tuple[str, ...] = ("id",),
        codec: CursorCodec | None = None,
    ) -> None:
        self._fetch_fn = fetch_fn
        self._key_fields = key_fields
        self._codec = codec or CursorCodec()

    async def paginate(
        self,
        *,
        cursor: str | None = None,
        size: int = 20,
        **kwargs: Any,
    ) -> CursorPage[T]:
        """Fetch one page of results.

        Args:
            cursor: Opaque cursor from a previous :class:`CursorPage`, or
                ``None`` for the first page.
            size: Number of items per page.
            **kwargs: Extra keyword arguments forwarded to ``fetch_fn``.

        Returns:
            A :class:`~quadkit.contracts.domain.pagination.CursorPage` with
            items and navigation cursors.
        """
        after = self._codec.decode(cursor) if cursor else None
        # Fetch one extra to test for a next page.
        raw: list[T] = await self._fetch_fn(after=after, limit=size + 1, **kwargs)

        has_more = len(raw) > size
        items = raw[:size]

        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = self._codec.encode(
                {f: getattr(last, f, None) for f in self._key_fields}
            )

        return CursorPage(
            items=items,
            next_cursor=next_cursor,
            prev_cursor=cursor,
            has_more=has_more,
            has_previous=cursor is not None,
        )


__all__ = ["CursorPaginator"]
