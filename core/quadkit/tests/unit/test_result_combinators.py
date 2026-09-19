"""Result combinators: map/filter/inspect/unwrap-or and async variants."""

"""Tests for Result types (Ok, Err, Result)."""

import pytest

from quadkit.result import Err, Ok, Result
from quadkit.result.errors import UnwrapError




class TestErrUnwrapWithException:
    """Tests for Err containing exceptions."""

    def test_unwrap_propagates_exception(self) -> None:
        """Test unwrap on Err with exception raises UnwrapError."""
        err: Result[int, ValueError] = Err(ValueError("test error"))
        with pytest.raises(UnwrapError, match="Called unwrap"):
            err.unwrap()

    def test_unwrap_or_returns_default_for_exception(self) -> None:
        """Test unwrap_or returns default for Err with exception."""
        err: Result[int, ValueError] = Err(ValueError("test"))
        assert err.unwrap_or(42) == 42


class TestOkMapErrOnException:
    """Tests for map_err when Ok contains exception."""

    def test_map_err_preserves_ok_with_exception(self) -> None:
        """Test map_err on Ok preserves value."""
        ok: Result[int, ValueError] = Ok(42)
        result = ok.map_err(lambda e: RuntimeError(str(e)))
        assert result.is_ok()
        assert result.unwrap() == 42


class TestResultFilter:
    """Tests for Result.filter() combinator."""

    def test_ok_filter_passes(self) -> None:
        """Test filter returns Ok when predicate is true."""
        result: Result[int, str] = Ok(5)
        filtered = result.filter(lambda x: x > 0, "negative")
        assert filtered == Ok(5)

    def test_ok_filter_fails(self) -> None:
        """Test filter converts Ok to Err when predicate is false."""
        result: Result[int, str] = Ok(5)
        filtered = result.filter(lambda x: x > 10, "too small")
        assert filtered == Err("too small")

    def test_ok_filter_with_string(self) -> None:
        """Test filter with string value."""
        result: Result[str, str] = Ok("hello")
        filtered = result.filter(lambda s: len(s) > 3, "too short")
        assert filtered == Ok("hello")

    def test_ok_filter_empty_string(self) -> None:
        """Test filter converts empty string to Err."""
        result: Result[str, str] = Ok("hi")
        filtered = result.filter(lambda s: len(s) > 3, "too short")
        assert filtered == Err("too short")

    def test_err_filter_noop(self) -> None:
        """Test filter is no-op on Err."""
        result: Result[int, str] = Err("original")
        filtered = result.filter(lambda _x: True, "ignored")
        assert filtered == Err("original")

    def test_err_filter_noop_predicate_not_called(self) -> None:
        """Test filter predicate is not called on Err."""
        call_count = [0]

        def predicate(x: int) -> bool:
            call_count[0] += 1
            return True

        result: Result[int, str] = Err("original")
        _filtered = result.filter(predicate, "ignored")
        assert call_count[0] == 0

    def test_filter_chain(self) -> None:
        """Test chaining multiple filters."""
        result: Result[int, str] = Ok(5)
        filtered = result.filter(lambda x: x > 0, "negative").filter(
            lambda x: x < 10, "too large"
        )
        assert filtered == Ok(5)

    def test_filter_chain_fails_early(self) -> None:
        """Test chain stops at first filter failure."""
        result: Result[int, str] = Ok(15)
        filtered = result.filter(lambda x: x > 0, "negative").filter(
            lambda x: x < 10, "too large"
        )
        assert filtered == Err("too large")


