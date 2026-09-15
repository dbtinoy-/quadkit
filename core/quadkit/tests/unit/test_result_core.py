"""Result core semantics: Ok/Err construction, match, expect, equality."""

"""Tests for Result types (Ok, Err, Result)."""

import pytest

from quadkit.result import Err, Ok, Result
from quadkit.result.errors import UnwrapError




class TestOk:
    """Tests for Ok result type."""

    def test_is_ok(self) -> None:
        """Test that Ok.is_ok() returns True."""
        result: Result[int, str] = Ok(42)
        assert result.is_ok() is True

    def test_is_err(self) -> None:
        """Test that Ok.is_err() returns False."""
        result: Result[int, str] = Ok(42)
        assert result.is_err() is False

    def test_unwrap(self) -> None:
        """Test unwrap returns the value."""
        result: Result[int, str] = Ok(42)
        assert result.unwrap() == 42

    def test_unwrap_err_raises(self) -> None:
        """Test that unwrap_err raises UnwrapError on Ok."""
        result: Result[int, str] = Ok(42)
        with pytest.raises(UnwrapError, match="Called unwrap_err"):
            result.unwrap_err()

    def test_unwrap_or_returns_value(self) -> None:
        """Test that unwrap_or returns the value, not default."""
        result: Result[int, str] = Ok(42)
        assert result.unwrap_or(0) == 42

    def test_unwrap_or_else_returns_value(self) -> None:
        """Test that unwrap_or_else returns value, not calling fn."""
        result: Result[int, str] = Ok(42)
        assert result.unwrap_or_else(lambda _e: 0) == 42

    def test_map(self) -> None:
        """Test map_sync transforms the value."""
        result: Result[int, str] = Ok(21)
        mapped = result.map_sync(lambda x: x * 2)
        assert mapped.unwrap() == 42

    def test_map_err_on_ok(self) -> None:
        """Test that map_err on Ok returns Ok unchanged."""
        result: Result[int, str] = Ok(42)
        mapped = result.map_err(lambda e: e.upper())
        assert mapped.is_ok()
        assert mapped.unwrap() == 42

    def test_and_then(self) -> None:
        """Test and_then_sync chains operations."""
        result: Result[int, str] = Ok(21)
        chained = result.and_then_sync(lambda x: Ok(x * 2))
        assert chained.unwrap() == 42

    def test_or_else_on_ok(self) -> None:
        """Test that or_else_sync on Ok returns Ok, not calling fn."""
        result: Result[int, str] = Ok(42)
        assert result.or_else_sync(lambda _e: Ok(0)).unwrap() == 42


class TestErr:
    """Tests for Err result type."""

    def test_is_ok(self) -> None:
        """Test that Err.is_ok() returns False."""
        result: Result[int, str] = Err("error")
        assert result.is_ok() is False

    def test_is_err(self) -> None:
        """Test that Err.is_err() returns True."""
        result: Result[int, str] = Err("error")
        assert result.is_err() is True

    def test_unwrap_raises(self) -> None:
        """Test that unwrap raises UnwrapError on Err."""
        result: Result[int, str] = Err("error")
        with pytest.raises(UnwrapError, match="error"):
            result.unwrap()

    def test_unwrap_err(self) -> None:
        """Test unwrap_err returns the error."""
        result: Result[int, str] = Err("error")
        assert result.unwrap_err() == "error"

    def test_unwrap_or_returns_default(self) -> None:
        """Test that unwrap_or returns default on Err."""
        result: Result[int, str] = Err("error")
        assert result.unwrap_or(42) == 42

    def test_unwrap_or_else_calls_fn(self) -> None:
        """Test that unwrap_or_else calls fn on Err."""
        result: Result[int, str] = Err("error")
        assert result.unwrap_or_else(len) == 5

    def test_map_on_err(self) -> None:
        """Test that map_sync on Err returns Err unchanged."""
        result: Result[int, str] = Err("error")
        mapped = result.map_sync(lambda x: x * 2)
        assert mapped.is_err()
        assert mapped.unwrap_err() == "error"

    def test_map_err(self) -> None:
        """Test map_err transforms the error."""
        result: Result[int, str] = Err("error")
        mapped = result.map_err(lambda e: e.upper())
        assert mapped.is_err()
        assert mapped.unwrap_err() == "ERROR"

    def test_and_then_on_err(self) -> None:
        """Test that and_then_sync on Err returns Err, not calling fn."""
        result: Result[int, str] = Err("error")
        assert result.and_then_sync(lambda x: Ok(x * 2)).is_err()

    def test_or_else(self) -> None:
        """Test or_else_sync on Err calls fn and returns new Result."""
        result: Result[int, str] = Err("error")
        recovered = result.or_else_sync(lambda _e: Ok(42))  # noqa: ARG005
        assert recovered.is_ok()
        assert recovered.unwrap() == 42


class TestResultFlatten:
    """Tests for Result.flatten()."""

    def test_flatten_nested_ok(self) -> None:
        """Test flattening nested Ok values."""
        outer: Result[Result[int, str], str] = Ok(Ok(42))
        flattened = outer.flatten()
        assert flattened.is_ok()
        assert flattened.unwrap() == 42

    def test_flatten_nested_err_in_ok(self) -> None:
        """Test flattening when Ok contains Err."""
        outer: Result[Result[int, str], str] = Ok(Err("inner"))
        flattened = outer.flatten()
        assert flattened.is_err()
        assert flattened.unwrap_err() == "inner"

    def test_flatten_outer_err(self) -> None:
        """Test flattening when outer is Err."""
        outer: Result[Result[int, str], str] = Err("outer")
        flattened = outer.flatten()
        assert flattened.is_err()
        assert flattened.unwrap_err() == "outer"

    def test_flatten_non_result_value(self) -> None:
        """Test flattening when value is not a Result."""
        outer: Result[int, str] = Ok(42)
        flattened = outer.flatten()
        assert flattened.is_ok()
        assert flattened.unwrap() == 42


