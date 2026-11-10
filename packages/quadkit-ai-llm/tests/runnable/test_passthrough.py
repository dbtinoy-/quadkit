"""Tests for RunnablePassthrough."""
from __future__ import annotations

import pytest


class TestRunnablePassthrough:
    """Tests for RunnablePassthrough."""

    def test_passthrough_returns_input(self) -> None:
        """Passthrough should return input unchanged."""
        from quadkit.ai.llm.runnable.passthrough import RunnablePassthrough

        passthrough = RunnablePassthrough()
        result = passthrough.invoke("test")
        assert result == "test"

    @pytest.mark.asyncio
    async def test_passthrough_ainvoke(self) -> None:
        """Passthrough should work with ainvoke."""
        from quadkit.ai.llm.runnable.passthrough import RunnablePassthrough

        passthrough = RunnablePassthrough()
        result = await passthrough.ainvoke("test")
        assert result == "test"

    def test_passthrough_with_name(self) -> None:
        """Passthrough with name should return dict with key."""
        from quadkit.ai.llm.runnable.passthrough import RunnablePassthrough

        passthrough = RunnablePassthrough(name="output")
        result = passthrough.invoke("test")
        assert result == {"output": "test"}

    @pytest.mark.asyncio
    async def test_passthrough_with_name_ainvoke(self) -> None:
        """Passthrough with name should work with ainvoke."""
        from quadkit.ai.llm.runnable.passthrough import RunnablePassthrough

        passthrough = RunnablePassthrough(name="output")
        result = await passthrough.ainvoke("test")
        assert result == {"output": "test"}
