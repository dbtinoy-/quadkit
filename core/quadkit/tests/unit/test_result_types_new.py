"""Tests for Result type: Ok, Err, map, and_then, chaining, and error handling."""

from __future__ import annotations

import pytest

from quadkit.result import Result
from quadkit.result import Err, Ok


# Custom error types for testing
class ValidationError(Exception):
    pass


class NotFoundError(Exception):
    pass


class TestResultConstruction:
    """Tests for Result construction (Ok, Err)."""

    @pytest.mark.asyncio
    async def test_ok_creates_successful_result(self) -> None:
        """Ok() creates a successful Result with a value."""
        result: Result[int, ValidationError] = Ok(42)

        assert result.is_ok() is True
        assert result.is_err() is False
        assert result.unwrap() == 42

    @pytest.mark.asyncio
    async def test_err_creates_failed_result(self) -> None:
        """Err() creates a failed Result with an error."""
        result: Result[int, ValidationError] = Err(ValidationError("invalid"))

        assert result.is_ok() is False
        assert result.is_err() is True
        assert isinstance(result.unwrap_err(), ValidationError)

    @pytest.mark.asyncio
    async def test_ok_with_none(self) -> None:
        """Ok() can hold None as a value."""
        result: Result[None, str] = Ok(None)

        assert result.is_ok() is True
        assert result.unwrap() is None


class TestResultMapSync:
    """Tests for map_sync: synchronous transformation of Ok value."""

    @pytest.mark.asyncio
    async def test_map_sync_transforms_ok_value(self) -> None:
        """map_sync applies function to Ok value, preserving error type."""
        result: Result[int, ValidationError] = Ok(10)
        mapped = result.map_sync(lambda x: x * 2)

        assert mapped.is_ok() is True
        assert mapped.unwrap() == 20

    @pytest.mark.asyncio
    async def test_map_sync_preserves_err(self) -> None:
        """map_sync returns Err unchanged (does not call function)."""
        result: Result[int, ValidationError] = Err(ValidationError("fail"))
        mapped = result.map_sync(lambda x: x * 2)

        assert mapped.is_err() is True
        assert isinstance(mapped.unwrap_err(), ValidationError)

    @pytest.mark.asyncio
    async def test_map_sync_changes_value_type(self) -> None:
        """map_sync can change the Ok value type."""
        result: Result[int, ValidationError] = Ok(100)
        mapped = result.map_sync(lambda x: str(x))

        assert mapped.is_ok() is True
        assert mapped.unwrap() == "100"


