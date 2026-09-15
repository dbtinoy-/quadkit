"""Tests for AsyncRWLock in concurrency module."""

import asyncio
import pytest

from quadkit.concurrency.locks.rwlock import AsyncRWLock


class TestAsyncRWLockBasics:
    """Basic tests for AsyncRWLock."""

    def test_init(self) -> None:
        """Test AsyncRWLock initialization."""
        rw = AsyncRWLock()
        assert rw.reader_count == 0
        assert rw.writer_active is False

    def test_reader_count_property(self) -> None:
        """Test reader_count property."""
        rw = AsyncRWLock()
        assert rw.reader_count == 0

    def test_writer_active_property(self) -> None:
        """Test writer_active property."""
        rw = AsyncRWLock()
        assert rw.writer_active is False


class TestAsyncRWLockRead:
    """Tests for read lock."""

    @pytest.mark.asyncio
    async def test_read_acquires_lock(self) -> None:
        """Test read context manager acquires lock."""
        rw = AsyncRWLock()
        async with rw.read():
            assert rw.reader_count == 1

    @pytest.mark.asyncio
    async def test_read_releases_lock(self) -> None:
        """Test read context manager releases lock."""
        rw = AsyncRWLock()
        async with rw.read():
            pass
        assert rw.reader_count == 0

    @pytest.mark.asyncio
    async def test_multiple_readers(self) -> None:
        """Test multiple readers can acquire."""
        rw = AsyncRWLock()
        async with rw.read():
            async with rw.read():
                assert rw.reader_count == 2
        assert rw.reader_count == 0


class TestAsyncRWLockWrite:
    """Tests for write lock."""

    @pytest.mark.asyncio
    async def test_write_acquires_lock(self) -> None:
        """Test write context manager acquires exclusive lock."""
        rw = AsyncRWLock()
        async with rw.write():
            assert rw.writer_active is True
            assert rw.reader_count == 0

    @pytest.mark.asyncio
    async def test_write_releases_lock(self) -> None:
        """Test write context manager releases lock."""
        rw = AsyncRWLock()
        async with rw.write():
            pass
        assert rw.writer_active is False


class TestAsyncRWLockExclusion:
    """Tests for reader-writer exclusion."""

    @pytest.mark.asyncio
    async def test_read_after_write_releases(self) -> None:
        """Test read can proceed after write completes."""
        rw = AsyncRWLock()

        async with rw.write():
            pass

        async with rw.read():
            assert rw.reader_count == 1

    @pytest.mark.asyncio
    async def test_write_after_read_releases(self) -> None:
        """Test write can proceed after read completes."""
        rw = AsyncRWLock()

        async with rw.read():
            pass

        async with rw.write():
            assert rw.writer_active is True


class TestAsyncRWLockEdgeCases:
    """Edge case tests for AsyncRWLock."""

    @pytest.mark.asyncio
    async def test_nested_reads_independent(self) -> None:
        """Test that nested reads work correctly."""
        rw = AsyncRWLock()
        async with rw.read():
            async with rw.read():
                assert rw.reader_count == 2
        assert rw.reader_count == 0


class TestAsyncRWLockAsyncBasics:
    """Basic async scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_reads_work(self) -> None:
        """Test concurrent reads work."""
        rw = AsyncRWLock()
        results: list[int] = []

        async def read_value(val: int) -> int:
            async with rw.read():
                return val

        results = await asyncio.gather(read_value(1), read_value(2), read_value(3))
        assert results == [1, 2, 3]
