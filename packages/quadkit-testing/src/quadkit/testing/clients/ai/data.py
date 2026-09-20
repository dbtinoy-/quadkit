from __future__ import annotations


class AITestData:
    """Container for AI-related test data and mock responses.

    Tracks AI operations (LLM completions, vector searches, ML predictions, etc.)
    performed during a test and provides mock response configuration.

    Args:
        prefix: Prefix used when generating unique identifiers for test data.
    """

    def __init__(self, prefix: str = "test") -> None:
        self.prefix = prefix
        self._llm_completions: list[dict] = []
        self._vector_searches: list[dict] = []
        self._ml_predictions: list[dict] = []
        self._pipeline_operations: list[dict] = []
        self._rag_operations: list[dict] = []
        self._agent_operations: list[dict] = []
        self._time_advances: list[float] = []
        self._mock_responses: dict[str, object] = {}

    # --- Recording helpers ---

    def add_llm_completion(self, completion: dict) -> None:
        """Record an LLM completion operation."""
        self._llm_completions.append(completion)

    def add_vector_search(self, search: dict) -> None:
        """Record a vector store search operation."""
        self._vector_searches.append(search)

    def add_ml_prediction(self, prediction: dict) -> None:
        """Record an ML model prediction operation."""
        self._ml_predictions.append(prediction)

    def add_pipeline_operation(self, operation: dict) -> None:
        """Record an AI pipeline stage operation."""
        self._pipeline_operations.append(operation)

    def add_rag_operation(self, operation: dict) -> None:
        """Record a retrieval-augmented generation operation."""
        self._rag_operations.append(operation)

    def add_agent_operation(self, operation: dict) -> None:
        """Record an AI agent action/operation."""
        self._agent_operations.append(operation)

    def record_time_advance(self, seconds: float) -> None:
        """Record a simulated time advance (for time-dependent AI logic)."""
        self._time_advances.append(seconds)

    # --- Mock response configuration ---

    def set_mock_response(self, key: str, response: object) -> None:
        """Register a canned response for a given AI service key."""
        self._mock_responses[key] = response

    def get_mock_response(self, key: str) -> object | None:
        """Retrieve the canned response for *key*, or None if not configured."""
        return self._mock_responses.get(key)

    # --- Reset ---

    def clear(self) -> None:
        """Clear all recorded operations and mock responses."""
        self._llm_completions.clear()
        self._vector_searches.clear()
        self._ml_predictions.clear()
        self._pipeline_operations.clear()
        self._rag_operations.clear()
        self._agent_operations.clear()
        self._time_advances.clear()
        self._mock_responses.clear()
