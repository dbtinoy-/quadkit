"""Tests for WebProvider middleware registry exposure."""

from __future__ import annotations

import asyncio

from quadkit.di.container import Container
from quadkit.web.config import RateLimitConfig, WebConfig
from quadkit.web.di.provider import WebProvider
from quadkit.web.middleware.base import MiddlewareRegistry
from quadkit.web.middleware.di_scope import DIScopeMiddleware
from quadkit.web.middleware.registry import MiddlewareAdapterRegistry


class _DummyMiddleware:
    """Stand-in middleware used to exercise registration."""

    def __init__(self, app: object = None) -> None:
        self.app = app


def _register_and_boot(provider: WebProvider, container: Container) -> None:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(provider.register(container))
        loop.run_until_complete(provider.boot(container))
    finally:
        loop.run_until_complete(provider.shutdown())
        loop.close()


def test_middleware_registry_bound_with_default_and_user_middleware() -> None:
    """Registry exposes DIScopeMiddleware plus user-supplied middleware."""
    provider = WebProvider(
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False)),
        middleware=[_DummyMiddleware],
    )
    container = Container()
    _register_and_boot(provider, container)

    registry = container.resolve_sync(MiddlewareRegistry)
    assert DIScopeMiddleware.__name__ in registry.get_middleware_order()
    assert _DummyMiddleware.__name__ in registry.get_middleware_order()
    assert container.resolve_sync(MiddlewareAdapterRegistry) is not None


def test_middleware_registry_accepts_middleware_instances() -> None:
    """Instance middleware is registered by its class name."""
    provider = WebProvider(
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False)),
        middleware=[_DummyMiddleware()],
    )
    container = Container()
    _register_and_boot(provider, container)

    registry = container.resolve_sync(MiddlewareRegistry)
    assert _DummyMiddleware.__name__ in registry.get_middleware_order()
