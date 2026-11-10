"""Tests for KeywordToolCallPredictor."""

from __future__ import annotations

import pytest

from quadkit.ai.agents.speculation.predictor import KeywordToolCallPredictor
from quadkit.ai.agents.tools.decorator import tool
from quadkit.contracts.ai.llm import ChatMessage


class TestKeywordToolCallPredictor:
    """Tests for KeywordToolCallPredictor."""

    def test_predict_returns_empty_for_no_tools(self) -> None:
        predictor = KeywordToolCallPredictor()
        result = predictor.predict("hello", [])
        assert result == []

    def test_predict_ranks_by_keyword_overlap(self) -> None:
        predictor = KeywordToolCallPredictor()

        @tool
        async def search(query: str) -> str:
            """Search for information online."""
            return ""

        @tool
        async def calculate(expr: str) -> str:
            """Perform mathematical calculations."""
            return ""

        tools = [search, calculate]
        result = predictor.predict("search for weather", tools)
        assert result[0].name == "search"

    def test_predict_boost_recency(self) -> None:
        predictor = KeywordToolCallPredictor(recency_boost=2.0, recency_window=3)

        @tool
        async def search(query: str) -> str:
            """Search tool."""
            return ""

        @tool
        async def other(query: str) -> str:
            """Other tool."""
            return ""

        recent_history = [
            ChatMessage(role="user", content="call the search"),
        ]

        result = predictor.predict(
            "do something",
            [search, other],
            recent_history=recent_history,
        )
        assert result[0].name == "search"

    def test_predict_no_boost_without_history(self) -> None:
        predictor = KeywordToolCallPredictor(recency_boost=2.0)

        @tool
        async def tool_a(x: str) -> str:
            """Alpha tool."""
            return ""

        @tool
        async def tool_b(x: str) -> str:
            """Beta tool."""
            return ""

        result = predictor.predict("alpha", [tool_a, tool_b])
        assert result[0].name == "tool_a"

    def test_tokenize_removes_punctuation(self) -> None:
        predictor = KeywordToolCallPredictor()
        tokens = predictor._tokenize("hello, world!")
        assert tokens == {"hello", "world"}

    def test_tokenize_returns_empty_set_for_empty(self) -> None:
        predictor = KeywordToolCallPredictor()
        assert predictor._tokenize("") == set()

    def test_score_zero_for_tool_with_no_description(self) -> None:
        predictor = KeywordToolCallPredictor()

        class MinimalTool:
            @property
            def name(self) -> str:
                return ""
            @property
            def description(self) -> str:
                return ""

        result = predictor.predict("hello", [MinimalTool()])
        assert len(result) == 1

    def test_default_constructor(self) -> None:
        predictor = KeywordToolCallPredictor()
        assert predictor._recency_boost == 1.5
        assert predictor._recency_window == 3
