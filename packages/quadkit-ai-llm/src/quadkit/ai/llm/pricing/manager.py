"""Pricing manager for LLM models with builder pattern.

This module provides a safe, intuitive API for configuring pricing sources
with validation and factory methods for common use cases.

Example:
    >>> # Simple usage (95% of cases)
    >>> pricing = PricingManager.from_defaults()
    >>> model_pricing = await pricing.get_pricing("gpt-4-turbo")
    >>>
    >>> # Custom sources
    >>> pricing = (
    ...     PricingManager.builder()
    ...     .add_json_source("custom.json")
    ...     .add_api_source("https://api.example.com/pricing")
    ...     .with_cache_ttl(3600)
    ...     .build()
    ... )

"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from quadkit.ai.llm.pricing.builder import PricingManagerBuilder
from quadkit.ai.llm.pricing.sources import (
    AbstractPricingSource,
    APIPricingSource,
    JSONFilePricingSource,
)
from quadkit.ai.llm.pricing.types import ModelPricing
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

__all__ = [
    "PricingCache",
    "PricingManager",
    "PricingManagerBuilder",
]


class PricingCache:
    """Cache for pricing data with TTL.

    Attributes:
        ttl: Time-to-live in seconds.
        cache: In-memory cache storage.

    """

    def __init__(self, ttl: int = 86400):
        """Initialize pricing cache.

        Args:
            ttl: Cache TTL in seconds (default: 24 hours).

        """
        self.ttl = ttl
        self._cache: dict[str, ModelPricing] = {}
        self._lock = asyncio.Lock()

    async def get(self, model: str) -> ModelPricing | None:
        """Get pricing from cache.

        Args:
            model: Model identifier.

        Returns:
            Cached pricing if valid, None otherwise.

        """
        async with self._lock:
            if model not in self._cache:
                return None

            pricing = self._cache[model]
            age = (datetime.now(UTC) - pricing.last_updated).total_seconds()

            if age > self.ttl:
                del self._cache[model]
                return None

            return pricing

    async def set(self, model: str, pricing: ModelPricing) -> None:
        """Set pricing in cache.

        Args:
            model: Model identifier.
            pricing: Pricing data.

        """
        async with self._lock:
            self._cache[model] = pricing

    async def clear(self) -> None:
        """Clear all cached pricing."""
        async with self._lock:
            self._cache.clear()


class PricingManager:
    """Manages pricing data from multiple sources with caching.

    Sources are queried in order until pricing is found. Typical hierarchy:
    1. JSON file (fastest, most reliable)
    2. API endpoints (for updates)
    3. Static fallback (hardcoded)

    Attributes:
        sources: List of pricing sources in priority order.
        cache: Pricing cache instance.
        enable_fuzzy_match: Whether to enable fuzzy model name matching.

    Example:
        >>> # Use defaults
        >>> manager = PricingManager.from_defaults()
        >>>
        >>> # Custom configuration
        >>> manager = (
        ...     PricingManager.builder()
        ...     .add_json_source("pricing.json")
        ...     .add_api_source("https://api.example.com/pricing")
        ...     .with_cache_ttl(3600)
        ...     .enable_fuzzy_matching()
        ...     .build()
        ... )
        >>>
        >>> pricing = await manager.get_pricing("gpt-4-turbo")

    """

    def __init__(
        self,
        sources: Sequence[AbstractPricingSource],
        cache_ttl: int = 86400,
        enable_fuzzy_match: bool = True,
    ):
        """Initialize pricing manager.

        Args:
            sources: List of pricing sources in priority order.
            cache_ttl: Cache TTL in seconds (default: 24 hours).
            enable_fuzzy_match: Enable fuzzy model name matching (default: True).

        """
        if not sources:
            msg = "At least one pricing source is required"
            raise ValueError(msg)

        self.sources = list(sources)
        self.cache = PricingCache(ttl=cache_ttl)
        self.enable_fuzzy_match = enable_fuzzy_match

        logger.info("pricing_manager_initialized", source_count=len(sources))

    async def get_pricing(
        self,
        model: str,
        force_refresh: bool = False,
    ) -> ModelPricing | None:
        """Get pricing for a specific model.

        Queries sources in order:
        1. Cache (if not force_refresh)
        2. Each source in priority order
        3. Fuzzy match if enabled
        4. None if not found

        Args:
            model: Model identifier (e.g., "gpt-4-turbo").
            force_refresh: Bypass cache and fetch fresh data.

        Returns:
            ModelPricing if found, None otherwise.

        """
        model_normalized = model.lower().strip()

        # Check cache first
        if not force_refresh:
            cached = await self.cache.get(model_normalized)
            if cached:
                logger.debug("pricing_cache_hit")
                return cached

        # Query sources in order
        for source in self.sources:
            pricing = await source.get_pricing(model_normalized)
            if pricing:
                logger.debug("pricing_entry_found")
                await self.cache.set(model_normalized, pricing)
                return pricing

        # Try fuzzy matching
        if self.enable_fuzzy_match:
            fuzzy_match = await self._fuzzy_match(model_normalized)
            if fuzzy_match:
                logger.info("pricing_fuzzy_match_applied")
                await self.cache.set(model_normalized, fuzzy_match)
                return fuzzy_match

        # Unknown model: report None (callers skip cost tracking) rather
        # than fabricate a price — mirrors PricingCostEstimator's 0.0 policy.
        logger.warning("pricing_not_found")
        return None

    async def _fuzzy_match(self, model: str) -> ModelPricing | None:
        """Try to fuzzy match model name.

        Args:
            model: Normalized model name.

        Returns:
            Matched pricing or None.

        """
        # Get all pricing from all sources
        for source in self.sources:
            all_pricing = await source.get_all_pricing()

            # Try substring matching
            for known_model, pricing in all_pricing.items():
                if model in known_model or known_model in model:
                    return pricing

        return None

    async def list_models(self, provider: str | None = None) -> list[str]:
        """List all available models.

        Args:
            provider: Filter by provider (optional).

        Returns:
            List of model names.

        """
        all_models = set()

        for source in self.sources:
            all_pricing = await source.get_all_pricing()
            for pricing in all_pricing.values():
                if provider is None or pricing.provider == provider:
                    all_models.add(pricing.model)

        return sorted(all_models)

    async def clear_cache(self) -> None:
        """Clear pricing cache."""
        await self.cache.clear()
        logger.info("Pricing cache cleared")

    async def preload(self) -> dict[str, ModelPricing]:
        """Load all pricing from all sources into one merged map.

        Earlier sources win on duplicate model names, mirroring
        :meth:`get_pricing` priority semantics.  Used to build the
        synchronous snapshot for cost estimators.

        Returns:
            Merged dictionary of model name to pricing.
        """
        merged: dict[str, ModelPricing] = {}
        for source in self.sources:
            all_pricing = await source.get_all_pricing()
            for model_name, pricing in all_pricing.items():
                merged.setdefault(model_name, pricing)
        return merged

    @classmethod
    def from_defaults(cls) -> PricingManager:
        """Create manager with default configuration.

        Uses LiteLLM API for dynamic, up-to-date pricing data.
        No static pricing files - always fetches current data.

        Returns:
            PricingManager with API source.

        Example:
            >>> manager = PricingManager.from_defaults()
            >>> pricing = await manager.get_pricing("gpt-4")

        """
        sources = [
            APIPricingSource(
                "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
            ),
        ]

        return cls(sources=sources, cache_ttl=86400, enable_fuzzy_match=True)

    @classmethod
    def from_json(
        cls,
        file_path: str | Path,
        cache_ttl: int = 86400,
    ) -> PricingManager:
        """Create manager from JSON file only.

        Useful for offline applications or when you want full control
        over pricing data.

        Args:
            file_path: Path to JSON pricing file.
            cache_ttl: Cache TTL in seconds (default: 24 hours).

        Returns:
            PricingManager with JSON source only.

        Example:
            >>> manager = PricingManager.from_json("my_pricing.json")
            >>> pricing = await manager.get_pricing("custom-model")

        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        sources = [JSONFilePricingSource(file_path)]
        return cls(sources=sources, cache_ttl=cache_ttl, enable_fuzzy_match=True)

    @classmethod
    def from_api(cls, endpoint: str, cache_ttl: int = 86400) -> PricingManager:
        """Create manager from API endpoint only.

        Args:
            endpoint: API endpoint URL.
            cache_ttl: Cache TTL in seconds (default: 24 hours).

        Returns:
            PricingManager with API source only.

        Example:
            >>> manager = PricingManager.from_api("https://api.example.com/pricing")
            >>> pricing = await manager.get_pricing("gpt-4")

        """
        sources = [APIPricingSource(endpoint)]
        return cls(sources=sources, cache_ttl=cache_ttl, enable_fuzzy_match=True)

    @classmethod
    def builder(cls) -> PricingManagerBuilder:
        """Create a builder for custom configuration.

        Returns:
            PricingManagerBuilder instance.

        Example:
            >>> manager = (
            ...     PricingManager.builder()
            ...     .add_json_source("custom.json")
            ...     .add_api_source("https://api.example.com")
            ...     .with_cache_ttl(3600)
            ...     .build()
            ... )

        """
        return PricingManagerBuilder()
