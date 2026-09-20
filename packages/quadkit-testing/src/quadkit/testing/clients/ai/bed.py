from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

from quadkit.testing.clients.ai.data import AITestData
from quadkit.testing.fixtures.bed import TestEnvironment

if TYPE_CHECKING:
    from quadkit.testing.clients.ai.client import AITestClient


class AITestBed(TestEnvironment):
    """AI test bed.

    Owns the :class:`AITestData` instance and lazily created mock AI service
    clients (LLM, vector store, ML predictor) so fixtures and tests can share
    a single deterministic mock per bed.
    """

    def __init__(self, name: str = "ai-test", **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.test_data = AITestData()
        self._llm_client: Any = None
        self._vector_store: Any = None
        self._ml_predictor: Any = None

    # ------------------------------------------------------------------
    # Test client
    # ------------------------------------------------------------------

    def create_test_client(self, **kwargs: Any) -> AITestClient:
        """Create an :class:`AITestClient` bound to this bed.

        Args:
            **kwargs: Forwarded to :class:`AITestClient`
                (e.g. ``max_tokens_per_run``).
        """
        from quadkit.testing.clients.ai.client import AITestClient

        return AITestClient(self, **kwargs)

    # ------------------------------------------------------------------
    # Mock AI service clients (lazy, cached per bed)
    # ------------------------------------------------------------------

    @property
    def mock_llm(self) -> Any:
        """The bed's mock LLM client (``complete`` is an AsyncMock)."""
        if self._llm_client is None:
            self._llm_client = MagicMock()
            self._llm_client.complete = AsyncMock(
                return_value=MagicMock(
                    content="Mock response",
                    model="mock-model",
                    usage=MagicMock(total_tokens=10),
                ),
            )
        return self._llm_client

    @property
    def mock_vector_store(self) -> Any:
        """The bed's mock vector store (``add``/``search`` are AsyncMocks)."""
        if self._vector_store is None:
            self._vector_store = MagicMock()
            self._vector_store.add = AsyncMock(return_value=["doc1", "doc2", "doc3"])
            self._vector_store.search = AsyncMock(
                return_value=[
                    MagicMock(document=MagicMock(text="Result 1"), score=0.95),
                    MagicMock(document=MagicMock(text="Result 2"), score=0.89),
                ],
            )
        return self._vector_store

    @property
    def mock_ml_predictor(self) -> Any:
        """The bed's mock ML predictor (``predict`` is an AsyncMock)."""
        if self._ml_predictor is None:
            self._ml_predictor = MagicMock()
            self._ml_predictor.predict = AsyncMock(
                return_value=MagicMock(
                    result="positive",
                    confidence=0.95,
                    model_name="mock-model",
                ),
            )
        return self._ml_predictor

    # ------------------------------------------------------------------
    # Async accessors (for async fixtures)
    # ------------------------------------------------------------------

    async def get_llm_client(self) -> Any:
        """Return the bed's mock LLM client."""
        return self.mock_llm

    async def get_vector_store(self) -> Any:
        """Return the bed's mock vector store."""
        return self.mock_vector_store

    async def get_ml_predictor(self) -> Any:
        """Return the bed's mock ML predictor."""
        return self.mock_ml_predictor
