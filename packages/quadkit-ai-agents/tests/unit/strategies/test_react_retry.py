"""Tests for ReAct strategy tool retry behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.ai.agents.strategies.react import ReActStrategy


class TestReActToolRetry:
    """Tests for retry behavior in ReAct._execute_tool."""

    @pytest.mark.asyncio
    async def test_retries_on_connection_error_then_succeeds(self) -> None:
        """Tool retries on ConnectionError and succeeds on second attempt."""
        call_count = 0

        async def flaky_execute(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection refused")
            return "tool output"

        tool = MagicMock()
        tool.name = "test_tool"
        tool.execute = flaky_execute

        strategy = ReActStrategy(tool_max_retries=3)
        record = await strategy._execute_tool("test_tool", {}, {"test_tool": tool})

        assert record.succeeded is True
        assert record.result == "tool output"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_returns_error_record(self) -> None:
        """Returns error ToolExecutionRecord after all retries fail."""

        async def always_fail(**kwargs):
            raise ConnectionError("Always fails")

        tool = MagicMock()
        tool.name = "flaky_tool"
        tool.execute = always_fail

        strategy = ReActStrategy(tool_max_retries=2)
        record = await strategy._execute_tool("flaky_tool", {}, {"flaky_tool": tool})

        assert record.succeeded is False
        assert record.error is not None
        assert "2 retries" in record.error
        assert "ConnectionError" in record.error
        assert "flaky_tool" not in record.error
        assert "Always fails" not in record.error
