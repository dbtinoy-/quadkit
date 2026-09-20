"""Test that TestContainer.bind() validates runtime-checkable protocols.

This test validates:
1. bind() accepts implementations that satisfy runtime-checkable protocols
2. bind() rejects implementations that don't satisfy runtime-checkable protocols
3. bind() raises TypeError with clear error message on validation failure
4. bind() doesn't validate non-runtime-checkable protocols (mypy will catch)
"""

from typing import Protocol, runtime_checkable

import pytest

from quadkit.testing.harness.container import QuadkitContainerHarness

# Use new name in code but keep backward-compat alias
TestContainer = QuadkitContainerHarness


@runtime_checkable
class CacheService(Protocol):
    """Example runtime-checkable protocol."""

    async def get(self, key: str) -> str | None:
        """Get value from cache."""
        ...

    async def set(self, key: str, value: str) -> None:
        """Set value in cache."""
        ...


class CorrectCacheImpl:
    """Correct implementation of CacheService."""

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str) -> None:
        pass


class IncorrectCacheImpl:
    """Incorrect implementation - missing required methods."""


class NonRuntimeCheckableProtocol(Protocol):
    """Protocol without @runtime_checkable."""

    async def do_something(self) -> None:
        """Do something."""
        ...


class TestContainerBindProtocolValidation:
    """Verify TestContainer.bind() validates protocol implementations."""

    def test_bind_accepts_correct_protocol_implementation(self) -> None:
        """Verify bind() accepts implementations that satisfy the protocol."""
        container = TestContainer(register_mocks=False)
        impl = CorrectCacheImpl()

        # Should not raise
        container.bind(CacheService, impl)

    def test_bind_rejects_incorrect_protocol_implementation(self) -> None:
        """Verify bind() rejects implementations that don't satisfy the protocol."""
        container = TestContainer(register_mocks=False)
        impl = IncorrectCacheImpl()

        # Should raise TypeError
        with pytest.raises(TypeError) as exc_info:
            container.bind(CacheService, impl)

        error_msg = str(exc_info.value)
        assert "does not implement protocol" in error_msg
        assert "CacheService" in error_msg

    def test_bind_error_includes_helpful_message(self) -> None:
        """Verify bind() error message includes helpful debugging info."""
        container = TestContainer(register_mocks=False)
        impl = IncorrectCacheImpl()

        with pytest.raises(TypeError) as exc_info:
            container.bind(CacheService, impl)

        error_msg = str(exc_info.value)
        # Error should mention:
        # 1. The implementation object
        # 2. The protocol name
        # 3. Suggestion to check methods/attributes
        assert "IncorrectCacheImpl" in error_msg or "does not implement" in error_msg
        assert "all required methods" in error_msg or "attributes" in error_msg

    def test_bind_skips_validation_for_non_runtime_checkable_protocol(self) -> None:
        """Verify bind() doesn't validate non-@runtime_checkable protocols.

        Type checking (mypy/pyright) handles non-runtime-checkable protocols.
        bind() should accept any implementation for those protocols.
        """
        container = TestContainer(register_mocks=False)

        class AnyImpl:
            async def do_something(self) -> None:
                pass

        # Should not validate - non-runtime-checkable protocols are type-checked only
        container.bind(NonRuntimeCheckableProtocol, AnyImpl())

    @pytest.mark.asyncio
    async def test_bind_makes_implementation_resolvable(self) -> None:
        """Verify that after bind(), the protocol can be resolved."""
        container = TestContainer(register_mocks=False)
        impl = CorrectCacheImpl()

        container.bind(CacheService, impl)

        # Should be resolvable as the same singleton instance
        resolved = await container.try_resolve(CacheService)
        assert resolved.is_ok()
        assert resolved.unwrap() is impl

    def test_bind_with_instance_not_class(self) -> None:
        """Verify bind() works with instances, not just classes."""
        container = TestContainer(register_mocks=False)
        impl_instance = CorrectCacheImpl()

        # bind() should validate the instance
        container.bind(CacheService, impl_instance)

    def test_bind_validates_all_methods_present(self) -> None:
        """Verify bind() checks for all required methods of the protocol."""
        container = TestContainer(register_mocks=False)

        class PartialImpl:
            async def get(self, key: str) -> str | None:
                return None

            # Missing set() method

        # Should fail because set() is missing
        with pytest.raises(TypeError):
            container.bind(CacheService, PartialImpl())

    def test_bind_error_is_raised_not_returned(self) -> None:
        """Verify bind() raises immediately, doesn't return an error Result."""
        container = TestContainer(register_mocks=False)
        impl = IncorrectCacheImpl()

        # bind() should raise, not return a Result
        try:
            container.bind(CacheService, impl)
            pytest.fail("Should have raised TypeError")
        except TypeError:
            pass  # Expected

    def test_bind_protocol_instance_check_is_runtime(self) -> None:
        """Verify bind() uses isinstance() check for runtime_checkable protocols."""
        container = TestContainer(register_mocks=False)
        impl = CorrectCacheImpl()

        # This should work because isinstance(impl, CacheService) should be True
        # when CacheService has the required methods
        assert isinstance(impl, CacheService)
        container.bind(CacheService, impl)
