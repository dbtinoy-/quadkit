"""Tests for result/utils module."""
import pytest

from quadkit.result import Ok, Err
from quadkit.result.utils import (
    as_result,
    as_result_sync,
    collect,
    partition,
    try_catch,
    try_catch_sync,
)


class TestAsResultSyncDecorator:
    """Tests for as_result_sync decorator (sync variant)."""

    def test_as_result_sync_no_exceptions_raises(self) -> None:
        """Test that as_result_sync raises TypeError with no exceptions."""
        with pytest.raises(TypeError, match="requires at least one exception type"):
            as_result_sync()

    def test_as_result_sync_success(self) -> None:
        """Test as_result_sync with successful function."""
        @as_result_sync(ValueError)
        def parse_int(data: str) -> int:
            return int(data)

        result = parse_int("42")
        assert result.is_ok()
        assert result.unwrap() == 42

    def test_as_result_sync_exception(self) -> None:
        """Test as_result_sync catches exception."""
        @as_result_sync(ValueError)
        def parse_int(data: str) -> int:
            return int(data)

        result = parse_int("not_a_number")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)

    def test_as_result_sync_unexpected_exception_propagates(self) -> None:
        """Test that unexpected exceptions propagate."""
        @as_result_sync(ValueError)  # Only catching ValueError
        def raise_type_error(data: str) -> int:
            raise TypeError("unexpected")

        with pytest.raises(TypeError):
            raise_type_error("test")

    def test_as_result_sync_multiple_exceptions(self) -> None:
        """Test as_result_sync with multiple exception types."""
        @as_result_sync(ValueError, KeyError)
        def get_item(data: dict, key: str) -> int:
            return data[key]

        result = get_item({"a": 1}, "b")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), KeyError)


class TestAsResultDecorator:
    """Tests for as_result decorator (canonical async variant)."""

    def test_as_result_no_exceptions_raises(self) -> None:
        """Test that as_result raises TypeError with no exceptions."""
        with pytest.raises(TypeError, match="requires at least one exception type"):
            as_result()

    @pytest.mark.asyncio
    async def test_as_result_success(self) -> None:
        """Test as_result with successful async function."""

        @as_result(ValueError)
        async def async_parse(data: str) -> int:
            return int(data)

        result = await async_parse("42")
        assert result.is_ok()
        assert result.unwrap() == 42

    @pytest.mark.asyncio
    async def test_as_result_exception(self) -> None:
        """Test as_result catches exception."""

        @as_result(ValueError)
        async def async_parse(data: str) -> int:
            return int(data)

        result = await async_parse("not_a_number")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)


class TestCollect:
    """Tests for collect function."""

    def test_collect_all_ok(self) -> None:
        """Test collect with all Ok results."""
        results = [Ok(1), Ok(2), Ok(3)]
        collected = collect(results)
        assert collected.is_ok()
        assert collected.unwrap() == [1, 2, 3]

    def test_collect_with_err(self) -> None:
        """Test collect stops at first error."""
        results = [Ok(1), Err("error"), Ok(3)]
        collected = collect(results)
        assert collected.is_err()
        assert collected.unwrap_err() == "error"

    def test_collect_empty(self) -> None:
        """Test collect with empty iterable."""
        results = []
        collected = collect(results)
        assert collected.is_ok()
        assert collected.unwrap() == []


class TestPartition:
    """Tests for partition function."""

    def test_partition_all_ok(self) -> None:
        """Test partition with all Ok results."""
        results = [Ok(1), Ok(2), Ok(3)]
        oks, errs = partition(results)
        assert oks == [1, 2, 3]
        assert errs == []

    def test_partition_all_err(self) -> None:
        """Test partition with all Err results."""
        results = [Err("a"), Err("b"), Err("c")]
        oks, errs = partition(results)
        assert oks == []
        assert errs == ["a", "b", "c"]

    def test_partition_mixed(self) -> None:
        """Test partition with mixed results."""
        results = [Ok(1), Err("error"), Ok(3), Err("another")]
        oks, errs = partition(results)
        assert oks == [1, 3]
        assert errs == ["error", "another"]

    def test_partition_empty(self) -> None:
        """Test partition with empty iterable."""
        results = []
        oks, errs = partition(results)
        assert oks == []
        assert errs == []


class TestTryCatchSync:
    """Tests for try_catch_sync function (sync variant)."""

    def test_try_catch_sync_success(self) -> None:
        """Test try_catch_sync with successful execution."""
        result = try_catch_sync((ValueError,), int, "42")
        assert result.is_ok()
        assert result.unwrap() == 42

    def test_try_catch_sync_catches_expected(self) -> None:
        """Test try_catch_sync catches expected exception."""
        result = try_catch_sync((ValueError,), int, "not_a_number")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)

    def test_try_catch_sync_unexpected_propagates(self) -> None:
        """Test that unexpected exceptions propagate."""
        def raise_error():
            raise RuntimeError("unexpected")

        with pytest.raises(RuntimeError):
            try_catch_sync((ValueError,), raise_error)

    def test_try_catch_sync_multiple_exception_types(self) -> None:
        """Test try_catch_sync with multiple exception types."""
        def get_item(d: dict, key: str):
            return d[key]

        result = try_catch_sync((KeyError, ValueError), get_item, {}, "missing")
        assert result.is_err()


@pytest.mark.asyncio
class TestTryCatch:
    """Tests for try_catch function with async."""

    async def test_try_catch_success(self) -> None:
        """Test try_catch with successful execution."""
        async def async_int(s: str) -> int:
            return int(s)

        result = await try_catch((ValueError,), async_int, "42")
        assert result.is_ok()
        assert result.unwrap() == 42

    async def test_try_catch_catches_expected(self) -> None:
        """Test try_catch catches expected exception."""
        async def async_int(s: str) -> int:
            return int(s)

        result = await try_catch((ValueError,), async_int, "not_a_number")
        assert result.is_err()

    async def test_try_catch_unexpected_propagates(self) -> None:
        """Test that unexpected exceptions propagate."""
        async def raises_type():
            raise TypeError("unexpected")

        with pytest.raises(TypeError):
            await try_catch((ValueError,), raises_type)