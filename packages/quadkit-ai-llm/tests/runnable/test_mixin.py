"""Tests for RunnableMixin and pipe operator."""
from __future__ import annotations

import pytest

from quadkit.result import Err, Ok, Result


class TestRunnableMixinPipe:
    """Tests for RunnableMixin pipe operator."""

    def test_pipe_returns_runnable_sequence(self) -> None:
        """Pipe operator should return RunnableSequence."""
        from quadkit.ai.llm.runnable.base import RunnableMixin

        class First(RunnableMixin):
            def invoke(self, input: str) -> str:
                return input.upper()

            async def ainvoke(self, input: str) -> str:
                return input.upper()

        class Second(RunnableMixin):
            def invoke(self, input: str) -> str:
                return input + "!"

            async def ainvoke(self, input: str) -> str:
                return input + "!"

        first = First()
        second = Second()

        result = first | second

        from quadkit.ai.llm.runnable.sequence import RunnableSequence
        assert isinstance(result, RunnableSequence)

    def test_pipe_chains_sync_execution(self) -> None:
        """Pipe should chain sync execution correctly."""
        from quadkit.ai.llm.runnable.base import RunnableMixin

        class First(RunnableMixin):
            def invoke(self, input: str) -> str:
                return input.upper()

            async def ainvoke(self, input: str) -> str:
                return input.upper()

        class Second(RunnableMixin):
            def invoke(self, input: str) -> str:
                return input + "!"

            async def ainvoke(self, input: str) -> str:
                return input + "!"

        result = First() | Second()

        output = result.invoke("hello")
        assert output == "HELLO!"

    @pytest.mark.asyncio
    async def test_pipe_chains_async_execution(self) -> None:
        """Pipe should chain async execution correctly."""
        from quadkit.ai.llm.runnable.base import RunnableMixin

        class First(RunnableMixin):
            def invoke(self, input: str) -> str:
                return input.upper()

            async def ainvoke(self, input: str) -> str:
                return input.upper()

        class Second(RunnableMixin):
            def invoke(self, input: str) -> str:
                return input + "!"

            async def ainvoke(self, input: str) -> str:
                return input + "!"

        result = First() | Second()

        output = await result.ainvoke("hello")
        assert output == "HELLO!"

    def test_pipe_short_circuits_on_err(self) -> None:
        """Pipe should short-circuit on Err result."""
        from quadkit.ai.llm.runnable.base import RunnableMixin

        class Failing(RunnableMixin):
            def invoke(self, input: str) -> Result[str, str]:
                return Err("failed")

            async def ainvoke(self, input: str) -> Result[str, str]:
                return Err("failed")

        class Second(RunnableMixin):
            def invoke(self, input: str) -> str:
                raise AssertionError("Should not reach")

            async def ainvoke(self, input: str) -> str:
                raise AssertionError("Should not reach")

        result = Failing() | Second()
        output = result.invoke("test")
        assert isinstance(output, Err)
        assert output.unwrap_err() == "failed"
