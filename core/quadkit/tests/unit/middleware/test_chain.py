"""Unit tests for MiddlewareChain and MiddlewareRegistry."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.middleware.core.chain import MiddlewareChain
from quadkit.middleware.core.registry import MiddlewareRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _identity(ctx: Any) -> Any:
    """Trivial terminal handler — returns context unchanged."""
    return ctx


# ---------------------------------------------------------------------------
# MiddlewareChain
# ---------------------------------------------------------------------------


class TestMiddlewareChain:
    """Tests for :class:`~quadkit.middleware.core.chain.MiddlewareChain`."""

    def test_chain_creation(self) -> None:
        """Empty chain has zero middleware."""
        chain = MiddlewareChain()
        assert chain is not None
        assert len(chain) == 0

    def test_chain_with_initial_middleware(self) -> None:
        """Chain seeded with one middleware has length 1."""
        middleware = AsyncMock()
        chain = MiddlewareChain([middleware])
        assert len(chain) == 1

    def test_chain_add_middleware(self) -> None:
        """add() increments chain length and returns self."""
        chain = MiddlewareChain()
        middleware = AsyncMock()
        returned = chain.add(middleware)
        assert len(chain) == 1
        assert returned is chain

    def test_chain_clear(self) -> None:
        """clear() removes all middleware."""
        chain = MiddlewareChain([AsyncMock(), AsyncMock()])
        chain.clear()
        assert len(chain) == 0

    def test_chain_build_returns_pipeline(self) -> None:
        """build() returns a MiddlewarePipeline snapshot of current state."""
        from quadkit.app.pipeline import MiddlewarePipeline

        chain = MiddlewareChain([AsyncMock()])
        pipeline = chain.build()
        assert isinstance(pipeline, MiddlewarePipeline)
        assert len(pipeline) == 1

    def test_chain_build_is_snapshot(self) -> None:
        """Subsequent add() calls do not affect already-built pipelines."""
        chain = MiddlewareChain()
        pipeline_before = chain.build()
        chain.add(AsyncMock())
        pipeline_after = chain.build()
        assert len(pipeline_before) == 0
        assert len(pipeline_after) == 1

    @pytest.mark.asyncio
    async def test_chain_execute_empty(self) -> None:
        """Empty chain passes context through to the terminal handler."""
        chain = MiddlewareChain()
        result = await chain.build().execute("request", _identity)
        assert result == "request"

    @pytest.mark.asyncio
    async def test_chain_execute_with_middleware(self) -> None:
        """Middleware in the chain can mutate the context."""
        chain = MiddlewareChain()

        async def mark_processed(request: dict, next_handler: Any) -> Any:
            request["processed"] = True
            return await next_handler(request)

        chain.add(mark_processed)
        result = await chain.build().execute({}, _identity)
        assert result.get("processed") is True

    @pytest.mark.asyncio
    async def test_chain_execute_multiple(self) -> None:
        """Multiple middleware all run in order."""
        chain = MiddlewareChain()

        async def first(request: dict, next_handler: Any) -> Any:
            request["first"] = True
            return await next_handler(request)

        async def second(request: dict, next_handler: Any) -> Any:
            request["second"] = True
            return await next_handler(request)

        chain.add(first).add(second)
        result = await chain.build().execute({}, _identity)
        assert result.get("first") is True
        assert result.get("second") is True

    @pytest.mark.asyncio
    async def test_chain_short_circuit(self) -> None:
        """Middleware can short-circuit the chain by not calling next_handler."""
        chain = MiddlewareChain()

        async def short_circuit(request: Any, next_handler: Any) -> str:
            return "early_return"

        chain.add(short_circuit)
        result = await chain.build().execute({}, _identity)
        assert result == "early_return"


# ---------------------------------------------------------------------------
# MiddlewareRegistry
# ---------------------------------------------------------------------------


class TestMiddlewareRegistry:
    """Tests for :class:`~quadkit.middleware.core.registry.MiddlewareRegistry`."""

    def test_registry_creation(self) -> None:
        """Registry can be created and starts empty."""
        registry = MiddlewareRegistry()
        assert registry is not None
        assert len(registry.names()) == 0

    def test_registry_register_middleware(self) -> None:
        """Registered middleware is discoverable via has()."""
        registry = MiddlewareRegistry()
        middleware = AsyncMock()
        registry.register("test_middleware", middleware)
        assert registry.has("test_middleware")

    def test_registry_get_middleware(self) -> None:
        """get() returns the registered middleware instance."""
        registry = MiddlewareRegistry()
        middleware = AsyncMock()
        registry.register("test_middleware", middleware)
        retrieved = registry.get("test_middleware")
        assert retrieved is middleware

    def test_registry_get_nonexistent_raises(self) -> None:
        """get() raises KeyError when the name is not registered."""
        registry = MiddlewareRegistry()
        assert not registry.has("nonexistent")
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_registry_names(self) -> None:
        """names() returns all registered middleware names (sorted)."""
        registry = MiddlewareRegistry()
        middleware = AsyncMock()

        registry.register("middleware_one", middleware)
        registry.register("middleware_two", middleware)

        names = registry.names()
        assert "middleware_one" in names
        assert "middleware_two" in names

    def test_registry_priority_order(self) -> None:
        """all() returns middleware in ascending priority order."""
        registry = MiddlewareRegistry()
        mw_high = AsyncMock()
        mw_low = AsyncMock()

        registry.register("high_priority", mw_high, priority=10)
        registry.register("low_priority", mw_low, priority=90)

        ordered = registry.all()
        assert ordered[0] is mw_high
        assert ordered[1] is mw_low

    def test_registry_unregister(self) -> None:
        """unregister() removes and returns the middleware."""
        registry = MiddlewareRegistry()
        middleware = AsyncMock()
        registry.register("mw", middleware)
        removed = registry.unregister("mw")
        assert removed is middleware
        assert not registry.has("mw")

    def test_registry_duplicate_raises(self) -> None:
        """Registering the same name twice raises ValueError."""
        registry = MiddlewareRegistry()
        registry.register("mw", AsyncMock())
        with pytest.raises(ValueError, match="already registered"):
            registry.register("mw", AsyncMock())

    def test_registry_build_chain(self) -> None:
        """build_chain() converts the registry into a MiddlewareChain."""
        registry = MiddlewareRegistry()
        registry.register("a", AsyncMock(), priority=1)
        registry.register("b", AsyncMock(), priority=2)
        chain = registry.build_chain()
        assert len(chain) == 2
