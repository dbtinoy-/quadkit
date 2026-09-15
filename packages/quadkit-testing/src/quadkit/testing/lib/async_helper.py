from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any


class AsyncTestHelper:
    """Helper utilities for async testing."""

    @staticmethod
    async def wait_for_condition(
        condition_func: Callable[[], bool],
        timeout: float = 5.0,
        interval: float = 0.1,
    ) -> bool:
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if condition_func():
                return True
            await asyncio.sleep(interval)
        return False

    @staticmethod
    async def collect_async_results(coros: list[Coroutine[Any, Any, Any]]) -> list[Any]:
        return await asyncio.gather(*coros, return_exceptions=True)

    @staticmethod
    async def run_with_timeout(coro: Coroutine[Any, Any, Any], timeout: float) -> Any:
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except TimeoutError as err:
            msg = f"Operation timed out after {timeout} seconds"
            raise TimeoutError(msg) from err
