"""Unit tests for the in-process lock manager (concurrency.locking).

Covers the documented non-blocking contention semantics, the blocking
``acquire_wait`` path used by ``UniqueTask`` wait mode, and stale-release
safety after lock expiry (added in a later task).
"""

import asyncio
import time

import pytest

from quadkit.tasks.concurrency.locking import LockManager, UniqueTask


@pytest.mark.asyncio
async def test_acquire_is_non_blocking_on_contention() -> None:
    """A contended acquire() returns False immediately instead of waiting."""
    lock_manager = LockManager()
    holder = lock_manager.acquire("key", timeout=60)
    assert await holder.acquire() is True

    waiter = lock_manager.acquire("key", timeout=60)
    start = time.monotonic()
    acquired = await waiter.try_acquire()
    assert acquired is False
    assert time.monotonic() - start < 0.05


@pytest.mark.asyncio
async def test_acquire_wait_blocks_until_released() -> None:
    """acquire_wait() suspends until the holder releases the key."""
    lock_manager = LockManager()
    holder = lock_manager.acquire("key", timeout=60)
    assert await holder.acquire() is True

    waiter = lock_manager.acquire("key", timeout=60)
    waited = asyncio.create_task(waiter.acquire_wait())
    await asyncio.sleep(0.1)
    assert waiter.acquired is False, "waiter must not acquire while held"

    await holder.release()
    assert await waited is True
    assert waiter.acquired is True
    await waiter.release()


@pytest.mark.asyncio
async def test_acquire_wait_timeout_returns_false() -> None:
    """acquire_wait(timeout) gives up when the lock stays held."""
    lock_manager = LockManager()
    holder = lock_manager.acquire("key", timeout=60)
    assert await holder.acquire() is True

    waiter = lock_manager.acquire("key", timeout=60)
    start = time.monotonic()
    assert await waiter.acquire_wait(timeout=0.15) is False
    assert time.monotonic() - start >= 0.14
    assert waiter.acquired is False
    await holder.release()


@pytest.mark.asyncio
async def test_acquire_wait_takes_over_expired_lock() -> None:
    """A waiting caller acquires the key once the holder's entry expires."""
    lock_manager = LockManager()
    holder = lock_manager.acquire("key", timeout=0.1)
    assert await holder.acquire() is True

    waiter = lock_manager.acquire("key", timeout=60)
    start = time.monotonic()
    assert await waiter.acquire_wait(timeout=2.0) is True
    assert time.monotonic() - start < 1.0
    assert waiter.acquired is True
    await waiter.release()


@pytest.mark.asyncio
async def test_unique_task_wait_mode_serializes_callers() -> None:
    """Wait-mode callers are serialized: the second starts only after release.

    Regression: the old wait branch used ``async with lock:`` whose
    __aenter__ ignored the False returned by the non-blocking acquire(),
    so the second caller ran concurrently with the first.
    """
    events: list[str] = []
    first_entered = asyncio.Event()
    release_first = asyncio.Event()

    lock_manager = LockManager()
    unique = UniqueTask(
        lock_manager=lock_manager,
        key_func=lambda: "sync:user:1",
        timeout=60.0,
        skip_if_locked=False,
    )

    @unique
    async def sync_user() -> str:
        events.append("start")
        first_entered.set()
        await release_first.wait()
        events.append("end")
        return "synced"

    first = asyncio.create_task(sync_user())
    await first_entered.wait()
    second = asyncio.create_task(sync_user())

    await asyncio.sleep(0.3)
    assert events == ["start"], "second caller must wait, not run concurrently"

    release_first.set()
    await asyncio.gather(first, second)

    assert events == ["start", "end", "start", "end"]
    assert first.result() == "synced"
    assert second.result() == "synced"


@pytest.mark.asyncio
async def test_stale_release_does_not_clobber_new_holder() -> None:
    """A stale release() must not evict the entry of a later acquirer.

    Regression: release() deleted the key whenever it was present,
    so a release of an expired lock instance clobbered the entry of a
    different, legitimate later acquirer.
    """
    lock_manager = LockManager()
    stale = lock_manager.acquire("key", timeout=0.1)
    assert await stale.acquire() is True

    await asyncio.sleep(0.15)  # stale's entry expires and is purged

    current = lock_manager.acquire("key", timeout=60)
    assert await current.acquire() is True

    await stale.release()  # stale release of the purged entry

    contender = lock_manager.acquire("key", timeout=60)
    assert await contender.try_acquire() is False, (
        "new holder's entry must survive a stale release()"
    )
    assert current.acquired is True

    await current.release()
    assert await contender.acquire() is True
    await contender.release()
