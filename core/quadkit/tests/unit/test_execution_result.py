"""Tests for execution/result module."""

import pytest

from quadkit.result import Err, Ok, as_result, as_result_sync, collect, partition, try_catch, try_catch_sync


class TestOkErr:
    """Test ok and err functions."""

    def test_ok_function(self):
        """Test Ok() function creates Ok result."""
        result = Ok("value")
        assert result.is_ok()
        assert result.unwrap() == "value"

    def test_err_function(self):
        """Test Err() function creates Err result."""
        result = Err("error")
        assert result.is_err()
        assert result.unwrap_err() == "error"


class TestCollectResults:
    """Test collect_results function."""

    def test_collect_all_ok(self):
        """Test collecting all Ok results."""
        results = [Ok(1), Ok(2), Ok(3)]
        collected = collect(results)

        assert collected.is_ok()
        assert collected.unwrap() == [1, 2, 3]

    def test_collect_with_err(self):
        """Test collecting with one Err."""
        results = [Ok(1), Err("error"), Ok(3)]
        collected = collect(results)

        assert collected.is_err()


class TestPartitionResults:
    """Test partition_results function."""

    def test_partition_all_ok(self):
        """Test partitioning all Ok results."""
        results = [Ok(1), Ok(2), Ok(3)]
        oks, errs = partition(results)

        assert len(oks) == 3
        assert len(errs) == 0

    def test_partition_mixed(self):
        """Test partitioning mixed results."""
        results = [Ok(1), Err("e1"), Ok(2), Err("e2")]
        oks, errs = partition(results)

        assert len(oks) == 2
        assert len(errs) == 2

    def test_partition_all_err(self):
        """Test partitioning all Err results."""
        results = [Err("e1"), Err("e2")]
        oks, errs = partition(results)

        assert len(oks) == 0
        assert len(errs) == 2


class TestResultClass:
    """Test Result class methods."""

    def test_result_is_ok(self):
        """Test Result is_ok method."""
        result = Ok("value")
        assert result.is_ok() is True

    def test_result_is_err(self):
        """Test Result is_err method."""
        result = Err("error")
        assert result.is_err() is True

    def test_result_unwrap_ok(self):
        """Test Result unwrap on Ok."""
        result = Ok("value")
        assert result.unwrap() == "value"

    def test_result_unwrap_err(self):
        """Test Result unwrap on Err raises."""
        from quadkit.result.errors import UnwrapError
        result = Err("error")
        with pytest.raises(UnwrapError):
            result.unwrap()

    def test_result_unwrap_or(self):
        """Test Result unwrap_or."""
        assert Ok("value").unwrap_or("default") == "value"
        assert Err("error").unwrap_or("default") == "default"

    def test_result_map(self):
        """Test Result map_sync."""
        result = Ok(5).map_sync(lambda x: x * 2)
        assert result.unwrap() == 10

    def test_result_map_err(self):
        """Test Result map_err."""
        result = Err("error").map_err(lambda x: x.upper())
        assert result.unwrap_err() == "ERROR"

    def test_result_and_then(self):
        """Test Result and_then_sync."""
        result = Ok(5).and_then_sync(lambda x: Ok(x * 2))
        assert result.unwrap() == 10

    def test_result_or_else(self):
        """Test Result or_else_sync."""
        result = Err("error").or_else_sync(lambda e: Ok(f"fallback_{e}"))
        assert result.unwrap() == "fallback_error"


class TestTryCatchSync:
    """Tests for the sync try_catch_sync() helper."""

    def test_ok_on_success(self) -> None:
        """Returns Ok when the function succeeds."""
        result = try_catch_sync((ValueError,), lambda: 42)
        assert result.is_ok()
        assert result.unwrap() == 42

    def test_err_on_listed_exception(self) -> None:
        """Returns Err when a listed exception is raised."""
        result = try_catch_sync((ValueError,), int, "not-a-number")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)

    def test_propagates_unlisted_exception(self) -> None:
        """Exceptions not in the catch tuple propagate normally."""
        def raiser() -> int:
            raise KeyError("key")

        with pytest.raises(KeyError):
            try_catch_sync((ValueError,), raiser)

    def test_empty_catch_tuple_raises(self) -> None:
        """Passing an empty catch tuple means 'catch nothing' — exceptions propagate."""
        with pytest.raises(ValueError):
            try_catch_sync((), int, "bad")


class TestTryCatch:
    """Tests for try_catch() with async functions."""

    @pytest.mark.asyncio
    async def test_ok_on_success(self) -> None:
        """Returns Ok when the async function succeeds."""
        async def succeed() -> int:
            return 7

        result = await try_catch((ValueError,), succeed)
        assert result.is_ok()
        assert result.unwrap() == 7

    @pytest.mark.asyncio
    async def test_err_on_listed_exception(self) -> None:
        """Returns Err for a listed exception."""
        async def fail() -> int:
            raise ValueError("bad")

        result = await try_catch((ValueError,), fail)
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)


class TestAsResult:
    """Tests for as_result() — canonical async decorator."""

    def test_requires_exception_types(self) -> None:
        """Calling @as_result() with no types raises TypeError."""
        with pytest.raises(TypeError, match="at least one exception type"):
            as_result()

    def test_wraps_success_in_ok(self) -> None:
        """as_result_sync decorated function returns Ok on success."""
        @as_result_sync(ValueError)
        def parse(s: str) -> int:
            return int(s)

        result = parse("5")
        assert result.is_ok()
        assert result.unwrap() == 5

    def test_wraps_listed_exception_in_err(self) -> None:
        """as_result_sync decorated function returns Err for a listed exception."""
        @as_result_sync(ValueError)
        def parse(s: str) -> int:
            return int(s)

        result = parse("nope")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)

    @pytest.mark.asyncio
    async def test_async_function_ok(self) -> None:
        """Works with async functions via as_result (canonical)."""
        @as_result(ValueError)
        async def parse_async(s: str) -> int:
            return int(s)

        result = await parse_async("3")
        assert result.is_ok()
        assert result.unwrap() == 3
