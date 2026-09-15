"""Memory system contracts: working, episodic, and semantic memory protocols."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from typing_extensions import Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from quadkit.contracts.core import HealthCheckResult


@dataclass(frozen=True)
class MemoryEntry:
    """A single memory entry with temporal and importance metadata.

    Attributes:
        id: Unique identifier for the entry
        owner_id: Owner scope for the entry (user, session, or composite)
        content: The actual content/text of the memory
        role: The role (e.g., "user", "assistant", "system")
        timestamp: When this entry was created
        importance: Score 0-1 indicating importance (default 0.5)
        metadata: Optional metadata dictionary
        embedding: Optional vector embedding of content
    """

    id: str
    owner_id: str
    content: str
    role: str
    timestamp: datetime
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


@dataclass(frozen=True)
class MemoryQuery:
    """Query parameters for searching memory.

    Attributes:
        owner_id: Owner scope the query is restricted to (user, session, or composite)
        query: The search query text
        top_k: Number of results to return (default 10)
        min_relevance: Minimum relevance score threshold (default 0.0)
        recency_weight: Weight for recency in ranking (default 0.3)
        importance_weight: Weight for importance in ranking (default 0.3)
        relevance_weight: Weight for relevance in ranking (default 0.4)
        filters: Optional filters as key-value pairs
        time_range: Optional (start_datetime, end_datetime) range
    """

    owner_id: str
    query: str
    top_k: int = 10
    min_relevance: float = 0.0
    recency_weight: float = 0.3
    importance_weight: float = 0.3
    relevance_weight: float = 0.4
    filters: dict[str, Any] = field(default_factory=dict)
    time_range: tuple[datetime, datetime] | None = None


@dataclass(frozen=True)
class MemorySearchResult:
    """Result of a memory search.

    Attributes:
        entry: The matching memory entry
        score: Relevance score (typically 0-1)
        source: Where this entry came from (e.g., "episodic", "semantic")
    """

    entry: MemoryEntry
    score: float
    source: str


@dataclass(frozen=True)
class ConsolidationResult:
    """Result of memory consolidation operation.

    Attributes:
        entries_processed: Total entries examined
        entries_consolidated: Entries that were compressed/merged
        entries_pruned: Entries that were deleted
        entities_extracted: Number of entities extracted
        duration_ms: Time taken to consolidate in milliseconds
    """

    entries_processed: int
    entries_consolidated: int
    entries_pruned: int
    entities_extracted: int
    duration_ms: float


from quadkit.contracts.ai.exceptions import AIMemoryError

# Memory Errors — AIMemoryError is the canonical base defined in ai/exceptions.py


class ConsolidationError(AIMemoryError):
    """Error raised during memory consolidation."""

    _code = "QK_ERR_MEM_002"


class StorageError(AIMemoryError):
    """Error raised during memory storage operations."""

    _code = "QK_ERR_MEM_003"


@runtime_checkable
class MemoryStoreProtocol(Protocol):
    """Protocol for storing and retrieving memory entries.

    Implementations should provide persistent or semi-persistent storage
    for memory entries, supporting both sequential and search-based access.
    """

    async def store(self, entry: MemoryEntry) -> None:
        """Store a single memory entry.

        Args:
            entry: The memory entry to store
        """
        ...

    async def retrieve(self, query: MemoryQuery) -> list[MemorySearchResult]:
        """Search for memory entries based on a query.

        Args:
            query: Query parameters

        Returns:
            List of matching entries with scores, ordered by relevance
        """
        ...

    async def get_recent(self, n: int, owner_id: str) -> list[MemoryEntry]:
        """Get the N most recent entries owned by ``owner_id``.

        Args:
            n: Number of entries to return
            owner_id: Owner scope; only this owner's entries are returned

        Returns:
            List of recent entries in descending temporal order
        """
        ...

    async def delete(self, entry_id: str, owner_id: str) -> None:
        """Delete an entry by ID, scoped to ``owner_id``.

        Args:
            entry_id: ID of the entry to delete
            owner_id: Owner scope; only this owner's entry may be deleted
        """
        ...

    async def clear(self, owner_id: str) -> None:
        """Clear all entries owned by ``owner_id`` from the store.

        Args:
            owner_id: Owner scope; only this owner's entries are cleared
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight connectivity check."""
        ...


@runtime_checkable
class WorkingMemoryProtocol(Protocol):
    """Protocol for working memory that assembles context for the current request.

    Working memory is the in-context window that gets passed to the LLM,
    assembled from episodic and semantic memory based on token budgets.
    """

    async def assemble(
        self,
        query: str,
        token_budget: int,
        *,
        owner_id: str,
        session_id: str | None = None,
    ) -> list[MemoryEntry]:
        """Assemble context window from available memory tiers.

        Retrieves relevant entries from episodic and semantic memory
        and fits them within the token budget.

        Args:
            query: The current query/prompt
            token_budget: Maximum tokens available for context
            owner_id: Owner scope; only this owner's memory is assembled
            session_id: Optional session scope for session-specific memory

        Returns:
            Ordered list of memory entries for context
        """
        ...

    async def add(self, entry: MemoryEntry) -> None:
        """Add a new entry to the working memory stream.

        Args:
            entry: The entry to add
        """
        ...

    async def get_context_entries(self) -> list[MemoryEntry]:
        """Get current assembled context entries.

        Returns:
            List of entries currently in context window
        """
        ...

    async def flush(self) -> None:
        """Clear the current context assembly."""
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check if the working memory backend is reachable and healthy.

        Args:
            timeout: Maximum seconds to wait for a response.

        Returns:
            Health check result with status and details.
        """
        ...


