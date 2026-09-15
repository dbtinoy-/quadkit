import asyncio

import pytest


def test_run_simple_coroutine():
    async def coro():
        return 123

    asyncio.run(coro())
    # run() should return same value even when no loop running
    from quadkit.concurrency.bridges.sync_bridge import SyncBridge

    assert SyncBridge.run(coro()) == 123


def test_run_async_function_from_sync():
    async def fn(x, y):
        await asyncio.sleep(0.001)
        return x + y

    from quadkit.concurrency.bridges.sync_bridge import SyncBridge

    assert SyncBridge.run(fn, 2, 3) == 5


def test_run_sync_function_from_sync():
    from quadkit.concurrency.bridges.sync_bridge import SyncBridge

    def add(x, y):
        return x + y

    with pytest.raises(ValueError):
        # run() expects an awaitable or async function; passing a sync
        # function should raise rather than silently return an incorrect
        # value (earlier implementation behaved this way).
        SyncBridge.run(add, 1, 2)
