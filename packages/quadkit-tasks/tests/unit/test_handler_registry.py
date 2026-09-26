"""Tests for HandlerRegistry."""

import pytest

from quadkit.tasks.execution.registry import HandlerRegistry


@pytest.fixture
def registry() -> HandlerRegistry:
    """Create a HandlerRegistry instance."""
    return HandlerRegistry()


class TestHandlerRegistryUnregister:
    """Tests for unregister functionality."""

    def test_unregister_removes_handler(self, registry: HandlerRegistry) -> None:
        """Test unregister removes a registered handler."""

        async def handler() -> None:
            pass

        registry.register("test-task", handler)
        assert "test-task" in registry

        result = registry.unregister("test-task")
        assert result is not None
        assert "test-task" not in registry

    def test_unregister_absent_is_noop(self, registry: HandlerRegistry) -> None:
        """Test unregistering a non-existent key is a no-op."""
        result = registry.unregister("never-registered")
        assert result is None

    def test_remove_is_alias_for_unregister(self, registry: HandlerRegistry) -> None:
        """Test remove() method is an alias for unregister()."""

        async def handler() -> None:
            pass

        registry.register("test-task", handler)
        result = registry.remove("test-task")
        assert result is True
        assert "test-task" not in registry
