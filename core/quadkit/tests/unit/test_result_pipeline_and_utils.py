"""Tests for ResultPipeline and result utility functions."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.result._pipeline import ResultPipeline, pipeline
from quadkit.result.types import Err, Ok
from quadkit.result.utils import (
    as_result,
    as_result_sync,
    collect,
    partition,
    try_catch,
    try_catch_sync,
)


class TestResultPipeline:
    def test_pipeline_starts_ok(self) -> None:
        p = pipeline(5)
        assert p.finalize().is_ok()
        assert p.finalize().unwrap() == 5

    def test_map_transforms_ok(self) -> None:
        assert pipeline(2).map(lambda x: x * 3).finalize().unwrap() == 6

    def test_map_preserves_err(self) -> None:
        p = ResultPipeline(Err(ValueError("nope")))
        result = p.map(lambda x: x * 3).finalize()
        assert result.is_err()
        assert "nope" in str(result.unwrap_err())

    def test_then_chains_ok(self) -> None:
        def step(value: int) -> Any:
            return Ok(value + 10)

        assert pipeline(1).then(step).then(step).finalize().unwrap() == 21

    def test_then_short_circuits_on_err(self) -> None:
        called = False

        def step(value: int) -> Any:
            nonlocal called
            called = True
            return Ok(value)

        p = ResultPipeline(Err(ValueError("early")))
        result = p.then(step).finalize()
        assert result.is_err()
        assert called is False

    def test_then_propagates_new_err(self) -> None:
        def failing(value: int) -> Any:
            return Err(KeyError("bad-key"))

        result = pipeline(1).then(failing).finalize()
        assert result.is_err()
        assert isinstance(result.unwrap_err(), KeyError)

    def test_recover_from_err(self) -> None:
        def recovery(err: Exception) -> Any:
            return Ok(f"recovered:{err}")

        p = ResultPipeline(Err(ValueError("bad")))
        assert p.recover(recovery).finalize().unwrap() == "recovered:bad"

    def test_recover_preserves_ok(self) -> None:
        called = False

        def recovery(err: Exception) -> Any:
            nonlocal called
            called = True
            return Ok("x")

        assert pipeline(7).recover(recovery).finalize().unwrap() == 7
        assert called is False

    def test_recover_to_another_err(self) -> None:
        def recovery(err: Exception) -> Any:
            return Err(RuntimeError("still broken"))

        p = ResultPipeline(Err(ValueError("v")))
        result = p.recover(recovery).finalize()
        assert isinstance(result.unwrap_err(), RuntimeError)

    def test_full_chain(self) -> None:
        def parse(text: str) -> Any:
            try:
                return Ok(int(text))
            except ValueError as e:
                return Err(e)

        def double(value: int) -> Any:
            return value * 2

        good = pipeline("41").then(parse).map(double).finalize()
        assert good.unwrap() == 82

        bad = pipeline("nope").then(parse).map(double).finalize()
        assert bad.is_err()


class TestAsResultDecorators:
    def test_as_result_requires_exceptions(self) -> None:
        with pytest.raises(TypeError, match="at least one exception type"):
            as_result()

    def test_as_result_sync_requires_exceptions(self) -> None:
        with pytest.raises(TypeError, match="at least one exception type"):
            as_result_sync()

    async def test_as_result_catches_listed(self) -> None:
        @as_result(OSError)
        async def failing() -> str:
            raise OSError("disk")

        result = await failing()
        assert result.is_err()
        assert isinstance(result.unwrap_err(), OSError)

    async def test_as_result_ok_path(self) -> None:
        @as_result(OSError)
        async def working(x: int) -> int:
            return x + 1

        result = await working(41)
        assert result.is_ok()
        assert result.unwrap() == 42

    async def test_as_result_lets_unlisted_propagate(self) -> None:
        @as_result(OSError)
        async def failing() -> None:
            raise KeyError("not caught")

        with pytest.raises(KeyError):
            await failing()

    def test_as_result_sync_catches_listed(self) -> None:
        @as_result_sync(ValueError, KeyError)
        def parse(text: str) -> int:
            return int(text)

        assert parse("42").unwrap() == 42
        result = parse("nope")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)

    def test_as_result_sync_preserves_name(self) -> None:
        @as_result_sync(ValueError)
        def my_func() -> int:
            return 1

        assert my_func.__name__ == "my_func"


class TestCollect:
    def test_collect_all_ok(self) -> None:
        result = collect([Ok(1), Ok(2), Ok(3)])
        assert result.is_ok()
        assert result.unwrap() == [1, 2, 3]

    def test_collect_stops_at_first_err(self) -> None:
        result = collect([Ok(1), Err(ValueError("boom")), Ok(3)])
        assert result.is_err()
        assert "boom" in str(result.unwrap_err())

    def test_collect_empty(self) -> None:
        result = collect([])
        assert result.is_ok()
        assert result.unwrap() == []


class TestPartition:
    def test_partition_splits(self) -> None:
        oks, errs = partition([Ok("a"), Err(1), Ok("b"), Err(2)])
        assert oks == ["a", "b"]
        assert errs == [1, 2]

    def test_partition_all_one_side(self) -> None:
        oks, errs = partition([Ok("a"), Ok("b")])
        assert oks == ["a", "b"]
        assert errs == []


class TestTryCatch:
    async def test_try_catch_ok(self) -> None:
        async def fetch(url: str) -> str:
            return f"data:{url}"

        result = await try_catch((OSError,), fetch, "u1")
        assert result.is_ok()
        assert result.unwrap() == "data:u1"

    async def test_try_catch_err(self) -> None:
        async def fetch(url: str) -> str:
            raise TimeoutError("slow")

        result = await try_catch((OSError, TimeoutError), fetch, "u1")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), TimeoutError)

    async def test_try_catch_unlisted_propagates(self) -> None:
        async def fetch(url: str) -> str:
            raise RuntimeError("infra")

        with pytest.raises(RuntimeError):
            await try_catch((OSError,), fetch, "u1")

    def test_try_catch_sync_ok_and_err(self) -> None:
        def parse(text: str) -> int:
            return int(text)

        assert try_catch_sync((ValueError,), parse, "7").unwrap() == 7
        result = try_catch_sync((ValueError,), parse, "x")
        assert result.is_err()

    def test_try_catch_sync_unlisted_propagates(self) -> None:
        def bad() -> None:
            raise KeyError("nope")

        with pytest.raises(KeyError):
            try_catch_sync((ValueError,), bad)

    def test_try_catch_forwards_kwargs(self) -> None:
        def with_kwargs(a: int, b: int) -> int:
            return a + b

        result = try_catch_sync((ValueError,), with_kwargs, 1, b=2)
        assert result.unwrap() == 3