class TestResultAndThenSync:
    """Tests for and_then_sync: chaining synchronous operations."""

    @pytest.mark.asyncio
    async def test_and_then_sync_chains_ok_results(self) -> None:
        """and_then_sync chains a Result-returning function on Ok."""

        def safe_divide(x: int) -> Result[int, str]:
            if x == 0:
                return Err("division by zero")
            return Ok(100 // x)

        result: Result[int, str] = Ok(10)
        chained = result.and_then_sync(safe_divide)

        assert chained.is_ok() is True
        assert chained.unwrap() == 10

    @pytest.mark.asyncio
    async def test_and_then_sync_short_circuits_on_err(self) -> None:
        """and_then_sync returns Err without calling the function."""

        def should_not_be_called(x: int) -> Result[int, str]:
            return Err("should not reach")

        result: Result[int, str] = Err("initial error")
        chained = result.and_then_sync(should_not_be_called)

        assert chained.is_err() is True
        assert chained.unwrap_err() == "initial error"

    @pytest.mark.asyncio
    async def test_and_then_sync_produces_err(self) -> None:
        """and_then_sync can produce an Err from the chained function."""

        def failing_transform(x: int) -> Result[int, str]:
            return Err(f"invalid: {x}")

        result: Result[int, str] = Ok(5)
        chained = result.and_then_sync(failing_transform)

        assert chained.is_err() is True
        assert chained.unwrap_err() == "invalid: 5"


class TestResultMap:
    """Tests for async map: asynchronous transformation of Ok value."""

    @pytest.mark.asyncio
    async def test_map_applies_async_function(self) -> None:
        """map applies async function to Ok value."""

        async def async_transform(x: int) -> int:
            return x * 3

        result: Result[int, ValidationError] = Ok(7)
        mapped = await result.map(async_transform)

        assert mapped.is_ok() is True
        assert mapped.unwrap() == 21

    @pytest.mark.asyncio
    async def test_map_preserves_err(self) -> None:
        """map returns Err unchanged without calling async function."""

        async def async_transform(x: int) -> int:
            raise RuntimeError("should not be called")

        result: Result[int, ValidationError] = Err(ValidationError("fail"))
        mapped = await result.map(async_transform)

        assert mapped.is_err() is True


class TestResultAndThen:
    """Tests for async and_then: chaining async operations."""

    @pytest.mark.asyncio
    async def test_and_then_chains_async_operations(self) -> None:
        """and_then chains an async Result-returning function."""

        async def async_transform(x: int) -> Result[str, str]:
            return Ok(f"value: {x}")

        result: Result[int, str] = Ok(42)
        chained = await result.and_then(async_transform)

        assert chained.is_ok() is True
        assert chained.unwrap() == "value: 42"

    @pytest.mark.asyncio
    async def test_and_then_short_circuits_on_err(self) -> None:
        """and_then returns Err without calling the async function."""

        async def async_transform(x: int) -> Result[int, str]:
            return Err("transform error")

        result: Result[int, str] = Err("initial")
        chained = await result.and_then(async_transform)

        assert chained.is_err() is True
        assert chained.unwrap_err() == "initial"


class TestResultUnwrapOr:
    """Tests for unwrap_or and unwrap_or_else."""

    @pytest.mark.asyncio
    async def test_unwrap_or_returns_value_on_ok(self) -> None:
        """unwrap_or returns the Ok value, ignoring the default."""
        result: Result[int, str] = Ok(99)
        value = result.unwrap_or(0)

        assert value == 99

    @pytest.mark.asyncio
    async def test_unwrap_or_returns_default_on_err(self) -> None:
        """unwrap_or returns the default when result is Err."""
        result: Result[int, str] = Err("error")
        value = result.unwrap_or(42)

        assert value == 42

    @pytest.mark.asyncio
    async def test_unwrap_or_else_calls_function_on_err(self) -> None:
        """unwrap_or_else calls the function with the error."""
        result: Result[int, ValidationError] = Err(ValidationError("fail"))
        value = result.unwrap_or_else(lambda e: len(str(e)))

        assert value == 4  # "fail" has 4 characters


class TestResultMatch:
    """Tests for match: pattern matching on Result."""

    @pytest.mark.asyncio
    async def test_match_calls_ok_callback_on_ok(self) -> None:
        """match calls the ok callback with the value."""
        result: Result[int, str] = Ok(10)
        message = result.match(
            ok=lambda v: f"got value: {v}",
            err=lambda e: f"error: {e}",
        )

        assert message == "got value: 10"

    @pytest.mark.asyncio
    async def test_match_calls_err_callback_on_err(self) -> None:
        """match calls the err callback with the error."""
        result: Result[int, str] = Err("something went wrong")
        message = result.match(
            ok=lambda v: f"got value: {v}",
            err=lambda e: f"error: {e}",
        )

        assert message == "error: something went wrong"


class TestResultMapErr:
    """Tests for map_err: transforming the error type."""

    @pytest.mark.asyncio
    async def test_map_err_transforms_error(self) -> None:
        """map_err transforms the error type."""
        result: Result[int, ValidationError] = Err(ValidationError("invalid"))
        mapped = result.map_err(lambda e: str(e))

        assert mapped.is_err() is True
        assert mapped.unwrap_err() == "invalid"

    @pytest.mark.asyncio
    async def test_map_err_preserves_ok(self) -> None:
        """map_err returns Ok unchanged."""
        result: Result[int, ValidationError] = Ok(42)
        mapped = result.map_err(lambda e: str(e))

        assert mapped.is_ok() is True
        assert mapped.unwrap() == 42


class TestResultOrElse:
    """Tests for or_else: recovering from errors."""

    @pytest.mark.asyncio
    async def test_or_else_returns_ok_unchanged(self) -> None:
        """or_else returns Ok value without calling fallback."""
        result: Result[int, str] = Ok(100)

        def fallback(x: str) -> Result[int, str]:
            return Ok(-1)

        recovered = result.or_else_sync(fallback)
        assert recovered.is_ok() is True
        assert recovered.unwrap() == 100

    @pytest.mark.asyncio
    async def test_or_else_applies_fallback_on_err(self) -> None:
        """or_else calls fallback function on Err."""
        result: Result[int, str] = Err("error")

        def fallback(e: str) -> Result[int, str]:
            return Ok(len(e))

        recovered = result.or_else_sync(fallback)
        assert recovered.is_ok() is True
        assert recovered.unwrap() == 5  # "error" has 5 characters

    @pytest.mark.asyncio
    async def test_or_else_can_return_err_again(self) -> None:
        """or_else fallback can also return an Err."""
        result: Result[int, str] = Err("original")

        def fallback(e: str) -> Result[int, str]:
            return Err(f"fallback: {e}")

        recovered = result.or_else_sync(fallback)
        assert recovered.is_err() is True
        assert recovered.unwrap_err() == "fallback: original"


class TestResultInspect:
    """Tests for inspect: side-effects without consuming the result."""

    @pytest.mark.asyncio
    async def test_inspect_runs_on_ok(self) -> None:
        """inspect runs the function on Ok value, returning original."""
        called = False

        def side_effect(x: int) -> None:
            nonlocal called
            called = True

        result: Result[int, str] = Ok(42)
        returned = result.inspect(side_effect)

        assert called is True
        assert returned.unwrap() == 42

    @pytest.mark.asyncio
    async def test_inspect_skips_on_err(self) -> None:
        """inspect does not run on Err, returning original."""
        called = False

        def side_effect(x: int) -> None:
            nonlocal called
            called = True

        result: Result[int, str] = Err("error")
        returned = result.inspect(side_effect)

        assert called is False
        assert returned.unwrap_err() == "error"
