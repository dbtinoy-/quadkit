"""Tests for LLM selector types."""

import pytest

from quadkit.ai.llm.selection.core import SelectionCriteria


class TestSelectionCriteria:
    """Tests for SelectionCriteria enum."""

    def test_selection_criteria_values(self) -> None:
        """Test SelectionCriteria enum values."""
        assert SelectionCriteria.TOKEN_COUNT.value == "token_count"
        assert SelectionCriteria.COST.value == "cost"
        assert SelectionCriteria.LATENCY.value == "latency"
        assert SelectionCriteria.QUALITY.value == "quality"
        assert SelectionCriteria.CUSTOM.value == "custom"

    def test_selection_criteria_members(self) -> None:
        """Test SelectionCriteria has expected members."""
        members = list(SelectionCriteria)
        assert len(members) == 5
