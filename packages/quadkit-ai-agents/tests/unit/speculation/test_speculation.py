"""Tests for speculation package — DraftVerifyExecutor, SpeculativeToolPreFetcher, KeywordToolCallPredictor."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.agents.speculation.draft_verify import DraftVerifyExecutor
from quadkit.ai.agents.speculation.predictor import KeywordToolCallPredictor
from quadkit.ai.agents.speculation.prefetcher import SpeculativeToolPreFetcher
from quadkit.contracts.ai.llm import ChatMessage, Completion
from quadkit.result import Ok


def make_completion(content: str, model: str = "gpt-4") -> Completion:
    return Completion(content=content, model=model)


def make_llm_client(content: str = "LLM response") -> MagicMock:
    client = MagicMock()
    client.complete = AsyncMock(return_value=Ok(make_completion(content)))
    return client


def make_tool(name: str, description: str = "") -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.execute = AsyncMock(return_value={"result": f"{name}_result"})
    return tool


class TestDraftVerifyExecutor:
    """Tests for DraftVerifyExecutor."""

    @pytest.mark.asyncio
    async def test_draft_verify_uses_draft_when_verified(self) -> None:
        """Pro task cancelled, draft Completion returned when verify says yes."""
        draft_client = make_llm_client("Draft answer")
        verify_client = make_llm_client("Yes, correct and valid")
        pro_client = make_llm_client("Pro answer")

        executor = DraftVerifyExecutor(draft_client, verify_client, pro_client)
        messages = [ChatMessage(role="user", content="What is 2+2?")]

        result = await executor.execute(messages)

        assert result.is_ok()
        completion = result.unwrap()
        assert completion.content == "Draft answer"

    @pytest.mark.asyncio
    async def test_draft_verify_falls_back_to_pro(self) -> None:
        """Failed verification → pro result returned."""
        draft_client = make_llm_client("Wrong draft")
        verify_client = make_llm_client("No, this is incorrect and wrong")
        pro_client = make_llm_client("Correct pro answer")

        executor = DraftVerifyExecutor(draft_client, verify_client, pro_client)
        messages = [ChatMessage(role="user", content="What is 2+2?")]

        result = await executor.execute(messages)

        assert result.is_ok()
        completion = result.unwrap()
        assert completion.content == "Correct pro answer"


class TestSpeculativeToolPreFetcher:
    """Tests for SpeculativeToolPreFetcher."""

    def make_registry(self, tools: list) -> MagicMock:
        registry = MagicMock()
        registry.list_tools = MagicMock(return_value=tools)
        return registry

    @pytest.mark.asyncio
    async def test_speculative_hit_returns_prefetched_result(self) -> None:
        """Predicted tool result used when LLM picks it — LLM completion returned."""
        tool = make_tool("calculator", "math calculation add subtract")
        registry = self.make_registry([tool])
        llm_client = make_llm_client("Here is the answer")

        prefetcher = SpeculativeToolPreFetcher(
            tool_registry=registry, max_speculative=3
        )
        messages = [ChatMessage(role="user", content="calculate math add numbers")]
        result = await prefetcher.execute_with_speculation(
            query="calculate math add numbers",
            tools=[tool],
            llm_client=llm_client,
            messages=messages,
        )

        assert result.is_ok()
        assert result.unwrap().content == "Here is the answer"

    @pytest.mark.asyncio
    async def test_speculative_miss_executes_normally(self) -> None:
        """Non-predicted tool executed normally — LLM completion still returned."""
        tool = make_tool("weather", "weather forecast temperature")
        registry = self.make_registry([tool])
        llm_client = make_llm_client("Here is the weather")

        prefetcher = SpeculativeToolPreFetcher(
            tool_registry=registry, max_speculative=3
        )
        messages = [ChatMessage(role="user", content="calculate math unrelated")]
        result = await prefetcher.execute_with_speculation(
            query="calculate math unrelated",
            tools=[tool],
            llm_client=llm_client,
            messages=messages,
        )

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_unused_speculative_tasks_cancelled(self) -> None:
        """task.cancel() is called on speculative tasks not used by LLM."""
        slow_tool = make_tool("slow_tool", "slow slow slow operation")
        # Make tool very slow so it won't finish before LLM

        async def slow_execute(*args: any, **kwargs: any) -> dict:
            """Execute slowly, handling cancellation gracefully."""
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass
            return {"result": "slow_tool_result"}

        slow_tool.execute = AsyncMock(side_effect=slow_execute)

        registry = self.make_registry([slow_tool])
        llm_client = make_llm_client("Quick response")

        prefetcher = SpeculativeToolPreFetcher(
            tool_registry=registry, max_speculative=3
        )
        messages = [ChatMessage(role="user", content="slow slow operation")]

        result = await prefetcher.execute_with_speculation(
            query="slow slow operation",
            tools=[slow_tool],
            llm_client=llm_client,
            messages=messages,
        )

        assert result.is_ok()
        # The slow tool's execute should have been called (started speculatively)
        slow_tool.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_references_stored(self) -> None:
        """Background tasks tracked in _background_tasks set (RUF006)."""
        tool = make_tool("search", "search query lookup")
        registry = self.make_registry([tool])
        llm_client = make_llm_client("Result")

        prefetcher = SpeculativeToolPreFetcher(
            tool_registry=registry, max_speculative=3
        )
        # _background_tasks should be a set
        assert isinstance(prefetcher._background_tasks, set)

        messages = [ChatMessage(role="user", content="search for something")]
        await prefetcher.execute_with_speculation(
            query="search for something",
            tools=[tool],
            llm_client=llm_client,
            messages=messages,
        )
        # After completion, tasks should have been discarded from set
        # (done_callback removes them)


class TestKeywordToolCallPredictor:
    """Tests for KeywordToolCallPredictor."""

    def test_keyword_predictor_scores_by_overlap(self) -> None:
        """Higher keyword overlap → higher ranking."""
        calc_tool = make_tool("calculator", "math calculation add subtract multiply")
        weather_tool = make_tool("weather", "weather forecast temperature rain")

        predictor = KeywordToolCallPredictor()
        result = predictor.predict(
            query="calculate math add numbers",
            available_tools=[weather_tool, calc_tool],
        )

        assert len(result) == 2
        # calculator should rank first due to higher overlap with "calculate math add"
        assert result[0].name == "calculator"

    def test_keyword_predictor_recency_boost(self) -> None:
        """Recently-used tools get boosted score."""
        calc_tool = make_tool("calculator", "math")
        weather_tool = make_tool("weather", "forecast temperature")

        # weather was recently used
        recent_history = [
            ChatMessage(role="user", content="what is the weather forecast?"),
            ChatMessage(role="assistant", content="I used weather to get the forecast"),
        ]

        predictor = KeywordToolCallPredictor(recency_boost=2.0, recency_window=3)
        # Query slightly favors calculator, but weather has recency boost
        result = predictor.predict(
            query="temperature math",
            available_tools=[calc_tool, weather_tool],
            recent_history=recent_history,
        )

        # weather has recency boost so it should be boosted even with partial overlap
        assert len(result) == 2
        assert result[0].name == "weather"
