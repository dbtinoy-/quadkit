"""Unit tests for middleware routing."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.middleware.builtins.routing import ConditionalMiddleware


async def _identity(ctx: Any) -> Any:
    """Trivial terminal handler — returns context unchanged."""
    return ctx


class TestConditionalMiddleware:
    """Tests for :class:`~quadkit.middleware.builtins.routing.ConditionalMiddleware`."""

    def test_creation_with_defaults(self) -> None:
        """ConditionalMiddleware can be created with default name."""
        mw = ConditionalMiddleware(AsyncMock(), lambda ctx: True)
        assert mw._name == "conditional"

    def test_creation_with_custom_name(self) -> None:
        """ConditionalMiddleware accepts custom name."""
        mw = ConditionalMiddleware(AsyncMock(), lambda ctx: True, name="custom")
        assert mw._name == "custom"

    @pytest.mark.asyncio
    async def test_predicate_true_runs_middleware(self) -> None:
        """When predicate returns True, wrapped middleware executes."""
        inner = AsyncMock(return_value="inner_result")
        predicate = Mock(return_value=True)
        chain = ConditionalMiddleware(inner, predicate)

        result = await chain("context", _identity)

        inner.assert_awaited_once_with("context", _identity)
        predicate.assert_called_once_with("context")
        assert result == "inner_result"

    @pytest.mark.asyncio
    async def test_predicate_false_skips_middleware(self) -> None:
        """When predicate returns False, wrapped middleware is skipped."""
        inner = AsyncMock()

        def predicate(ctx: Any) -> bool:
            return False

        chain = ConditionalMiddleware(inner, predicate)

        result = await chain("context", _identity)

        inner.assert_not_called()
        assert result == "context"

    @pytest.mark.asyncio
    async def test_predicate_receives_context(self) -> None:
        """Predicate receives the context object."""
        received_context = None

        def capture_predicate(ctx: dict[str, Any]) -> bool:
            nonlocal received_context
            received_context = ctx
            return True

        inner = AsyncMock()
        chain = ConditionalMiddleware(inner, capture_predicate)

        test_context = {"key": "value"}
        await chain(test_context, _identity)

        assert received_context is test_context

    @pytest.mark.asyncio
    async def test_passes_next_handler_correctly(self) -> None:
        """When skipping, next_handler is called with context."""
        inner = AsyncMock()

        def predicate(ctx: Any) -> bool:
            return False

        chain = ConditionalMiddleware(inner, predicate)

        next_handler = AsyncMock(return_value="next_result")
        result = await chain("ctx", next_handler)

        next_handler.assert_awaited_once_with("ctx")
        assert result == "next_result"

    @pytest.mark.asyncio
    async def test_multiple_calls_respect_predicate(self) -> None:
        """Each invocation re-evaluates the predicate."""
        inner = AsyncMock()
        call_count = 0

        def toggle_predicate(ctx: dict[str, Any]) -> bool:
            nonlocal call_count
            call_count += 1
            return ctx.get("enabled", False)

        chain = ConditionalMiddleware(inner, toggle_predicate)

        await chain({"enabled": False}, _identity)
        await chain({"enabled": True}, _identity)
        await chain({"enabled": False}, _identity)

        assert inner.call_count == 1
        assert call_count == 3
