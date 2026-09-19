"""Tests for Parallel execution utilities."""

import asyncio

import pytest

from quadkit.concurrency.executors.parallel import Parallel
from quadkit.contracts.core import ExecutionStrategy


class TestParallelMap:
    """Tests for Parallel.map."""

    @pytest.mark.asyncio
    async def test_map_basic(self) -> None:
        """Test basic parallel map."""

        async def double(x: int) -> int:
            return x * 2

        results = await Parallel.map([1, 2, 3], double)
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_map_empty_list(self) -> None:
        """Test parallel map with empty list."""

        async def double(x: int) -> int:
            return x * 2

        results = await Parallel.map([], double)
        assert results == []

    @pytest.mark.asyncio
    async def test_map_single_item(self) -> None:
        """Test parallel map with single item."""

        async def increment(x: int) -> int:
            return x + 1

        results = await Parallel.map([5], increment)
        assert results == [6]


class TestParallelGather:
    """Tests for Parallel.gather."""

    @pytest.mark.asyncio
    async def test_gather_basic(self) -> None:
        """Test basic parallel gather."""

        async def get_value(x: int) -> int:
            return x * 2

        results = await Parallel.gather(get_value(1), get_value(2), get_value(3))
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_gather_empty(self) -> None:
        """Test gather with no awaitables."""
        results = await Parallel.gather()
        assert results == []

    @pytest.mark.asyncio
    async def test_gather_preserves_order(self) -> None:
        """Test that gather preserves order."""

        async def make_value(x: int) -> int:
            await asyncio.sleep(0.01 * (3 - x))  # reverse delay
            return x

        results = await Parallel.gather(make_value(1), make_value(2), make_value(3))
        assert results == [1, 2, 3]


class TestParallelAllSettled:
    """Tests for Parallel.all_settled."""

    @pytest.mark.asyncio
    async def test_all_settled_all_success(self) -> None:
        """Test all_settled with all successful results."""

        async def succeed(x: int) -> int:
            return x * 2

        results = await Parallel.all_settled(succeed(1), succeed(2), succeed(3))
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_all_settled_with_exception(self) -> None:
        """Test all_settled includes exceptions as values."""

        async def succeed(x: int) -> int:
            return x

        async def fail() -> int:
            raise ValueError("test error")

        results = await Parallel.all_settled(succeed(1), fail(), succeed(3))
        assert results[0] == 1
        assert isinstance(results[1], ValueError)
        assert results[1].args[0] == "test error"
        assert results[2] == 3

    @pytest.mark.asyncio
    async def test_all_settled_empty(self) -> None:
        """Test all_settled with empty list."""
        results = await Parallel.all_settled()
        assert results == []


class TestParallelExecute:
    """Tests for Parallel.execute."""

    @pytest.mark.asyncio
    async def test_execute_default_gather(self) -> None:
        """Test execute with default (GATHER) strategy."""

        async def get_value(x: int) -> int:
            return x * 2

        results = await Parallel.execute(get_value(1), get_value(2), get_value(3))
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_execute_all_settled_strategy(self) -> None:
        """Test execute with ALL_SETTLED strategy."""

        async def succeed(x: int) -> int:
            return x

        async def fail() -> int:
            raise ValueError("error")

        results = await Parallel.execute(
            succeed(1), fail(), succeed(3), strategy=ExecutionStrategy.ALL_SETTLED
        )
        assert results[0] == 1
        assert isinstance(results[1], ValueError)
        assert results[2] == 3

    @pytest.mark.asyncio
    async def test_execute_race_strategy(self) -> None:
        """Test execute with RACE strategy."""

        async def fast(value: int) -> int:
            await asyncio.sleep(0.01 * (3 - value))
            return value

        result = await Parallel.execute(
            fast(1), fast(2), fast(3), strategy=ExecutionStrategy.RACE
        )
        assert result == 3  # fastest should complete first

    @pytest.mark.asyncio
    async def test_execute_as_completed_strategy(self) -> None:
        """Test execute with AS_COMPLETED strategy."""

        async def make_value(x: int) -> int:
            await asyncio.sleep(0.01 * (3 - x))
            return x

        results = await Parallel.execute(
            make_value(1), make_value(2), make_value(3), strategy=ExecutionStrategy.AS_COMPLETED
        )
        assert len(results) == 3
        assert set(results) == {1, 2, 3}
