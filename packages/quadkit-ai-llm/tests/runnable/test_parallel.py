"""Tests for RunnableParallel."""
from __future__ import annotations

import pytest

from quadkit.ai.llm.runnable.lambda_ import RunnableLambda


class TestRunnableParallel:
    """Tests for RunnableParallel."""

    def test_parallel_sync_invoke(self) -> None:
        """Parallel should invoke all runnables synchronously."""
        from quadkit.ai.llm.runnable.parallel import RunnableParallel

        parallel = RunnableParallel(
            upper=RunnableLambda(lambda x: x.upper()),
            lower=RunnableLambda(lambda x: x.lower()),
        )
        result = parallel.invoke("Hello")
        assert result == {"upper": "HELLO", "lower": "hello"}

    @pytest.mark.asyncio
    async def test_parallel_async_invoke(self) -> None:
        """Parallel should invoke all runnables asynchronously."""
        from quadkit.ai.llm.runnable.parallel import RunnableParallel

        parallel = RunnableParallel(
            upper=RunnableLambda(lambda x: x.upper()),
            lower=RunnableLambda(lambda x: x.lower()),
        )
        result = await parallel.ainvoke("Hello")
        assert result == {"upper": "HELLO", "lower": "hello"}

    def test_parallel_empty(self) -> None:
        """Parallel with no runnables should return empty dict."""
        from quadkit.ai.llm.runnable.parallel import RunnableParallel

        parallel = RunnableParallel()
        result = parallel.invoke("test")
        assert result == {}
