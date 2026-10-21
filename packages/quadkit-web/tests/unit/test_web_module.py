"""Tests for web module."""

from __future__ import annotations

from quadkit.contracts.web import WebRateLimiterProtocol
from quadkit.di.module import DynamicModule
from quadkit.web import WebModule


class TestWebModule:
    def test_web_module_exists(self) -> None:
        assert WebModule is not None

    def test_configure_returns_dynamic_module(self) -> None:
        result = WebModule.configure()
        assert isinstance(result, DynamicModule)
        assert result.module is WebModule

    def test_configure_with_custom_host(self) -> None:
        result = WebModule.configure(host="127.0.0.1")
        assert isinstance(result, DynamicModule)

    def test_configure_with_custom_port(self) -> None:
        result = WebModule.configure(port=9000)
        assert isinstance(result, DynamicModule)

    def test_configure_with_controllers(self) -> None:
        class DummyController:
            pass

        result = WebModule.configure(controllers=[DummyController])
        assert isinstance(result, DynamicModule)

    def test_configure_discovers_controllers_and_websockets_from_packages(
        self, monkeypatch
    ) -> None:
        class DummyController:
            pass

        class DummyWebSocket:
            _is_websocket_handler = True
            _ws_path = "/ws/dummy"

        monkeypatch.setattr(
            "quadkit.web.routing.discovery.discover_controllers",
            lambda _packages: [DummyController],
        )
        monkeypatch.setattr(
            "quadkit.web.routing.discovery.discover_websocket_handlers",
            lambda _packages: [DummyWebSocket],
        )

        result = WebModule.configure(discover=["dummy.package"])
        assert isinstance(result, DynamicModule)
        provider = result.providers[0]
        assert provider.controllers == [DummyController]
        assert provider.websocket_handlers == [DummyWebSocket]

    def test_legacy_auto_discover_factory_is_removed(self) -> None:
        assert not hasattr(WebModule, "auto_discover")

class TestRateLimiterExportOwnership:
    """A module exports what its own providers register.

    `WebModule` declared `WebRateLimiterProtocol` while `RateLimitProvider` —
    `RateLimitModule`'s provider — was what bound it. The export was therefore
    unresolvable in an application that used `WebModule` alone (its documented
    usage), and invisible to consumers in one that
    also added `RateLimitModule`, whose descriptor exported nothing at all.
    """

    def test_web_module_does_not_export_a_limiter_it_never_binds(self) -> None:
        assert WebRateLimiterProtocol not in WebModule.configure().exports
        assert WebRateLimiterProtocol not in WebModule.stub().exports

    def test_rate_limit_module_exports_the_limiter_it_binds(self) -> None:
        from quadkit.web.integrations.throttle import RateLimitModule

        descriptor = RateLimitModule.configure(backend="memory")

        assert WebRateLimiterProtocol in descriptor.exports
        assert descriptor.is_global is True
