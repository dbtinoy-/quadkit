"""Tests for memory contracts."""

import pytest
from datetime import datetime, timezone

from quadkit.contracts.ai.memory import (
    ConsolidationResult,
    EpisodicMemoryProtocol,
    MemoryConsolidatorProtocol,
    MemoryEntry,
    MemoryQuery,
    MemorySearchResult,
    MemoryStoreProtocol,
    SemanticMemoryProtocol,
    WorkingMemoryProtocol,
)


class TestMemoryDataclasses:
    """Test memory dataclass definitions."""

    def test_memory_entry_frozen(self) -> None:
        """MemoryEntry should be frozen (immutable)."""
        entry = MemoryEntry(
            id="1",
            owner_id="owner-1",
            content="test",
            role="user",
            timestamp=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            entry.importance = 0.8

    def test_memory_entry_with_defaults(self) -> None:
        """MemoryEntry should have sensible defaults."""
        entry = MemoryEntry(
            id="1",
            owner_id="owner-1",
            content="test",
            role="user",
            timestamp=datetime.now(timezone.utc),
        )
        assert entry.importance == 0.5
        assert entry.metadata == {}
        assert entry.embedding is None

    def test_memory_query_frozen(self) -> None:
        """MemoryQuery should be frozen."""
        query = MemoryQuery(owner_id="owner-1", query="test")
        with pytest.raises(AttributeError):
            query.top_k = 20

    def test_memory_query_defaults(self) -> None:
        """MemoryQuery should have proper defaults."""
        query = MemoryQuery(owner_id="owner-1", query="test")
        assert query.top_k == 10
        assert query.min_relevance == 0.0
        assert query.recency_weight == 0.3
        assert query.importance_weight == 0.3
        assert query.relevance_weight == 0.4

    def test_memory_search_result_frozen(self) -> None:
        """MemorySearchResult should be frozen."""
        entry = MemoryEntry(
            id="1",
            owner_id="owner-1",
            content="test",
            role="user",
            timestamp=datetime.now(timezone.utc),
        )
        result = MemorySearchResult(entry=entry, score=0.95, source="episodic")
        with pytest.raises(AttributeError):
            result.score = 0.5

    def test_consolidation_result_frozen(self) -> None:
        """ConsolidationResult should be frozen."""
        result = ConsolidationResult(
            entries_processed=10,
            entries_consolidated=5,
            entries_pruned=3,
            entities_extracted=2,
            duration_ms=150.0,
        )
        with pytest.raises(AttributeError):
            result.entries_processed = 20


class TestMemoryProtocols:
    """Test that memory protocols are runtime checkable."""

    def test_memory_store_protocol_runtime_checkable(self) -> None:
        """MemoryStoreProtocol should be runtime checkable."""
        assert isinstance(MemoryStoreProtocol, type)

        class MockStore:
            async def store(self, entry):
                pass

            async def retrieve(self, query):
                return []

            async def get_recent(self, n, owner_id):
                return []

            async def delete(self, entry_id, owner_id):
                pass

            async def clear(self, owner_id):
                pass

            async def health_check(self, timeout=5.0):
                pass

        mock = MockStore()
        assert isinstance(mock, MemoryStoreProtocol)

    def test_working_memory_protocol_runtime_checkable(self) -> None:
        """WorkingMemoryProtocol should be runtime checkable."""
        assert isinstance(WorkingMemoryProtocol, type)

        class MockWorking:
            async def assemble(self, query, token_budget, *, owner_id, session_id=None):
                return []

            async def add(self, entry):
                pass

            async def get_context_entries(self):
                return []

            async def flush(self):
                pass

            async def health_check(self, timeout=5.0):
                pass

        mock = MockWorking()
        assert isinstance(mock, WorkingMemoryProtocol)

    def test_episodic_memory_protocol_runtime_checkable(self) -> None:
        """EpisodicMemoryProtocol should be runtime checkable."""
        assert isinstance(EpisodicMemoryProtocol, type)

        class MockEpisodic:
            async def record(self, entry):
                pass

            async def recall(self, query):
                return []

            async def forget(self, entry_id, owner_id):
                pass

            async def health_check(self, timeout=5.0):
                pass

        mock = MockEpisodic()
        assert isinstance(mock, EpisodicMemoryProtocol)

    def test_semantic_memory_protocol_runtime_checkable(self) -> None:
        """SemanticMemoryProtocol should be runtime checkable."""
        assert isinstance(SemanticMemoryProtocol, type)

        class MockSemantic:
            async def store_fact(self, subject, predicate, object_, confidence):
                pass

            async def query_facts(self, subject):
                return []

            async def get_entity_facts(self, entity):
                return []

            async def update_fact(self, fact_id, confidence):
                pass

            async def health_check(self, timeout=5.0):
                pass

        mock = MockSemantic()
        assert isinstance(mock, SemanticMemoryProtocol)

    def test_memory_consolidator_protocol_runtime_checkable(self) -> None:
        """MemoryConsolidatorProtocol should be runtime checkable."""
        assert isinstance(MemoryConsolidatorProtocol, type)

        class MockConsolidator:
            async def consolidate(self, entries):
                return ConsolidationResult(0, 0, 0, 0, 0.0)

            async def health_check(self, timeout=5.0):
                pass

        mock = MockConsolidator()
        assert isinstance(mock, MemoryConsolidatorProtocol)
