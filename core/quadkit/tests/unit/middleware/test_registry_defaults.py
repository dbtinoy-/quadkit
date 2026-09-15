from __future__ import annotations

from quadkit.middleware.core.registry import MiddlewareRegistry


class TestMiddlewareRegistryDefaults:
    def test_with_defaults_returns_registry(self) -> None:
        registry = MiddlewareRegistry.with_defaults()
        assert isinstance(registry, MiddlewareRegistry)

    def test_with_defaults_has_logging(self) -> None:
        registry = MiddlewareRegistry.with_defaults()
        assert registry.has("logging")

    def test_with_defaults_has_correlation_id(self) -> None:
        registry = MiddlewareRegistry.with_defaults()
        assert registry.has("correlation_id")

    def test_with_defaults_has_timing(self) -> None:
        registry = MiddlewareRegistry.with_defaults()
        assert registry.has("timing")

    def test_with_defaults_priority_order(self) -> None:
        registry = MiddlewareRegistry.with_defaults()
        # Get middleware in priority order (all() returns priority-ordered list)
        middleware = registry.all()
        # Expected order: LoggingMiddleware (10) < CorrelationIdMiddleware (20) < TimingMiddleware (90)
        from quadkit.middleware.builtins import (
            CorrelationIdMiddleware,
            LoggingMiddleware,
            TimingMiddleware,
        )

        assert isinstance(middleware[0], LoggingMiddleware)
        assert isinstance(middleware[1], CorrelationIdMiddleware)
        assert isinstance(middleware[2], TimingMiddleware)

    def test_empty_init_has_no_defaults(self) -> None:
        registry = MiddlewareRegistry()
        assert len(registry.names()) == 0
