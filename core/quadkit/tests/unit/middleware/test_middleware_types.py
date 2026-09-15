"""Tests for middleware types."""

from collections.abc import Awaitable

from quadkit.middleware.types import (
    C,
    MiddlewareCallable,
    NextHandler,
)


class TestMiddlewareTypes:
    """Tests for middleware type definitions."""

    def test_next_handler_is_type_alias(self) -> None:
        """Test NextHandler type alias."""

        async def handler(request: str) -> str:
            return request

        assert callable(handler)
        next_handler: NextHandler = handler
        assert next_handler is not None

    def test_middleware_callable_is_type_alias(self) -> None:
        """Test MiddlewareCallable type alias."""

        async def middleware(
            request: str,
            next_handler: NextHandler,
        ) -> str:
            return await next_handler(request)

        assert callable(middleware)
        middleware_callable: MiddlewareCallable = middleware
        assert middleware_callable is not None

    def test_type_var_c(self) -> None:
        """Test C TypeVar."""
        assert C is not None

    def test_types_exported(self) -> None:
        """Test that all types are in __all__."""
        from quadkit.middleware.types import __all__

        assert "C" in __all__
        assert "MiddlewareCallable" in __all__
        assert "NextHandler" in __all__

    def test_next_handler_signature(self) -> None:
        """Test NextHandler accepts any and returns Awaitable[Any]."""

        async def example_next(request: dict) -> dict:
            return {"status": "ok"}

        result = example_next({"test": True})
        assert isinstance(result, Awaitable)
        result.close()  # explicitly close the coroutine to avoid RuntimeWarning

    def test_middleware_callable_signature(self) -> None:
        """Test MiddlewareCallable signature with context and next."""

        async def example_middleware(
            context: dict,
            next_handler: NextHandler,
        ) -> dict:
            return await next_handler(context)

        assert callable(example_middleware)