@runtime_checkable
class EpisodicMemoryProtocol(Protocol):
    """Protocol for episodic memory (conversation history with temporal grounding).

    Episodic memory stores timestamped events and conversations,
    supporting hybrid retrieval based on recency and relevance.
    """

    async def record(self, entry: MemoryEntry) -> None:
        """Record a new episode/conversation turn.

        Args:
            entry: The episode to record
        """
        ...

    async def recall(self, query: MemoryQuery) -> list[MemorySearchResult]:
        """Recall episodes based on relevance and recency.

        Args:
            query: Query parameters with weighting preferences

        Returns:
            Ranked list of matching episodes
        """
        ...

    async def forget(self, entry_id: str, owner_id: str) -> None:
        """Forget/delete a specific episode, scoped to ``owner_id``.

        Args:
            entry_id: ID of the episode to forget
            owner_id: Owner scope; only this owner's episode may be forgotten
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check if the episodic memory backend is reachable and healthy.

        Args:
            timeout: Maximum seconds to wait for a response.

        Returns:
            Health check result with status and details.
        """
        ...


@runtime_checkable
class SemanticMemoryProtocol(Protocol):
    """Protocol for semantic memory (extracted facts and entities).

    Semantic memory stores generalized knowledge in the form of facts,
    entities, and their relationships for long-term retention.
    """

    async def store_fact(
        self, subject: str, predicate: str, object_: str, confidence: float
    ) -> None:
        """Store a fact as a subject-predicate-object triple.

        Args:
            subject: The subject entity
            predicate: The relationship type
            object_: The object entity
            confidence: Confidence score (0-1) for this fact
        """
        ...

    async def query_facts(self, subject: str) -> list[dict[str, Any]]:
        """Query facts by subject.

        Args:
            subject: The subject entity to query

        Returns:
            List of facts with this subject
        """
        ...

    async def get_entity_facts(self, entity: str) -> list[dict[str, Any]]:
        """Get all facts mentioning an entity (subject or object).

        Args:
            entity: The entity name

        Returns:
            List of facts involving this entity
        """
        ...

    async def update_fact(self, fact_id: str, confidence: float) -> None:
        """Update the confidence score of a fact.

        Args:
            fact_id: ID of the fact to update
            confidence: New confidence score (0-1)
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check if the semantic memory backend is reachable and healthy.

        Args:
            timeout: Maximum seconds to wait for a response.

        Returns:
            Health check result with status and details.
        """
        ...


@runtime_checkable
class MemoryConsolidatorProtocol(Protocol):
    """Protocol for consolidating and optimizing memory.

    Consolidation compresses old entries, deduplicates, extracts entities,
    and manages memory size to prevent unbounded growth.
    """

    async def consolidate(self, entries: list[MemoryEntry]) -> ConsolidationResult:
        """Consolidate a batch of memory entries.

        Applies compression, deduplication, entity extraction, and pruning
        strategies to optimize memory storage and retrieval.

        Args:
            entries: Entries to consolidate

        Returns:
            Consolidation result with statistics
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check if the memory consolidator backend is reachable and healthy.

        Args:
            timeout: Maximum seconds to wait for a response.

        Returns:
            Health check result with status and details.
        """
        ...


from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryProtocol(Protocol):
    """Protocol for conversation memory (G-02 parity)."""

    async def add_message(self, message: Any) -> None:
        """Add a message to memory."""
        ...

    async def get_messages(self) -> list[Any]:
        """Get all messages from memory."""
        ...

    async def clear(self) -> None:
        """Clear all messages from memory."""
        ...


class ConversationMemory:
    """Simple conversation memory that keeps all messages.

    Like LangChain's ConversationBufferMemory.
    """

    def __init__(self, max_messages: int | None = None) -> None:
        self._messages: list[Any] = []
        self.max_messages = max_messages

    def add_message(self, message: Any) -> None:
        self._messages.append(message)
        if self.max_messages and len(self._messages) > self.max_messages:
            self._messages.pop(0)

    def get_messages(self) -> list[Any]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    async def aadd_message(self, message: Any) -> None:
        self.add_message(message)

    async def aget_messages(self) -> list[Any]:
        return self.get_messages()

    async def aclear(self) -> None:
        self.clear()


class WindowMemory:
    """Memory that keeps only the last N messages.

    Like LangChain's ConversationBufferWindowMemory.
    """

    def __init__(self, window_size: int = 5) -> None:
        self.window_size = window_size
        self._messages: list[Any] = []

    def add_message(self, message: Any) -> None:
        self._messages.append(message)
        if len(self._messages) > self.window_size:
            self._messages.pop(0)

    def get_messages(self) -> list[Any]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    async def aadd_message(self, message: Any) -> None:
        self.add_message(message)

    async def aget_messages(self) -> list[Any]:
        return self.get_messages()

    async def aclear(self) -> None:
        self.clear()


__all__ = [
    "ConsolidationError",
    "ConsolidationResult",
    "ConversationMemory",
    "EpisodicMemoryProtocol",
    "MemoryConsolidatorProtocol",
    "MemoryEntry",
    "MemoryProtocol",
    "MemoryQuery",
    "MemorySearchResult",
    "MemoryStoreProtocol",
    "SemanticMemoryProtocol",
    "StorageError",
    "WindowMemory",
    "WorkingMemoryProtocol",
]
