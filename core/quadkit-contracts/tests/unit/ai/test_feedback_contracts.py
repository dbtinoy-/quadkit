"""Tests for AI feedback contracts: FeedbackItem and protocol signatures."""

from __future__ import annotations

import inspect

import pytest

from quadkit.contracts.ai.feedback import (
    FeedbackItem,
    FeedbackProtocol,
    FeedbackStoreProtocol,
    FeedbackType,
)


class TestFeedbackItem:
    """Test the FeedbackItem dataclass."""

    def test_owner_id_is_required(self) -> None:
        """Constructing without owner_id raises TypeError."""
        with pytest.raises(TypeError):
            FeedbackItem(feedback_type=FeedbackType.RATING, value=5)  # type: ignore[call-arg]

    def test_owner_id_persisted(self) -> None:
        """owner_id survives construction."""
        item = FeedbackItem(
            feedback_type=FeedbackType.RATING, value=5, owner_id="owner-1"
        )
        assert item.owner_id == "owner-1"

    def test_to_dict_includes_owner_id(self) -> None:
        """to_dict() round-trips owner_id."""
        item = FeedbackItem(
            feedback_type=FeedbackType.TEXT,
            value="good",
            owner_id="owner-1",
            id="fb-1",
        )
        assert item.to_dict()["owner_id"] == "owner-1"

    def test_context_and_metadata_default_empty(self) -> None:
        """context and metadata still default to empty dicts."""
        item = FeedbackItem(
            feedback_type=FeedbackType.RATING, value=5, owner_id="owner-1"
        )
        assert item.context == {}
        assert item.metadata == {}


class TestFeedbackStoreProtocolSignatures:
    """FeedbackStoreProtocol query methods must carry owner_id."""

    def test_find_by_session_has_owner_id(self) -> None:
        """find_by_session takes keyword-only owner_id."""
        parameters = inspect.signature(
            FeedbackStoreProtocol.find_by_session
        ).parameters
        assert "owner_id" in parameters
        assert parameters["owner_id"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_find_by_type_has_owner_id(self) -> None:
        """find_by_type takes keyword-only owner_id."""
        parameters = inspect.signature(FeedbackStoreProtocol.find_by_type).parameters
        assert "owner_id" in parameters
        assert parameters["owner_id"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_aggregate_has_owner_id(self) -> None:
        """aggregate takes keyword-only owner_id."""
        parameters = inspect.signature(FeedbackStoreProtocol.aggregate).parameters
        assert "owner_id" in parameters
        assert parameters["owner_id"].kind is inspect.Parameter.KEYWORD_ONLY


class TestFeedbackProtocolSignatures:
    """FeedbackProtocol methods must carry owner_id."""

    def test_submit_feedback_has_owner_id(self) -> None:
        """submit_feedback takes keyword-only owner_id."""
        parameters = inspect.signature(
            FeedbackProtocol.submit_feedback
        ).parameters
        assert "owner_id" in parameters
        assert parameters["owner_id"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_get_feedback_stats_has_owner_id(self) -> None:
        """get_feedback_stats takes keyword-only owner_id."""
        parameters = inspect.signature(
            FeedbackProtocol.get_feedback_stats
        ).parameters
        assert "owner_id" in parameters
        assert parameters["owner_id"].kind is inspect.Parameter.KEYWORD_ONLY
