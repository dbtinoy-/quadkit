"""Tests for task backends registry."""

from quadkit.tasks.backends.registry import TaskBackendRegistry
from quadkit.tasks.config import TaskBackendConfig, TaskConfig


class TestTaskBackendRegistry:
    """Tests for TaskBackendRegistry."""

    def test_empty_registry(self) -> None:
        """Test creating an empty registry."""
        registry = TaskBackendRegistry()
        assert registry._factories == {}
        assert registry.available_backends() == []

    def test_with_defaults(self) -> None:
        """Test with_defaults creates registry with default backends."""
        registry = TaskBackendRegistry.with_defaults()

        backends = registry.available_backends()
        assert len(backends) == 4
        assert "memory" in backends
        assert "redis" in backends
        assert "rabbitmq" in backends
        assert "postgres" in backends

    def test_register(self) -> None:
        """Test registering a custom backend."""
        registry = TaskBackendRegistry()

        def custom_factory(config: TaskConfig):
            return object()

        registry.register("custom", custom_factory)

        assert "custom" in registry.available_backends()

    def test_register_overrides_existing(self) -> None:
        """Test registering with existing key overrides."""
        registry = TaskBackendRegistry.with_defaults()

        def custom_factory(config: TaskConfig):
            return object()

        registry.register("memory", custom_factory)

        # Should not raise and should have memory
        assert "memory" in registry.available_backends()

    def test_available_backends_sorted(self) -> None:
        """Test available_backends returns sorted list."""
        registry = TaskBackendRegistry()
        registry.register("z_backend", lambda cfg: object())
        registry.register("a_backend", lambda cfg: object())
        registry.register("m_backend", lambda cfg: object())

        backends = registry.available_backends()
        assert backends == ["a_backend", "m_backend", "z_backend"]
