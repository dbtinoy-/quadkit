from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.testing.clients.ai.data import AITestData


class AITestClient:
    """Test client that provides ergonomic helpers for exercising AI service boundaries.

    Wraps a :class:`TestEnvironment` (or ``AITestBed``) and provides recording wrappers
    for common AI operations — LLM completions, vector searches, and ML predictions —
    so tests can make assertions about what the system under test invoked.

    Args:
        test_bed: The test environment that owns AI providers and test data.
        max_tokens_per_run: Maximum token budget for all LLM operations in this
            test run.  Set to ``0`` to disable enforcement.  Defaults to 10 000.
    """

    def __init__(
        self,
        test_bed: object,
        *,
        max_tokens_per_run: int = 10_000,
    ) -> None:
        self.test_bed = test_bed
        self._token_budget: int = max_tokens_per_run
        self._tokens_used: int = 0

    # --- Property accessors ---

    @property
    def test_data(self) -> AITestData:
        """Return the :class:`AITestData` instance owned by the test bed."""
        return self.test_bed.test_data  # type: ignore[attr-defined,no-any-return]

    @property
    def tokens_used(self) -> int:
        """Total tokens consumed by LLM completions in this run."""
        return self._tokens_used

    @property
    def token_budget(self) -> int:
        """Configured maximum tokens per run (0 = unlimited)."""
        return self._token_budget

    def reset_token_budget(self) -> None:
        """Reset the token usage counter to zero."""
        self._tokens_used = 0

    # --- Mock response helpers --------------------------------------------

    def _mock_response(self, key: str, default: dict[str, Any]) -> dict[str, Any]:
        """Return the canned response for *key* when configured, else *default*.

        Args:
            key: Mock response key (``llm``, ``vector``, ``ml``).
            default: Structure returned when the key is unset or empty.

        Returns:
            The configured mapping, or *default*.
        """
        response = self.test_data.get_mock_response(key)
        return response if isinstance(response, dict) and response else default

    # --- Token budget helpers ---------------------------------------------

    def _charge_tokens(self, tokens: int) -> None:
        """Charge *tokens* to the budget, raising if the cap is exceeded.

        Args:
            tokens: Number of tokens to charge.

        Raises:
            TokenBudgetExceededError: When budget is configured and would be exceeded.
        """
        if self._token_budget == 0:
            return  # unlimited
        next_total = self._tokens_used + tokens
        if next_total > self._token_budget:
            from quadkit.testing.exceptions import TokenBudgetExceededError

            raise TokenBudgetExceededError(self._tokens_used, self._token_budget)
        self._tokens_used = next_total

    # --- Operation recording wrappers ---

    async def complete_with_llm(
        self,
        prompt: str,
        **kwargs: object,
    ) -> dict:
        """Simulate an LLM completion, enforce the token budget, and record it.

        Token cost is read from the mock response's ``"tokens"`` field if present;
        otherwise estimated as ``ceil(len(prompt.split()) * 1.3)``.

        Args:
            prompt: The prompt text sent to the (mock) LLM.
            **kwargs: Extra fields included in the recorded entry.

        Returns:
            The recorded completion dict.

        Raises:
            TokenBudgetExceededError: When the token budget is set and would be exceeded.
        """
        import math

        mock = self._mock_response("llm", {"response": "", "tokens": 0})
        tokens = int(mock.get("tokens", 0)) or math.ceil(len(prompt.split()) * 1.3)
        self._charge_tokens(tokens)
        record = {"prompt": prompt, "response": mock, **kwargs}
        self.test_data.add_llm_completion(record)
        return record

    async def search_vector_store(
        self,
        query: str,
        **kwargs: object,
    ) -> dict:
        """Simulate a vector store search and record it in :attr:`test_data`.

        Returns the mock response keyed ``"vector"`` if configured, otherwise
        an empty results structure.
        """
        mock = self._mock_response("vector", {"results": []})
        record = {"query": query, "results": mock, **kwargs}
        self.test_data.add_vector_search(record)
        return record

    async def predict_with_ml(
        self,
        input_data: object,
        **kwargs: object,
    ) -> dict:
        """Simulate an ML model prediction and record it in :attr:`test_data`.

        Returns the mock response keyed ``"ml"`` if configured, otherwise a default
        confidence structure.
        """
        mock = self._mock_response("ml", {"output": None, "confidence": 0.0})
        record = {"input": input_data, "output": mock, **kwargs}
        self.test_data.add_ml_prediction(record)
        return record

    # --- Assertion helpers ---

    def assert_llm_completions_count(self, expected: int) -> None:
        """Assert that exactly *expected* LLM completions were recorded."""
        actual = len(self.test_data._llm_completions)
        assert actual == expected, f"Expected {expected} LLM completions, got {actual}"

    def assert_vector_searches_count(self, expected: int) -> None:
        """Assert that exactly *expected* vector searches were recorded."""
        actual = len(self.test_data._vector_searches)
        assert actual == expected, f"Expected {expected} vector searches, got {actual}"

    def assert_ml_predictions_count(self, expected: int) -> None:
        """Assert that exactly *expected* ML predictions were recorded."""
        actual = len(self.test_data._ml_predictions)
        assert actual == expected, f"Expected {expected} ML predictions, got {actual}"
