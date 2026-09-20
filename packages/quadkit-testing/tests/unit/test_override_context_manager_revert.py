"""Test override() context manager reverts binding on exit.

override() provides a context manager to temporarily override a dependency
in the container. Upon context exit, it reverts the binding to its original
state (restored or removed).

This test suite validates:
1. Temporary override during context execution
2. Revert to original value on exit
3. Removal of new binding if service wasn't registered before
4. Safe handling of nested or sequential overrides
5. Proper exception handling doesn't prevent revert
"""

from __future__ import annotations

import pytest

from quadkit.di.container import Container
from quadkit.testing.harness.overrides import override


class SimpleService:
    """Simple test service without protocol requirements."""

    def __init__(self, name: str = "default") -> None:
        self.name = name

    def get_name(self) -> str:
        return self.name


class OtherService:
    """Another service for testing nested overrides."""

    def __init__(self, name: str = "other") -> None:
        self.name = name


class TestOverrideBasicFunction:
    """Test basic override() context manager functionality."""

    def test_override_temporarily_changes_registered_service(self) -> None:
        """Verify override() temporarily changes a registered service."""
        container = Container()
        original = SimpleService("original")
        container.singleton(SimpleService, instance=original)

        replacement = SimpleService("replacement")

        # Verify original is there before override
        assert container.resolve_sync(SimpleService) is original

        # During override, verify the registry changed
        with override(container, SimpleService, replacement):
            # Check the descriptor in registry
            descriptor = container._service_resolver._registry.get(SimpleService)
            assert descriptor is not None
            assert descriptor.instance is replacement

        # After exit, verify restored
        assert container.resolve_sync(SimpleService) is original

    def test_override_reverts_after_context_exit(self) -> None:
        """Verify override() reverts to original after context exit."""
        container = Container()
        original = SimpleService("original")
        container.singleton(SimpleService, instance=original)
        replacement = SimpleService("replacement")

        with override(container, SimpleService, replacement):
            descriptor = container._service_resolver._registry.get(SimpleService)
            assert descriptor.instance is replacement

        # After exit, should be reverted
        descriptor = container._service_resolver._registry.get(SimpleService)
        assert descriptor.instance is original

    def test_override_with_exception_still_reverts(self) -> None:
        """Verify override() reverts even if exception is raised in context."""
        container = Container()
        original = SimpleService("original")
        container.singleton(SimpleService, instance=original)
        replacement = SimpleService("replacement")

        try:
            with override(container, SimpleService, replacement):
                descriptor = container._service_resolver._registry.get(SimpleService)
                assert descriptor.instance is replacement
                raise ValueError("test error")
        except ValueError:
            pass

        # Should still be reverted despite exception
        descriptor = container._service_resolver._registry.get(SimpleService)
        assert descriptor.instance is original

    def test_override_removes_binding_if_not_registered(self) -> None:
        """Verify override() removes binding if service wasn't registered."""
        container = Container()

        # Service not registered at all
        assert container._service_resolver._registry.get(SimpleService) is None

        replacement = SimpleService("replacement")

        with override(container, SimpleService, replacement):
            # During override, it should be in registry
            descriptor = container._service_resolver._registry.get(SimpleService)
            assert descriptor is not None
            assert descriptor.instance is replacement

        # After exit, should be removed
        assert container._service_resolver._registry.get(SimpleService) is None


class TestOverrideSequential:
    """Test sequential override() calls."""

    def test_override_multiple_times_independently(self) -> None:
        """Verify override() can be used multiple times without state leakage."""
        container = Container()
        original = SimpleService("original")
        container.singleton(SimpleService, instance=original)

        # First override
        with override(container, SimpleService, SimpleService("first")):
            descriptor = container._service_resolver._registry.get(SimpleService)
            assert descriptor.instance.get_name() == "first"

        # After first, check reverted
        assert container.resolve_sync(SimpleService) is original

        # Second override
        with override(container, SimpleService, SimpleService("second")):
            descriptor = container._service_resolver._registry.get(SimpleService)
            assert descriptor.instance.get_name() == "second"

        # After both, back to original
        assert container.resolve_sync(SimpleService) is original

    def test_override_preserves_raised_exceptions(self) -> None:
        """Verify override() properly re-raises exceptions from context."""
        container = Container()
        original = SimpleService("original")
        container.singleton(SimpleService, instance=original)

        with pytest.raises(RuntimeError, match="expected error"):
            with override(container, SimpleService, SimpleService("temp")):
                raise RuntimeError("expected error")


