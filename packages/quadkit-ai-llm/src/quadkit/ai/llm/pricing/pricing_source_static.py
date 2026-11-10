"""Static in-memory pricing source for LLM models.

Hardcoded pricing data as a fallback when other sources are unavailable.
"""

from __future__ import annotations

from quadkit.ai.llm.pricing.sources import AbstractPricingSource
from quadkit.ai.llm.pricing.types import ModelPricing

__all__ = [
    "StaticPricingSource",
]


class StaticPricingSource(AbstractPricingSource):
    """Pricing source from static dictionary.

    Hardcoded pricing data as a fallback when other sources are unavailable.
    Useful for custom internal models or as ultimate fallback.

    Attributes:
        pricing_map: Dictionary of model name to pricing.

    Example:
        >>> source = StaticPricingSource({
        ...     "my-model": ModelPricing(
        ...         model="my-model",
        ...         prompt_per_1m=5.0,
        ...         completion_per_1m=10.0,
        ...         provider="custom"
        ...     )
        ... })

    """

    def __init__(self, pricing_map: dict[str, ModelPricing]):
        """Initialize static pricing source.

        Args:
            pricing_map: Dictionary mapping model names to pricing.

        """
        # Normalize keys to lowercase
        self.pricing_map = {k.lower(): v for k, v in pricing_map.items()}

    async def get_pricing(self, model: str) -> ModelPricing | None:
        """Get pricing for a specific model.

        Args:
            model: Model identifier.

        Returns:
            ModelPricing if found, None otherwise.

        """
        return self.pricing_map.get(model.lower())

    async def get_all_pricing(self) -> dict[str, ModelPricing]:
        """Get all pricing data.

        Returns:
            All static pricing data.

        """
        return self.pricing_map.copy()

    @property
    def source_name(self) -> str:
        """Get source name."""
        return f"Static ({len(self.pricing_map)} models)"
