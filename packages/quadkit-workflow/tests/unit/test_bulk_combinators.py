"""Tests for the bulk combinators: bulk_map, bulk_filter, bulk_reduce."""

from __future__ import annotations

from quadkit.workflow.bulk.combinators import bulk_filter, bulk_map, bulk_reduce


class TestBulkMap:
    async def test_sync_function(self) -> None:
        result = await bulk_map(lambda x: x * 2, [1, 2, 3])
        assert result == [2, 4, 6]

    async def test_identity(self) -> None:
        result = await bulk_map(lambda x: x, ["a", "b"])
        assert result == ["a", "b"]

    async def test_async_iterable_input(self) -> None:
        async def gen():
            for i in range(4):
                yield i

        result = await bulk_map(lambda x: x + 1, gen())
        assert result == [1, 2, 3, 4]

    async def test_empty(self) -> None:
        assert await bulk_map(lambda x: x, []) == []

    async def test_result_order_preserved(self) -> None:
        result = await bulk_map(lambda x: x, list(range(50)))
        assert result == list(range(50))


class TestBulkFilter:
    async def test_filters_items(self) -> None:
        async def is_even(x: int) -> bool:
            return x % 2 == 0

        batches = [b async for b in bulk_filter([1, 2, 3, 4, 5, 6], is_even)]
        kept = [item for b in batches for item in b.results]
        assert kept == [2, 4, 6]

    async def test_all_kept(self) -> None:
        async def keep_all(_x: int) -> bool:
            return True

        batches = [b async for b in bulk_filter([1, 2], keep_all)]
        assert [item for b in batches for item in b.results] == [1, 2]

    async def test_none_kept(self) -> None:
        async def keep_none(_x: int) -> bool:
            return False

        batches = [b async for b in bulk_filter([1, 2, 3], keep_none)]
        assert [item for b in batches for item in b.results] == []

    async def test_async_iterable_input(self) -> None:
        async def gen():
            yield 10
            yield 20
            yield 30

        async def is_gt_15(x: int) -> bool:
            return x > 15

        batches = [b async for b in bulk_filter(gen(), is_gt_15)]
        assert [item for b in batches for item in b.results] == [20, 30]


class TestBulkReduce:
    async def test_sum_sync_list(self) -> None:
        async def add(acc: int, x: int) -> int:
            return acc + x

        assert await bulk_reduce([1, 2, 3], add, 0) == 6

    async def test_string_accumulator(self) -> None:
        async def concat(acc: str, x: str) -> str:
            return acc + x

        assert await bulk_reduce(["a", "b", "c"], concat, "") == "abc"

    async def test_async_iterable_input(self) -> None:
        async def gen():
            yield 1
            yield 2
            yield 3

        async def add(acc: int, x: int) -> int:
            return acc + x

        assert await bulk_reduce(gen(), add, 10) == 16

    async def test_empty_returns_initial(self) -> None:
        async def add(acc: int, x: int) -> int:
            return acc + x

        assert await bulk_reduce([], add, 99) == 99

    async def test_reducer_receives_accumulated_state(self) -> None:
        seen: list[int] = []

        async def track(acc: int, x: int) -> int:
            seen.append(acc)
            return acc + x

        await bulk_reduce([1, 2, 3], track, 0)
        assert seen == [0, 1, 3]
