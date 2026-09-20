"""Test middleware registry functionality."""
from unittest.mock import Mock

from starlette.middleware.base import BaseHTTPMiddleware

from quadkit.web.middleware.base import MiddlewareRegistry


class DummyMiddleware(BaseHTTPMiddleware):
    """Dummy middleware for testing."""

    async def dispatch(self, request, call_next):
        return await call_next(request)


class ASGIMiddleware:
    """ASGI middleware for testing."""

    def __init__(self, app, some_option=None):
        self.app = app
        self.some_option = some_option

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


class TestMiddlewareRegistry:
    """Test middleware registry."""

    def test_prevents_duplicate_class_middleware(self):
        """Test class-based middleware can't be registered twice."""
        registry = MiddlewareRegistry()

        # First registration succeeds
        registry.register_middleware(DummyMiddleware)
        assert registry.is_registered(DummyMiddleware)

        # Second registration is skipped
        registry.register_middleware(DummyMiddleware)

        # Should only appear once in order
        order = registry.get_middleware_order()
        assert order.count("DummyMiddleware") == 1

    def test_prevents_duplicate_function_middleware(self):
        """Test function middleware can't be registered twice."""
        app = Mock()
        registry = MiddlewareRegistry()

        async def my_middleware(request, call_next):
            return await call_next(request)

        # First registration succeeds
        registry.register_function_middleware(app, my_middleware, name="my_middleware")
        assert registry.is_registered("my_middleware")

        # Second registration is skipped
        registry.register_function_middleware(app, my_middleware, name="my_middleware")

        # Should only appear once
        order = registry.get_middleware_order()
        assert order.count("my_middleware") == 1

    def test_tracks_middleware_order(self):
        """Test middleware order is tracked correctly."""
        registry = MiddlewareRegistry()

        class Middleware1(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                return await call_next(request)

        class Middleware2(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                return await call_next(request)

        registry.register_middleware(Middleware1)
        registry.register_middleware(Middleware2)

        order = registry.get_middleware_order()
        assert order == ["Middleware1", "Middleware2"]

    def test_function_middleware_uses_default_name(self):
        """Test function middleware uses function name as default."""
        app = Mock()
        registry = MiddlewareRegistry()

        async def test_middleware(request, call_next):
            return await call_next(request)

        registry.register_function_middleware(app, test_middleware)

        assert registry.is_registered("test_middleware")
        order = registry.get_middleware_order()
        assert "test_middleware" in order

    def test_mixed_middleware_types(self):
        """Test mixing class and function middleware."""
        app = Mock()
        registry = MiddlewareRegistry()

        # Add class middleware
        registry.register_middleware(DummyMiddleware)

        # Add function middleware
        async def func_mw(request, call_next):
            return await call_next(request)

        registry.register_function_middleware(app, func_mw, name="func_mw")

        # Check both are registered
        assert registry.is_registered(DummyMiddleware)
        assert registry.is_registered("func_mw")

        # Check order
        order = registry.get_middleware_order()
        assert order == ["DummyMiddleware", "func_mw"]

    def test_app_methods_called_correctly(self):
        """Test that middleware instantiation works correctly."""
        app = Mock()
        registry = MiddlewareRegistry()

        # Register ASGI middleware with options
        registry.register_middleware(ASGIMiddleware, some_option="value")

        # Check middleware was instantiated correctly during compose_app
        composed_app = registry.compose_app(app)

        # The composed app should be the ASGIMiddleware instance
        assert isinstance(composed_app, ASGIMiddleware)
        assert composed_app.some_option == "value"
        assert composed_app.app == app

        # Register function middleware
        async def func_mw(request, call_next):
            return await call_next(request)

        registry.register_function_middleware(app, func_mw)

        # Check app.middleware was called
        app.middleware.assert_called_once_with("http")
