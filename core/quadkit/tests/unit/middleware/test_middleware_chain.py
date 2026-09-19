"""Unit tests for MiddlewareChain."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.middleware.core.chain import MiddlewareChain


async def _identity(ctx: Any) -> Any:
    """Trivial terminal handler — returns context unchanged."""
    return ctx


class TestMiddlewareChainBuild:
    """Tests for MiddlewareChain.build() creating immutable pipeline."""

    def test_build_returns_pipeline(self) -> None:
        """build() returns a MiddlewarePipeline snapshot of current state."""
        from quadkit.app.pipeline import MiddlewarePipeline

        chain = MiddlewareChain([AsyncMock()])
        pipeline = chain.build()
        assert isinstance(pipeline, MiddlewarePipeline)
        assert len(pipeline) == 1

    def test_build_is_snapshot(self) -> None:
        """Subsequent add() calls do not affect already-built pipelines."""
        chain = MiddlewareChain()
        pipeline_before = chain.build()
        chain.add(AsyncMock())
        pipeline_after = chain.build()
        assert len(pipeline_before) == 0
        assert len(pipeline_after) == 1

    def test_build_immutable_after_creation(self) -> None:
        """The built pipeline cannot be modified by later chain changes."""
        chain = MiddlewareChain()
        pipeline = chain.build()
        chain.add(AsyncMock())
        assert len(pipeline) == 0

    def test_build_with_multiple_middleware(self) -> None:
        """build() captures all middleware added so far."""
        chain = MiddlewareChain()
        chain.add(AsyncMock()).add(AsyncMock()).add(AsyncMock())
        pipeline = chain.build()
        assert len(pipeline) == 3


class TestMiddlewareChainClear:
    """Tests for MiddlewareChain.clear() behavior."""

    def test_clear_removes_all(self) -> None:
        """clear() removes all middleware from the chain."""
        chain = MiddlewareChain([AsyncMock(), AsyncMock()])
        chain.clear()
        assert len(chain) == 0

    def test_clear_then_add(self) -> None:
        """clear() followed by add() works correctly."""
        chain = MiddlewareChain([AsyncMock()])
        chain.clear()
        chain.add(AsyncMock())
        assert len(chain) == 1

    def test_clear_on_empty_chain(self) -> None:
        """clear() on empty chain is a no-op."""
        chain = MiddlewareChain()
        chain.clear()
        assert len(chain) == 0


class TestMiddlewareChainMultiple:
    """Tests for independent builds."""

    def test_multiple_builds_independent(self) -> None:
        """Multiple build() calls produce independent pipelines."""
        chain = MiddlewareChain()
        chain.add(AsyncMock())

        pipeline_a = chain.build()
        chain.add(AsyncMock())
        pipeline_b = chain.build()

        assert len(pipeline_a) == 1
        assert len(pipeline_b) == 2

    def test_parallel_pipelines_isolated(self) -> None:
        """Built pipelines are isolated snapshots at build time."""
        chain = MiddlewareChain([AsyncMock()])

        pipeline_1 = chain.build()
        pipeline_2 = chain.build()

        assert len(pipeline_1) == 1
        assert len(pipeline_2) == 1
        assert pipeline_1 is not pipeline_2


@pytest.mark.asyncio
class TestMiddlewareChainExecution:
    """Integration-style tests for build() + execute()."""

    async def test_build_and_execute_works(self) -> None:
        """Built pipeline executes middleware correctly."""
        chain = MiddlewareChain()

        async def mark_processed(request: dict, next_handler: Any) -> Any:
            request["processed"] = True
            return await next_handler(request)

        chain.add(mark_processed)
        result = await chain.build().execute({}, _identity)
        assert result.get("processed") is True

    async def test_empty_chain_passes_through(self) -> None:
        """Empty chain passes context to terminal handler."""
        chain = MiddlewareChain()
        result = await chain.build().execute("request", _identity)
        assert result == "request"