class TestResultInspectErr:
    """Tests for Result.inspect_err() combinator."""

    def test_err_inspect_err_side_effect_called(self) -> None:
        """Test inspect_err calls side effect on Err."""
        errors: list[str] = []
        result: Result[str, ValueError] = Err(ValueError("bad"))
        result.inspect_err(lambda e: errors.append(str(e)))
        assert errors == ["bad"]

    def test_err_inspect_err_returns_self(self) -> None:
        """Test inspect_err returns the same Err unchanged."""
        result: Result[str, ValueError] = Err(ValueError("bad"))
        inspected = result.inspect_err(lambda _e: None)
        assert inspected == result

    def test_ok_inspect_err_side_effect_not_called(self) -> None:
        """Test inspect_err side effect is not called on Ok."""
        errors: list[str] = []
        result: Result[str, ValueError] = Ok("good")
        result.inspect_err(lambda e: errors.append(str(e)))
        assert errors == []

    def test_ok_inspect_err_returns_self(self) -> None:
        """Test inspect_err returns the same Ok unchanged."""
        result: Result[str, ValueError] = Ok("good")
        inspected = result.inspect_err(lambda _e: None)
        assert inspected == result

    def test_err_inspect_err_chain(self) -> None:
        """Test chaining inspect_err with other operations."""
        errors: list[str] = []

        result: Result[str, str] = Err("first error")
        chained = result.inspect_err(errors.append).map_err(lambda e: e.upper())

        assert errors == ["first error"]
        assert chained == Err("FIRST ERROR")

    def test_inspect_err_with_complex_operation(self) -> None:
        """Test inspect_err with a more complex side effect."""
        logs: dict[str, int] = {"count": 0, "sum": 0}

        result: Result[int, int] = Err(42)
        result.inspect_err(
            lambda e: logs.update({"count": logs["count"] + 1, "sum": logs["sum"] + e})
        )

        assert logs["count"] == 1
        assert logs["sum"] == 42


class TestResultOkOr:
    """Tests for Result.ok_or() accessor."""

    def test_ok_returns_value(self) -> None:
        """Test ok_or returns Ok value, ignoring default."""
        result: Result[int, str] = Ok(42)
        assert result.ok_or(0) == 42

    def test_err_returns_default(self) -> None:
        """Test ok_or returns default on Err."""
        result: Result[int, str] = Err("oops")
        assert result.ok_or(0) == 0

    def test_ok_or_with_string(self) -> None:
        """Test ok_or with string values."""
        result: Result[str, str] = Ok("hello")
        assert result.ok_or("default") == "hello"

    def test_ok_or_with_err_returns_default_string(self) -> None:
        """Test ok_or with string error returns default."""
        result: Result[str, str] = Err("error")
        assert result.ok_or("default") == "default"

    def test_ok_or_with_none(self) -> None:
        """Test ok_or with None as default."""
        result: Result[int, str] = Err("error")
        assert result.ok_or(None) is None

    def test_ok_or_preserves_ok_type(self) -> None:
        """Test ok_or preserves the Ok type."""
        result: Result[list[int], str] = Ok([1, 2, 3])
        value = result.ok_or([])
        assert value == [1, 2, 3]
        assert isinstance(value, list)


class TestResultAsyncMapAlias:
    """Tests for Result.async_map alias."""

    @pytest.mark.asyncio
    async def test_async_map_ok(self) -> None:
        """Test async_map alias works on Ok."""
        ok = Ok(21)

        async def double(x: int) -> int:
            return x * 2

        result = await ok.async_map(double)
        assert result.unwrap() == 42

    @pytest.mark.asyncio
    async def test_async_map_err(self) -> None:
        """Test async_map alias works on Err."""
        err = Err("error")

        async def double(x: int) -> int:
            return x * 2

        result = await err.async_map(double)
        assert result.is_err()
        assert result.unwrap_err() == "error"

    @pytest.mark.asyncio
    async def test_async_map_is_same_as_map(self) -> None:
        """Test async_map is the same as map."""
        ok = Ok(21)

        async def double(x: int) -> int:
            return x * 2

        result1 = await ok.map(double)
        result2 = await ok.async_map(double)
        assert result1 == result2


