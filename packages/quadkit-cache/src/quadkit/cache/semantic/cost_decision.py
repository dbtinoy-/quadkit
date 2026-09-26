"""Cost-aware semantic cache hit decision logic.

Weighs the risk of serving a slightly wrong cached answer against the
cost of a fresh API call. Higher API costs make the decision function
more willing to accept lower-similarity cache hits.
"""

from __future__ import annotations


class CostAwareCacheDecision:
    """Cost-aware cache hit/miss decision function.

    Implements a simple heuristic that balances accuracy (similarity score)
    against the economic cost of invoking the API. When API costs are high,
    lower similarity thresholds become acceptable to save money. When costs
    are low, higher similarity thresholds are enforced.

    The decision is based on:
    - similarity: Cosine similarity [0, 1]. Closeness to 1 = high accuracy.
    - api_cost_per_1k_tokens: USD cost per 1000 tokens.
    - expected_tokens: Expected token count for a fresh API call.
    """

    def __init__(self, accuracy_weight: float = 0.7) -> None:
        """Initialize the cost-aware decision function.

        Args:
            accuracy_weight: Weight (0 to 1) assigned to accuracy mismatch
                penalty. Higher values prioritize accuracy over cost. Defaults to 0.7.
        """
        if not 0 <= accuracy_weight <= 1:
            raise ValueError(
                f"accuracy_weight must be in [0, 1], got {accuracy_weight}"
            )
        self._accuracy_weight = accuracy_weight

    def should_use_cache(
        self,
        similarity: float,
        api_cost_per_1k_tokens: float,
        expected_tokens: int,
    ) -> bool:
        """Decide whether to use a cached response.

        Decision logic:
        - Compute mismatch_penalty = (1 - similarity) * accuracy_weight
        - Compute cost_incentive = min(estimated_cost * (1 - accuracy_weight), 1.0)
        - Return mismatch_penalty < cost_incentive

        When accuracy_weight=0.7 and similarity=0.95:
        - mismatch_penalty = 0.05 * 0.7 = 0.035
        - If estimated_cost >= 0.035/0.3 = 0.117 USD, cache is used.
        - For gpt-4 (~$0.03 per 1k tokens), expected_tokens=100 → ~$0.003,
          cache is skipped (cost too low to accept small mismatch).
        - For gpt-4 (~$0.03 per 1k tokens), expected_tokens=5000 → ~$0.15,
          cache is used (cost high enough to accept 5% mismatch).

        Args:
            similarity: Cosine similarity in [0, 1].
            api_cost_per_1k_tokens: Estimated USD cost per 1000 tokens.
            expected_tokens: Expected token count for fresh call.

        Returns:
            True if the cached response should be used, False if a fresh
            API call should be made.
        """
        if not 0 <= similarity <= 1:
            raise ValueError(f"similarity must be in [0, 1], got {similarity}")
        if api_cost_per_1k_tokens < 0:
            raise ValueError(
                f"api_cost_per_1k_tokens must be non-negative, got "
                f"{api_cost_per_1k_tokens}"
            )
        if expected_tokens < 0:
            raise ValueError(
                f"expected_tokens must be non-negative, got {expected_tokens}"
            )

        # If cost is zero or tokens is zero, never use cache (free to call API)
        if api_cost_per_1k_tokens == 0 or expected_tokens == 0:
            return False

        estimated_cost = (expected_tokens / 1000) * api_cost_per_1k_tokens
        mismatch_penalty = (1 - similarity) * self._accuracy_weight
        cost_incentive = min(estimated_cost * (1 - self._accuracy_weight), 1.0)

        return mismatch_penalty < cost_incentive
