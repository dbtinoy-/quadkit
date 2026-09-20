"""Tests for testing.utils.async_helper module."""

import asyncio

import pytest

from quadkit.testing.lib.async_helper import AsyncTestHelper


class TestAsyncTestHelper:
    """Tests for AsyncTestHelper."""

    @pytest.mark.asyncio
    async def test_wait_for_condition_condition_met_immediately(
        self,
    ) -> None:
        """Test wait_for_condition when condition is met immediately."""
        # Note: condition_func is synchronous (Callable[[], bool])
        def condition() -> bool:
            return True

        result = await AsyncTestHelper.wait_for_condition(condition, timeout=5.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_condition_eventually_met(self) -> None:
        """Test wait_for_condition when condition is met after some time."""
        counter = 0

        def condition() -> bool:
            nonlocal counter
            counter += 1
            return counter >= 3

        result = await AsyncTestHelper.wait_for_condition(condition, timeout=5.0)

        assert result is True
        assert counter >= 3

    @pytest.mark.asyncio
    async def test_wait_for_condition_timeout(self) -> None:
        """Test wait_for_condition when condition is never met."""

        def condition() -> bool:
            return False

        result = await AsyncTestHelper.wait_for_condition(condition, timeout=0.2)

        assert result is False

    @pytest.mark.asyncio
    async def test_collect_async_results_all_success(self) -> None:
        """Test collect_async_results with all successful coroutines."""

        async def coro1() -> int:
            return 1

        async def coro2() -> int:
            return 2

        async def coro3() -> int:
            return 3

        coros = [coro1(), coro2(), coro3()]
        results = await AsyncTestHelper.collect_async_results(coros)

        assert len(results) == 3
        assert 1 in results
        assert 2 in results
        assert 3 in results

    @pytest.mark.asyncio
    async def test_collect_async_results_with_exception(self) -> None:
        """Test collect_async_results with one exception."""

        async def coro_success() -> int:
            return 1

        async def coro_fail() -> int:
            raise ValueError("Test error")

        coros = [coro_success(), coro_fail()]
        results = await AsyncTestHelper.collect_async_results(coros)

        assert len(results) == 2
        assert results[0] == 1
        assert isinstance(results[1], ValueError)

    @pytest.mark.asyncio
    async def test_run_with_timeout_success(self) -> None:
        """Test run_with_timeout when operation completes in time."""

        async def slow_operation() -> str:
            await asyncio.sleep(0.1)
            return "completed"

        result = await AsyncTestHelper.run_with_timeout(slow_operation(), timeout=5.0)

        assert result == "completed"

    @pytest.mark.asyncio
    async def test_run_with_timeout_raises_timeout(self) -> None:
        """Test run_with_timeout when operation times out."""

        async def slow_operation() -> str:
            await asyncio.sleep(10.0)
            return "completed"

        with pytest.raises(TimeoutError) as exc_info:
            await AsyncTestHelper.run_with_timeout(slow_operation(), timeout=0.1)

        assert "timed out" in str(exc_info.value).lower()