class TestResultCombinatorsIntegration:
    """Integration tests combining multiple new combinators."""

    def test_filter_and_inspect_err(self) -> None:
        """Test filter followed by inspect_err."""
        errors: list[str] = []

        result: Result[int, str] = Ok(5)
        filtered = result.filter(lambda x: x > 10, "too small").inspect_err(
            lambda e: errors.append(f"Error: {e}")
        )

        assert filtered.is_err()
        assert errors == ["Error: too small"]

    def test_filter_ok_or_pattern(self) -> None:
        """Test filter followed by ok_or for safe extraction."""
        result: Result[int, str] = Ok(5)
        filtered = result.filter(lambda x: x > 0, "negative")
        value = filtered.ok_or(0)
        assert value == 5

    def test_filter_ok_or_err_pattern(self) -> None:
        """Test filter followed by ok_or with error path."""
        result: Result[int, str] = Ok(-5)
        filtered = result.filter(lambda x: x > 0, "negative")
        value = filtered.ok_or(0)
        assert value == 0

    @pytest.mark.asyncio
    async def test_filter_and_async_map(self) -> None:
        """Test filter followed by async_map."""

        async def fetch_double(x: int) -> int:
            return x * 2

        result: Result[int, str] = Ok(5)
        processed = await result.filter(lambda x: x > 0, "negative").async_map(
            fetch_double
        )

        assert processed.unwrap() == 10

    def test_inspect_and_filter_chain(self) -> None:
        """Test inspect followed by filter."""
        logs: list[str] = []

        result: Result[int, str] = Ok(5)
        processed = (
            result.inspect(lambda x: logs.append(f"Original: {x}"))
            .filter(lambda x: x > 0, "negative")
            .inspect(lambda x: logs.append(f"After filter: {x}"))
        )

        assert processed.is_ok()
        assert logs == ["Original: 5", "After filter: 5"]


class TestResultFromException:
    """Tests for Result.from_exception() class method."""

    def test_from_exception_returns_err(self) -> None:
        """Test from_exception wraps exception in Err."""
        result = Result.from_exception(ValueError("test error"))
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)

    def test_from_exception_with_string_error(self) -> None:
        """Test from_exception with string error type."""
        result = Result.from_exception(RuntimeError("runtime failed"))
        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, RuntimeError)
        assert str(err) == "runtime failed"

    def test_from_exception_preserves_exception_message(self) -> None:
        """Test from_exception preserves exception message."""
        result = Result.from_exception(KeyError("missing key"))
        err = result.unwrap_err()
        assert isinstance(err, KeyError)

    def test_from_exception_type_inference(self) -> None:
        """Test from_exception type inference works."""
        result: Result[int, Exception] = Result.from_exception(ValueError("test"))
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)

    def test_from_exception_ok_type_parameter(self) -> None:
        """Test from_exception ok_type parameter is accepted."""
        result = Result.from_exception(OSError("io failed"), ok_type=int)
        assert result.is_err()
        assert isinstance(result.unwrap_err(), OSError)


class TestOkInspectSideEffects:
    """Tests for Ok.inspect() side effects."""

    def test_inspect_calls_side_effect(self) -> None:
        """Test inspect calls side effect with Ok value."""
        calls: list[int] = []

        result: Result[int, str] = Ok(42)
        result.inspect(calls.append)

        assert calls == [42]

    def test_inspect_returns_self(self) -> None:
        """Test inspect returns same Ok instance."""
        result: Result[int, str] = Ok(42)
        inspected = result.inspect(lambda _x: None)

        assert inspected is result

    def test_inspect_chaining(self) -> None:
        """Test chaining inspect with other operations."""
        results: list[str] = []

        result: Result[int, str] = Ok(5)
        result = result.inspect(lambda x: results.append(f"got {x}"))
        result = result.map_sync(lambda x: x * 2)
        result = result.inspect(lambda x: results.append(f"mapped {x}"))

        assert result.unwrap() == 10
        assert results == ["got 5", "mapped 10"]


class TestOkAsyncMap:
    """Tests for Ok.async_map method alias."""

    @pytest.mark.asyncio
    async def test_async_map_alias_works(self) -> None:
        """Test async_map is an alias for map."""
        ok = Ok(10)

        async def transform(x: int) -> int:
            return x + 5

        result = await ok.async_map(transform)
        assert result.unwrap() == 15

    @pytest.mark.asyncio
    async def test_async_map_on_err_returns_err(self) -> None:
        """Test async_map alias on Err returns Err."""
        err = Err("error")

        async def transform(x: int) -> int:
            return x * 2

        result = await err.async_map(transform)
        assert result.is_err()
        assert result.unwrap_err() == "error"


class TestErrAsyncMap:
    """Tests for Err.async_map method alias."""

    @pytest.mark.asyncio
    async def test_async_map_alias_on_err(self) -> None:
        """Test async_map alias preserves Err."""
        err = Err("failure")

        async def transform(x: int) -> int:
            return x * 2

        result = await err.async_map(transform)
        assert result.is_err()
        assert result.unwrap_err() == "failure"
