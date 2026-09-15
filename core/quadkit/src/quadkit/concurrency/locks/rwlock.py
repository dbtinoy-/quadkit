"""Async reader-writer lock for Quadkit Framework.

Provides ``AsyncRWLock`` — an asyncio-native, readers-writer lock that
allows many concurrent readers OR exactly one writer.  Ideal for
protecting state shared across many async tasks where reads vastly
outnumber writes.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import contextlib


class AsyncRWLock:
    """Asyncio reader-writer lock (many readers, one writer).

    Readers may enter concurrently as long as no writer is active.
    A writer blocks until all active readers have exited and then
    acquires exclusive access.

    Use the async context managers :meth:`read` and :meth:`write`
    to bracket read/write critical sections.

    Example::

        rw = AsyncRWLock()

        async def do_read():
            async with rw.read():
                data = shared_data.copy()
            return data

        async def do_write(item):
            async with rw.write():
                shared_data.append(item)

    .. note::
        Writers are not prioritised over readers in this implementation.
        Under sustained read load a writer may starve. If writer latency
        is critical, use an external library with write-priority support.
    """

    def __init__(self) -> None:
        self._condition = asyncio.Condition(asyncio.Lock())
        self._readers: int = 0
        self._writer_active: bool = False

    @contextlib.asynccontextmanager
    async def read(self) -> AsyncIterator[None]:
        """Async context manager that acquires a shared read lock.

        Multiple readers may hold the lock simultaneously.

        Usage::

            async with rw_lock.read():
                ...  # shared read access
        """
        async with self._condition:
            while self._writer_active:
                await self._condition.wait()
            self._readers += 1

        try:
            yield
        finally:
            async with self._condition:
                self._readers -= 1
                if self._readers == 0:
                    self._condition.notify_all()

    @contextlib.asynccontextmanager
    async def write(self) -> AsyncIterator[None]:
        """Async context manager that acquires an exclusive write lock.

        Blocks until all active readers and any pending writer have
        finished.

        Usage::

            async with rw_lock.write():
                ...  # exclusive write access
        """
        async with self._condition:
            while self._writer_active or self._readers > 0:
                await self._condition.wait()
            self._writer_active = True

        try:
            yield
        finally:
            async with self._condition:
                self._writer_active = False
                self._condition.notify_all()

    # -- Introspection helpers --

    @property
    def reader_count(self) -> int:
        """Number of currently active readers.

        Returns:
            Active reader count.
        """
        return self._readers

    @property
    def writer_active(self) -> bool:
        """True if a writer currently holds the lock.

        Returns:
            ``True`` if a writer is active.
        """
        return self._writer_active


__all__ = ["AsyncRWLock"]
