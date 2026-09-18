"""Tests for search types."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from quadkit.contracts.search.types import (
    DocumentData,
    IndexSettings,
    SearchableSpec,
    SearchFilters,
    SearchIndexResult,
)


class TestSearchIndexResult:
    """Tests for SearchIndexResult."""

    def test_creation(self) -> None:
        """Test creating a SearchIndexResult."""
        result = SearchIndexResult(id="doc-1", score=0.95)
        assert result.id == "doc-1"
        assert result.score == 0.95

    def test_default_values(self) -> None:
        """Test SearchIndexResult has correct defaults."""
        result = SearchIndexResult(id="doc-1", score=0.5)
        assert result.data == {}
        assert result.highlights is None

    def test_custom_values(self) -> None:
        """Test SearchIndexResult with custom values."""
        result = SearchIndexResult(
            id="doc-2",
            score=0.85,
            data={"title": "Test", "content": "Hello world"},
            highlights={"content": "Hello <em>world</em>"},
        )
        assert result.data == {"title": "Test", "content": "Hello world"}
        assert result.highlights == {"content": "Hello <em>world</em>"}

    def test_score_range(self) -> None:
        """Test various score values."""
        assert SearchIndexResult(id="doc", score=0.0).score == 0.0
        assert SearchIndexResult(id="doc", score=1.0).score == 1.0
        assert SearchIndexResult(id="doc", score=0.5).score == 0.5

    def test_frozen_dataclass(self) -> None:
        """Test SearchIndexResult is frozen (immutable)."""
        result = SearchIndexResult(id="doc-1", score=0.9)
        with pytest.raises(FrozenInstanceError):
            result.id = "new-id"

    def test_slots(self) -> None:
        """Test SearchIndexResult uses slots."""
        result = SearchIndexResult(id="doc-1", score=0.9)
        # Should have __slots__
        assert hasattr(SearchIndexResult, "__slots__")


class TestTypeAliases:
    """Tests for search type aliases."""

    def test_document_data_is_dict(self) -> None:
        """Test DocumentData is a dict type alias."""
        data: DocumentData = {"title": "Test", "count": 42}
        assert isinstance(data, dict)

    def test_index_settings_is_dict(self) -> None:
        """Test IndexSettings is a dict type alias."""
        settings: IndexSettings = {"number_of_shards": 3}
        assert isinstance(settings, dict)

    def test_search_filters_is_dict(self) -> None:
        """Test SearchFilters is a dict type alias."""
        filters: SearchFilters = {"status": "active"}
        assert isinstance(filters, dict)

    def test_type_aliases_are_interchangeable(self) -> None:
        """Test type aliases can be used interchangeably."""
        # All are dict[str, Any]
        doc: DocumentData = {"key": "value"}
        settings: IndexSettings = doc  # type: ignore[assignment]
        filters: SearchFilters = settings  # type: ignore[assignment]
        assert isinstance(filters, dict)


class TestSearchIndexResultIntegration:
    """Integration tests for SearchIndexResult."""

    def test_can_build_search_results(self) -> None:
        """Test building a list of search results."""
        results = [
            SearchIndexResult(id="doc-1", score=0.9, data={"title": "First"}),
            SearchIndexResult(id="doc-2", score=0.7, data={"title": "Second"}),
            SearchIndexResult(id="doc-3", score=0.5, data={"title": "Third"}),
        ]
        assert len(results) == 3
        assert results[0].score > results[1].score > results[2].score

    def test_can_filter_by_threshold(self) -> None:
        """Test filtering results by score threshold."""
        results = [
            SearchIndexResult(id="doc-1", score=0.9),
            SearchIndexResult(id="doc-2", score=0.6),
            SearchIndexResult(id="doc-3", score=0.4),
        ]
        relevant = [r for r in results if r.score >= 0.7]
        assert len(relevant) == 1
        assert relevant[0].id == "doc-1"

    def test_can_convert_to_dict(self) -> None:
        """Test SearchIndexResult can be converted to dict."""
        from dataclasses import asdict

        result = SearchIndexResult(
            id="doc-1",
            score=0.85,
            data={"key": "value"},
            highlights={"body": "matched"},
        )
        result_dict = asdict(result)
        assert result_dict["id"] == "doc-1"
        assert result_dict["score"] == 0.85
        assert result_dict["highlights"] == {"body": "matched"}


class TestSearchableSpec:
    """Tests for SearchableSpec."""

    def test_defaults(self) -> None:
        spec = SearchableSpec()
        assert spec.index_name is None
        assert spec.fields == ()
        assert spec.result_limit == 50

    def test_configured(self) -> None:
        spec = SearchableSpec(index_name="posts", fields=("title",), result_limit=10)
        assert spec.index_name == "posts"
        assert spec.fields == ("title",)
        assert spec.result_limit == 10

    def test_frozen_dataclass(self) -> None:
        from dataclasses import FrozenInstanceError

        spec = SearchableSpec()
        with pytest.raises(FrozenInstanceError):
            spec.index_name = "mutated"