class TestResultMatch:
    """Tests for Result.match() method."""

    def test_match_ok(self) -> None:
        """Test match on Ok."""
        result: Result[int, str] = Ok(42)
        message = result.match(
            ok=lambda v: f"Got: {v}",
            err=lambda e: f"Error: {e}",
        )
        assert message == "Got: 42"

    def test_match_err(self) -> None:
        """Test match on Err."""
        result: Result[int, str] = Err("error")
        message = result.match(
            ok=lambda v: f"Got: {v}",
            err=lambda e: f"Error: {e}",
        )
        assert message == "Error: error"


class TestOkAsyncMethods:
    """Tests for Ok async methods (canonical map/and_then/or_else)."""

    @pytest.mark.asyncio
    async def test_map(self) -> None:
        """Test map transforms the value asynchronously."""
        ok = Ok(21)

        async def double(x: int) -> int:
            return x * 2

        result = await ok.map(double)
        assert result.unwrap() == 42

    @pytest.mark.asyncio
    async def test_and_then(self) -> None:
        """Test and_then chains operations asynchronously."""
        ok = Ok(21)

        async def double(x: int) -> Result[int, str]:
            return Ok(x * 2)

        result = await ok.and_then(double)
        assert result.unwrap() == 42

    @pytest.mark.asyncio
    async def test_and_then_returns_err(self) -> None:
        """Test and_then can return Err."""
        ok = Ok(21)

        async def fail(_x: int) -> Result[int, str]:
            return Err("failed")

        result = await ok.and_then(fail)
        assert result.is_err()
        assert result.unwrap_err() == "failed"

    @pytest.mark.asyncio
    async def test_or_else_on_ok(self) -> None:
        """Test or_else on Ok returns self."""
        ok = Ok(42)

        async def fallback(_e: str) -> Result[int, str]:
            return Ok(0)

        result = await ok.or_else(fallback)
        assert result.unwrap() == 42


class TestErrAsyncMethods:
    """Tests for Err async methods (canonical map/and_then/or_else)."""

    @pytest.mark.asyncio
    async def test_map_on_err(self) -> None:
        """Test map on Err returns same Err."""
        err = Err("error")

        async def double(x: int) -> int:
            return x * 2

        result = await err.map(double)
        assert result.is_err()
        assert result.unwrap_err() == "error"

    @pytest.mark.asyncio
    async def test_and_then_on_err(self) -> None:
        """Test and_then on Err returns same Err."""
        err = Err("error")

        async def double(x: int) -> Result[int, str]:
            return Ok(x * 2)

        result = await err.and_then(double)
        assert result.is_err()
        assert result.unwrap_err() == "error"

    @pytest.mark.asyncio
    async def test_or_else(self) -> None:
        """Test or_else on Err calls function."""
        err = Err("error")

        async def recover(_e: str) -> Result[int, str]:
            return Ok(42)

        result = await err.or_else(recover)
        assert result.unwrap() == 42


class TestOkExpect:
    """Tests for Ok.expect()."""

    def test_expect_on_ok(self) -> None:
        """Test expect on Ok returns value."""
        ok: Result[int, str] = Ok(42)
        assert ok.expect("should not raise") == 42


class TestErrExpect:
    """Tests for Err.expect()."""

    def test_expect_raises_with_message(self) -> None:
        """Test expect on Err raises UnwrapError with custom message."""
        err: Result[int, str] = Err("error")
        with pytest.raises(UnwrapError, match="custom message"):
            err.expect("custom message")


class TestOkEquality:
    """Tests for Ok equality and hashing."""

    def test_eq_same_value(self) -> None:
        """Test Ok equality with same value."""
        assert Ok(42) == Ok(42)

    def test_eq_different_value(self) -> None:
        """Test Ok inequality with different value."""
        assert Ok(42) != Ok(100)

    def test_eq_different_type(self) -> None:
        """Test Ok != Err."""
        assert Ok(42) != Err(42)

    def test_hash_same_value(self) -> None:
        """Test hash equality for same value."""
        assert hash(Ok(42)) == hash(Ok(42))

    def test_can_use_in_set(self) -> None:
        """Test Ok can be used in set."""
        s = {Ok(1), Ok(2), Ok(1)}
        assert len(s) == 2


class TestErrEquality:
    """Tests for Err equality and hashing."""

    def test_eq_same_error(self) -> None:
        """Test Err equality with same error."""
        assert Err("error") == Err("error")

    def test_eq_different_error(self) -> None:
        """Test Err inequality with different error."""
        assert Err("error") != Err("different")

    def test_eq_different_type(self) -> None:
        """Test Err != Ok."""
        assert Err("error") != Ok("error")

    def test_hash_same_error(self) -> None:
        """Test hash equality for same error."""
        assert hash(Err("error")) == hash(Err("error"))


class TestOkRepr:
    """Tests for Ok repr."""

    def test_repr(self) -> None:
        """Test repr format."""
        assert repr(Ok(42)) == "Ok(42)"

    def test_repr_string(self) -> None:
        """Test repr with string value."""
        assert repr(Ok("test")) == "Ok('test')"


class TestErrRepr:
    """Tests for Err repr."""

    def test_repr(self) -> None:
        """Test repr format."""
        assert repr(Err("error")) == "Err('error')"


