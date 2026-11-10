"""KeywordToolCallPredictor — keyword-based tool call prediction."""

from __future__ import annotations

import re

from quadkit.contracts import (
    ToolProtocol,
)
from quadkit.contracts.ai.llm import ChatMessage
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


class KeywordToolCallPredictor:
    """Keyword-based tool call prediction heuristic.

    Implements ToolCallPredictorProtocol. Scores each tool by keyword
    overlap between the query and the tool's name + description.

    Heuristic algorithm:
    1. Tokenize query into lowercase words.
    2. For each tool, tokenize name + description into keywords.
    3. Score = |query_words ∩ tool_words| / |tool_words|
    4. Boost score by 1.5x if the tool was called in the last recency_window turns.
    5. Return tools sorted by score descending.
    """

    def __init__(self, recency_boost: float = 1.5, recency_window: int = 3) -> None:
        """Initialize the predictor.

        Args:
            recency_boost: Multiplier applied to recently-used tools.
            recency_window: Number of recent turns to consider for recency boost.
        """
        self._recency_boost = recency_boost
        self._recency_window = recency_window

    def _tokenize(self, text: str) -> set[str]:
        """Split text on whitespace and punctuation, return lowercase tokens."""
        return set(re.split(r"[\s\W]+", text.lower())) - {""}

    def predict(
        self,
        query: str,
        available_tools: list[ToolProtocol],
        recent_history: list[ChatMessage] | None = None,
    ) -> list[ToolProtocol]:
        """Return tools ranked by likelihood of being called.

        Args:
            query: The current user query.
            available_tools: All tools registered in the agent.
            recent_history: Recent conversation turns for context.

        Returns:
            Tools sorted by predicted likelihood, most likely first.
        """
        query_words = self._tokenize(query)

        # Find recently-used tool names from history
        recently_used: set[str] = set()
        if recent_history:
            for msg in recent_history[-self._recency_window :]:
                content = getattr(msg, "content", "") or ""
                for tool in available_tools:
                    tool_name = getattr(tool, "name", "")
                    if tool_name and tool_name.lower() in content.lower():
                        recently_used.add(tool_name)

        def score(tool: ToolProtocol) -> float:
            tool_name = getattr(tool, "name", "") or ""
            tool_desc = getattr(tool, "description", "") or ""
            tool_words = self._tokenize(f"{tool_name} {tool_desc}")
            if not tool_words:
                return 0.0
            overlap = len(query_words & tool_words)
            s = overlap / len(tool_words)
            if getattr(tool, "name", "") in recently_used:
                s *= self._recency_boost
            return s

        return sorted(available_tools, key=score, reverse=True)