class TestOverrideNesting:
    """Test nested override() contexts."""

    def test_nested_same_service_reverts_properly(self) -> None:
        """Verify nested overrides of same service revert in correct order."""
        container = Container()
        original = SimpleService("original")
        container.singleton(SimpleService, instance=original)

        with override(container, SimpleService, SimpleService("outer")):
            descriptor = container._service_resolver._registry.get(SimpleService)
            assert descriptor.instance.get_name() == "outer"

            with override(container, SimpleService, SimpleService("inner")):
                descriptor = container._service_resolver._registry.get(SimpleService)
                assert descriptor.instance.get_name() == "inner"

            # After inner exit, should revert to outer
            descriptor = container._service_resolver._registry.get(SimpleService)
            assert descriptor.instance.get_name() == "outer"

        # After outer exit, should revert to original
        assert container.resolve_sync(SimpleService) is original

    def test_nested_different_services_independent(self) -> None:
        """Verify nested overrides of different services work independently."""
        container = Container()
        original = SimpleService("a_original")
        container.singleton(SimpleService, instance=original)

        with override(container, SimpleService, SimpleService("a_override")):
            descriptor = container._service_resolver._registry.get(SimpleService)
            assert descriptor.instance.get_name() == "a_override"

            with override(container, OtherService, OtherService("b_override")):
                # Both should be overridden
                desc_a = container._service_resolver._registry.get(SimpleService)
                desc_b = container._service_resolver._registry.get(OtherService)
                assert desc_a.instance.get_name() == "a_override"
                assert desc_b.instance.name == "b_override"

            # Inner override reverted, outer still active
            descriptor = container._service_resolver._registry.get(SimpleService)
            assert descriptor.instance.get_name() == "a_override"

        # Both reverted
        assert container.resolve_sync(SimpleService) is original
        assert container._service_resolver._registry.get(OtherService) is None


class TestOverrideIntegration:
    """Integration tests for override() with realistic usage patterns."""

    def test_override_in_test_isolation(self) -> None:
        """Verify override() enables test isolation without container reset."""
        container = Container()
        service = SimpleService("production")
        container.singleton(SimpleService, instance=service)

        # Simulate multiple independent tests using same container
        test_1_called = False
        test_2_called = False

        # "Test 1" — override for isolation
        with override(container, SimpleService, SimpleService("test-1")):
            assert container.resolve_sync(SimpleService).get_name() == "test-1"
            test_1_called = True

        # "Test 2" — different override
        with override(container, SimpleService, SimpleService("test-2")):
            assert container.resolve_sync(SimpleService).get_name() == "test-2"
            test_2_called = True

        # Production state restored
        assert test_1_called
        assert test_2_called
        assert container.resolve_sync(SimpleService).get_name() == "production"

    def test_override_with_multiple_service_types(self) -> None:
        """Verify override() handles multiple service types correctly."""
        container = Container()
        svc_a = SimpleService("a")
        svc_b = OtherService("b")
        container.singleton(SimpleService, instance=svc_a)
        container.singleton(OtherService, instance=svc_b)

        with override(container, SimpleService, SimpleService("a_override")):
            with override(container, OtherService, OtherService("b_override")):
                desc_a = container._service_resolver._registry.get(SimpleService)
                desc_b = container._service_resolver._registry.get(OtherService)
                assert desc_a.instance.get_name() == "a_override"
                assert desc_b.instance.name == "b_override"

        # Both restored
        assert container.resolve_sync(SimpleService) is svc_a
        assert container.resolve_sync(OtherService) is svc_b

    def test_override_exception_safety_with_multiple_services(self) -> None:
        """Verify all overrides revert even if exception in multi-service context."""
        container = Container()
        svc_a = SimpleService("a")
        svc_b = OtherService("b")
        container.singleton(SimpleService, instance=svc_a)
        container.singleton(OtherService, instance=svc_b)

        try:
            with override(container, SimpleService, SimpleService("a_temp")):
                with override(container, OtherService, OtherService("b_temp")):
                    raise ValueError("something went wrong")
        except ValueError:
            pass

        # Both safely reverted despite exception
        assert container.resolve_sync(SimpleService) is svc_a
        assert container.resolve_sync(OtherService) is svc_b
