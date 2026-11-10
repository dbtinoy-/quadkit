"""Fluent builder for PricingManager.

Provides a validated, chainable API for configuring pricing sources.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from quadkit.ai.llm.pricing.sources import (
    AbstractPricingSource,
    APIPricingSource,
    JSONFilePricingSource,
    StaticPricingSource,
)
from quadkit.ai.llm.pricing.types import ModelPricing

if TYPE_CHECKING:
    from quadkit.ai.llm.pricing.manager import PricingManager

__all__ = [
    "PricingManagerBuilder",
]


class PricingManagerBuilder:
    """Builder for PricingManager with validation.

    Provides a fluent API for configuring pricing sources safely.

    Example:
        >>> manager = (
        ...     PricingManager.builder()
        ...     .add_json_source("pricing.json")
        ...     .add_api_source("https://api.example.com/pricing")
        ...     .add_fallback({"custom-model": ModelPricing(...)})
        ...     .with_cache_ttl(3600)
        ...     .enable_fuzzy_matching()
        ...     .build()
        ... )

    """

    def __init__(self) -> None:
        """Initialize builder."""
        self._sources: list[AbstractPricingSource] = []
        self._cache_ttl: int = 86400
        self._enable_fuzzy_match: bool = True

    def add_json_source(self, file_path: str | Path) -> PricingManagerBuilder:
        """Add JSON file pricing source.

        Args:
            file_path: Path to JSON file.

        Returns:
            Self for chaining.

        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        self._sources.append(JSONFilePricingSource(file_path))
        return self

    def add_api_source(
        self,
        endpoint: str,
        timeout: float = 10.0,
    ) -> PricingManagerBuilder:
        """Add API endpoint pricing source.

        Args:
            endpoint: API endpoint URL.
            timeout: Request timeout in seconds (default: 10).

        Returns:
            Self for chaining.

        """
        self._sources.append(APIPricingSource(endpoint, timeout))
        return self

    def add_fallback(
        self,
        pricing_map: dict[str, ModelPricing],
    ) -> PricingManagerBuilder:
        """Add static fallback pricing.

        Args:
            pricing_map: Dictionary of model to pricing.

        Returns:
            Self for chaining.

        """
        self._sources.append(StaticPricingSource(pricing_map))
        return self

    def add_source(self, source: AbstractPricingSource) -> PricingManagerBuilder:
        """Add custom pricing source.

        Args:
            source: Custom AbstractPricingSource implementation.

        Returns:
            Self for chaining.

        """
        self._sources.append(source)
        return self

    def with_cache_ttl(self, seconds: int) -> PricingManagerBuilder:
        """Set cache TTL.

        Args:
            seconds: Cache TTL in seconds.

        Returns:
            Self for chaining.

        Raises:
            ValueError: If seconds is negative.

        """
        if seconds < 0:
            msg = "cache TTL must be non-negative"
            raise ValueError(msg)

        self._cache_ttl = seconds
        return self

    def enable_fuzzy_matching(self, enabled: bool = True) -> PricingManagerBuilder:
        """Enable or disable fuzzy model name matching.

        Args:
            enabled: Whether to enable fuzzy matching (default: True).

        Returns:
            Self for chaining.

        """
        self._enable_fuzzy_match = enabled
        return self

    def build(self) -> PricingManager:
        """Build PricingManager instance.

        Returns:
            Configured PricingManager.

        Raises:
            ValueError: If no sources were added.

        """
        if not self._sources:
            raise ValueError(
                "At least one pricing source must be added. "
                "Use add_json_source(), add_api_source(), or add_fallback()",
            )

        # Imported lazily to avoid a circular import with pricing.manager.
        from quadkit.ai.llm.pricing.manager import PricingManager

        return PricingManager(
            sources=self._sources,
            cache_ttl=self._cache_ttl,
            enable_fuzzy_match=self._enable_fuzzy_match,
        )
