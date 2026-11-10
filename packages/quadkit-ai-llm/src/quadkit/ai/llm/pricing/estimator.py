"""Synchronous cost estimator over preloaded pricing data.

Provides :class:`PricingCostEstimator`, a concrete implementation of
:class:`~quadkit.contracts.ai.llm.CostEstimatorProtocol` that prices
token usage against a snapshot of :class:`ModelPricing` entries.

The snapshot is preloaded at container boot (see ``LLMProvider``); the
estimator itself is fully synchronous so it can be called on the hot
path without blocking the event loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.ai.llm.pricing.types import ModelPricing
from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.ai.llm.pricing.manager import PricingManager

logger = get_logger(__name__)


class PricingCostEstimator:
    """Estimate USD cost of LLM usage from a pricing snapshot.

    Implements ``CostEstimatorProtocol.estimate_cost``.  Model lookup is
    exact (case-insensitive), then a substring match in both directions
    (mirrors ``PricingManager`` fuzzy matching) when enabled.  Unknown
    models price at ``0.0`` — callers must skip cost tracking rather than
    fabricate estimates.

    Attributes:
        pricing: Snapshot of model name to pricing data.
        enable_fuzzy_match: Allow substring model name matching.

    Example:
        >>> estimator = PricingCostEstimator(
        ...     {"gpt-4o": ModelPricing(model="gpt-4o", prompt_per_1m=2.5,
        ...                              completion_per_1m=10.0, provider="openai")}
        ... )
        >>> estimator.estimate_cost("gpt-4o", 1500, prompt_tokens=1000,
        ...                         completion_tokens=500)
        0.0075

    """

    def __init__(
        self,
        pricing: dict[str, ModelPricing],
        *,
        enable_fuzzy_match: bool = True,
    ) -> None:
        """Initialize the estimator.

        Args:
            pricing: Preloaded snapshot of model name to pricing data.
            enable_fuzzy_match: Allow substring model name matching
                (default: True).
        """
        self.pricing = {k.lower(): v for k, v in pricing.items()}
        self.enable_fuzzy_match = enable_fuzzy_match

    async def warm(self, manager: PricingManager) -> None:
        """Reload the pricing snapshot from a manager.

        Aggregates all sources via :meth:`PricingManager.preload`; source
        failures degrade to empty entries, which price at ``0.0``.

        Args:
            manager: Pricing manager to load from.
        """
        merged = await manager.preload()
        self.pricing = {k.lower(): v for k, v in merged.items()}
        logger.info(
            "Cost estimator warmed with %d models",
            len(self.pricing),
        )

    def estimate_cost(
        self,
        model: str,
        total_tokens: int,
        provider: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> float:
        """Estimate cost in USD for the given token usage.

        When *prompt_tokens* and *completion_tokens* are known they are
        priced at the input and output rates.  When both are ``0`` the
        split is unknown and *total_tokens* is priced at the input rate —
        prompt tokens dominate agent turns, so this is the closest
        approximation available.

        Args:
            model: Model identifier (e.g. ``gpt-4o``).
            total_tokens: Total tokens consumed (prompt + completion).
            provider: Provider name (e.g. ``openai``) — currently unused,
                pricing is keyed by model.
            prompt_tokens: Input token count. ``0`` means unknown.
            completion_tokens: Output token count. ``0`` means unknown.

        Returns:
            Estimated cost in USD. ``0.0`` when the model has no pricing.

        Example:
            >>> estimator.estimate_cost("gpt-4o", 1500, prompt_tokens=1000,
            ...                         completion_tokens=500)
            0.0075
        """
        entry = self._lookup(model)
        if entry is None:
            return 0.0

        if prompt_tokens > 0 or completion_tokens > 0:
            prompt_cost = (prompt_tokens / 1_000_000) * entry.prompt_per_1m
            completion_cost = (completion_tokens / 1_000_000) * entry.completion_per_1m
            return prompt_cost + completion_cost

        # Unknown split: price the total at the input rate (prompt tokens
        # dominate agent turns).
        return (total_tokens / 1_000_000) * entry.prompt_per_1m

    def _lookup(self, model: str) -> ModelPricing | None:
        """Resolve pricing for a model name.

        Args:
            model: Model identifier.

        Returns:
            Matching pricing entry or None.
        """
        normalized = model.lower().strip()
        entry = self.pricing.get(normalized)
        if entry is not None:
            return entry

        if not self.enable_fuzzy_match:
            return None

        for known_model, candidate in self.pricing.items():
            if normalized in known_model or known_model in normalized:
                return candidate

        return None


__all__ = ["PricingCostEstimator"]
