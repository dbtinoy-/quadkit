"""Tests for middleware module."""

from quadkit.middleware import MiddlewareModule


class TestMiddlewareModule:
    def test_middleware_module_exists(self) -> None:
        assert MiddlewareModule is not None
