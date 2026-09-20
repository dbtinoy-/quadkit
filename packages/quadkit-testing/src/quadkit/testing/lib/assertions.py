from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.result import Result

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


class TestAssertions:
    """Custom assertion helpers for testing."""

    @staticmethod
    def assert_eventually_true(
        condition_func: Callable[[], bool],
        timeout: float = 5.0,
        message: str = "Condition never became true",
    ) -> None:
        async def check() -> bool:
            from quadkit.testing.lib.async_helper import AsyncTestHelper

            return await AsyncTestHelper.wait_for_condition(condition_func, timeout)

        result = asyncio.run(check())
        assert result, message

    @staticmethod
    def assert_dict_contains_subset(
        subset: dict[str, Any],
        superset: dict[str, Any],
        message: str | None = None,
    ) -> None:
        for key, value in subset.items():
            if key not in superset:
                raise AssertionError(message or f"Key '{key}' not found in superset")
            if superset[key] != value:
                raise AssertionError(
                    message
                    or f"Value mismatch for key '{key}': expected {value}, got {superset[key]}",
                )

    @staticmethod
    async def assert_async_raises(
        exc_class: type[Exception],
        coro: Awaitable[Any],
        message: str | None = None,
    ) -> None:
        try:
            await coro
            msg = f"Expected {exc_class.__name__} but no exception was raised"
            raise AssertionError(msg)
        except exc_class as e:
            if message and str(e) != message:
                raise AssertionError(
                    f"Exception message mismatch: expected '{message}', got '{e!s}'",
                ) from None
        except Exception as e:
            msg = f"Expected {exc_class.__name__} but got {type(e).__name__}: {e}"
            raise AssertionError(msg) from e

    @staticmethod
    def assert_metrics_contain(
        metrics: dict[str, Any],
        key: str,
        min_value: float | None = None,
    ) -> None:
        assert key in metrics, f"MetricProtocol '{key}' not found"
        if min_value is not None:
            assert metrics[key] >= min_value, (
                f"MetricProtocol '{key}' value {metrics[key]} is less than minimum {min_value}"
            )


# ---------------------------------------------------------------------------
# Result assertion free functions
# ---------------------------------------------------------------------------


def assert_result_ok(result: Result[T, E]) -> T:
    """Unwrap and return the ``Ok`` value; raise ``AssertionError`` if ``Err``.

    Example::

        user = assert_result_ok(service.create_user(data))
        assert user.name == "Jo"
    """
    if result.is_err():
        msg = f"Expected Ok but got Err({result.unwrap_err()!r})"
        raise AssertionError(msg)
    return result.unwrap()


def assert_result_err(result: Result[Any, E]) -> E:
    """Unwrap and return the ``Err`` value; raise ``AssertionError`` if ``Ok``.

    Example::

        error = assert_result_err(service.create_user(bad_data))
        assert "email" in str(error)
    """
    if result.is_ok():
        msg = f"Expected Err but got Ok({result.unwrap()!r})"
        raise AssertionError(msg)
    return result.unwrap_err()


def assert_result_err_type(result: Result[Any, E], error_type: type[E]) -> None:
    """Assert the result is ``Err`` with an error of the given type.

    Example::

        assert_result_err_type(result, ValidationError)
    """
    error = assert_result_err(result)
    if not isinstance(error, error_type):
        msg = (
            f"Expected Err of type {error_type.__name__} but got "
            f"{type(error).__name__}: {error!r}"
        )
        raise AssertionError(  # noqa: TRY004
            msg
        )  # AssertionError is correct for test assertion helpers


def assert_healthy(results: dict[str, HealthCheckResult]) -> None:
    """Assert every health check in *results* passed.

    Example::

        results = await health_checker.run_all()
        assert_healthy(results)
    """
    unhealthy = {
        name: r for name, r in results.items() if r.status != HealthStatus.HEALTHY
    }
    if unhealthy:
        details = {name: r.status.value for name, r in unhealthy.items()}
        msg = f"Expected all health checks healthy but got: {details}"
        raise AssertionError(msg)


def assert_result_err_contains(
    result: Result[Any, E],
    substring: str,
) -> None:
    """Assert Result is Err and ``str(error)`` contains *substring*.

    Example::

        assert_result_err_contains(result, "not found")
    """
    error = assert_result_err(result)
    if substring not in str(error):
        msg = f"Expected error to contain {substring!r}, got {error!r}"
        raise AssertionError(msg)


def assert_result_ok_value(result: Result[T, E], expected: T) -> None:
    """Assert Result is Ok with a specific value.

    Example::

        assert_result_ok_value(result, expected_user)
    """
    value = assert_result_ok(result)
    if value != expected:
        msg = f"Expected Ok({expected!r}), got Ok({value!r})"
        raise AssertionError(msg)


def assert_all_ok(results: list[Result[T, E]]) -> list[T]:
    """Assert every Result in *results* is Ok and return the unwrapped values.

    Example::

        values = assert_all_ok([service.find(id) for id in ids])
    """
    values: list[T] = []
    for i, result in enumerate(results):
        if result.is_err():
            msg = f"Result[{i}] is Err({result.unwrap_err()!r})"
            raise AssertionError(msg)
        values.append(result.unwrap())
    return values


def assert_result_maps_to(
    result: Result[T, E],
    mapper: Callable[[T], U],
    expected: U,
) -> None:
    """Assert the Ok value transforms to *expected* via *mapper*.

    Example::

        assert_result_maps_to(result, lambda u: u.email, "user@example.com")
    """
    value = assert_result_ok(result)
    mapped = mapper(value)
    if mapped != expected:
        msg = f"Expected mapped value {expected!r}, got {mapped!r}"
        raise AssertionError(msg)


# ---------------------------------------------------------------------------
# Short-form aliases (idiomatic test-assertion API)
# ---------------------------------------------------------------------------


def assert_ok(result: Result[T, E]) -> T:
    """Assert *result* is ``Ok`` and return the inner value.

    Short alias for :func:`assert_result_ok`. Intended for tests that
    want concise, idiomatic assertions::

        user = assert_ok(service.find_user("123"))
        assert user.email == "test@example.com"

    Args:
        result: The ``Result`` to inspect.

    Returns:
        The unwrapped ``Ok`` value.

    Raises:
        AssertionError: If *result* is ``Err``.
    """
    return assert_result_ok(result)


def assert_err(result: Result[Any, E], error_type: type[E] | None = None) -> E:
    """Assert *result* is ``Err``, optionally checking the error type.

    Short alias combining :func:`assert_result_err` and
    :func:`assert_result_err_type`. Intended for tests that want concise,
    idiomatic assertions::

        error = assert_err(service.find_user("missing"), UserNotFound)
        assert error.user_id == "missing"

    Args:
        result: The ``Result`` to inspect.
        error_type: When provided, asserts that the error is an instance
            of this type.

    Returns:
        The unwrapped ``Err`` value.

    Raises:
        AssertionError: If *result* is ``Ok``, or if *error_type* is given
            and the error is not an instance of that type.
    """
    error = assert_result_err(result)
    if error_type is not None and not isinstance(error, error_type):
        msg = (
            f"Expected Err of type {error_type.__name__} but got "
            f"{type(error).__name__}: {error!r}"
        )
        raise AssertionError(msg)
    return error
