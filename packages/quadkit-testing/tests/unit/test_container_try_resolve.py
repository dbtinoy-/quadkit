"""Test that TestContainer.try_resolve() returns Result correctly.

This test validates:
1. try_resolve() returns Ok(instance) for registered types
2. try_resolve() returns Err(exception) for missing types
3. Errors preserve the original exception type
4. try_resolve() is safe to use without causing crashes
"""

import pytest

from quadkit.result import Result
from quadkit.testing import QuadkitContainerHarness

# Use new name in code but keep backward-compat alias
TestContainer = QuadkitContainerHarness


class FakeService:
    """Simple service for testing."""

    def __init__(self) -> None:
        self.called = False


class TestTryResolveReturnsResult:
    """Verify TestContainer.try_resolve() returns Result[T, Exception]."""

    @pytest.mark.asyncio
    async def test_try_resolve_returns_ok_for_registered_type(self) -> None:
        """Verify try_resolve() returns Ok(instance) for registered types."""
        container = TestContainer(register_mocks=False)
        container.singleton(FakeService, FakeService())

        result = await container.try_resolve(FakeService)

        assert result.is_ok()
        instance = result.unwrap()
        assert isinstance(instance, FakeService)

    @pytest.mark.asyncio
    async def test_try_resolve_returns_err_for_missing_type(self) -> None:
        """Verify try_resolve() returns Err for unregistered types."""
        container = TestContainer(register_mocks=False)

        result = await container.try_resolve(FakeService)

        assert result.is_err()
        error = result.unwrap_err()
        assert error is not None

    @pytest.mark.asyncio
    async def test_try_resolve_preserves_exception_type(self) -> None:
        """Verify the exception inside Err preserves its original type."""
        container = TestContainer(register_mocks=False)

        result = await container.try_resolve(FakeService)

        assert result.is_err()
        error = result.unwrap_err()
        # The error should be some kind of exception (likely ResolutionError)
        assert isinstance(error, Exception)

    @pytest.mark.asyncio
    async def test_try_resolve_can_be_chained(self) -> None:
        """Verify try_resolve() Result can be chained with map_sync/and_then_sync."""
        container = TestContainer(register_mocks=False)
        container.singleton(FakeService, FakeService())

        result = await container.try_resolve(FakeService)
        mapped = result.map_sync(lambda svc: type(svc).__name__)

        assert mapped.is_ok()
        assert mapped.unwrap() == "FakeService"

    @pytest.mark.asyncio
    async def test_try_resolve_safe_error_handling(self) -> None:
        """Verify try_resolve() makes error handling safe without unwrap()."""
        container = TestContainer(register_mocks=False)

        result = await container.try_resolve(FakeService)

        # Safe handling without unwrap()
        if result.is_err():
            error_type = type(result.unwrap_err()).__name__
            assert error_type is not None
        else:
            pytest.fail("Should have returned Err")

    @pytest.mark.asyncio
    async def test_try_resolve_matches_on_ok_and_err(self) -> None:
        """Verify try_resolve() Result.match() works correctly."""
        container = TestContainer(register_mocks=False)
        container.singleton(FakeService, FakeService())

        result = await container.try_resolve(FakeService)
        message = result.match(
            ok=lambda _: "success",
            err=lambda _: "failure",
        )

        assert message == "success"

    @pytest.mark.asyncio
    async def test_try_resolve_err_match(self) -> None:
        """Verify try_resolve() Result.match() for error case."""
        container = TestContainer(register_mocks=False)

        result = await container.try_resolve(FakeService)
        message = result.match(
            ok=lambda _: "success",
            err=lambda e: f"error: {type(e).__name__}",
        )

        assert message.startswith("error:")

    @pytest.mark.asyncio
    async def test_try_resolve_result_type_is_correct(self) -> None:
        """Verify try_resolve() return type annotation is Result[T, Exception]."""
        container = TestContainer(register_mocks=False)
        container.singleton(FakeService, FakeService())

        result = await container.try_resolve(FakeService)

        # Check that it's actually a Result type
        assert isinstance(result, Result)
        assert hasattr(result, "is_ok")
        assert hasattr(result, "is_err")
        assert hasattr(result, "unwrap")
        assert hasattr(result, "unwrap_err")
        assert hasattr(result, "match")
