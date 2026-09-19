"""Tests for quadkit.types module - type aliases and callables."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from quadkit.types import (
    ActionHandler,
    AsyncServiceFactory,
    ErrorHandler,
    FilterHandler,
    GuardFunction,
    MiddlewareFactory,
    ResultHandler,
    ServiceFactory,
)


class TestTypeAliases:
    """Test that type aliases are properly defined and usable."""

    def test_service_factory_is_callable(self) -> None:
        """ServiceFactory should be a callable type."""
        def my_factory() -> str:
            return "service"

        factory: ServiceFactory = my_factory
        result = factory()
        assert result == "service"

    def test_async_service_factory_is_callable(self) -> None:
        """AsyncServiceFactory should be a callable type."""
        async def my_async_factory() -> str:
            return "async_service"

        factory: AsyncServiceFactory = my_async_factory

        async def run_test() -> None:
            result = await factory()
            assert result == "async_service"

        asyncio.run(run_test())

    def test_middleware_factory_signature(self) -> None:
        """MiddlewareFactory should accept Any and return Awaitable[Any]."""
        async def my_middleware(context: Any) -> str:
            return "processed"

        factory: MiddlewareFactory = my_middleware

        async def run_test() -> None:
            result = await factory("test_context")
            assert result == "processed"

        asyncio.run(run_test())

    def test_guard_function_signature(self) -> None:
        """GuardFunction should accept Any and return Awaitable[bool]."""
        async def my_guard(context: Any) -> bool:
            return True

        guard: GuardFunction = my_guard

        async def run_test() -> None:
            result = await guard("test_context")
            assert result is True

        asyncio.run(run_test())

    def test_result_handler_signature(self) -> None:
        """ResultHandler should accept Any and return Awaitable[Any] | Any."""
        def sync_handler(value: Any) -> str:
            return f"handled {value}"

        async def async_handler(value: Any) -> str:
            return f"handled async {value}"

        handler: ResultHandler = sync_handler
        assert handler("test") == "handled test"

        handler2: ResultHandler = async_handler

        async def run_test() -> None:
            result = await handler2("test")
            assert result == "handled async test"

        asyncio.run(run_test())

    def test_error_handler_signature(self) -> None:
        """ErrorHandler should accept Any and return Awaitable[Any] | Any."""
        def sync_error_handler(error: Any) -> str:
            return f"error {error}"

        async def async_error_handler(error: Any) -> str:
            return f"error async {error}"

        handler: ErrorHandler = sync_error_handler
        assert handler("test_error") == "error test_error"

        handler2: ErrorHandler = async_error_handler

        async def run_test() -> None:
            result = await handler2("test_error")
            assert result == "error async test_error"

        asyncio.run(run_test())

    def test_action_handler_signature(self) -> None:
        """ActionHandler should accept variadic args and return Any."""
        def action_handler(*args: Any, **kwargs: Any) -> None:
            pass

        handler: ActionHandler = action_handler
        assert handler("arg1", key="value") is None

    def test_filter_handler_signature(self) -> None:
        """FilterHandler should accept variadic args and return Any."""
        def filter_handler(value: Any) -> int:
            return len(str(value))

        handler: FilterHandler = filter_handler
        assert handler("test") == 4


class TestTypeAliasesAreReExported:
    """Test that all type aliases are in __all__."""

    def test_all_contains_all_aliases(self) -> None:
        """All public type aliases should be in __all__."""
        import quadkit.types as types_module

        expected_exports = [
            "ActionHandler",
            "AsyncServiceFactory",
            "ErrorHandler",
            "FilterHandler",
            "GuardFunction",
            "MiddlewareFactory",
            "ResultHandler",
            "ServiceFactory",
        ]

        for name in expected_exports:
            assert hasattr(types_module, name), f"Missing: {name}"

        assert sorted(types_module.__all__) == sorted(expected_exports)