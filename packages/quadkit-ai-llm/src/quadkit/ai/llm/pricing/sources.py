"""Pricing data sources for LLM models.

This module provides abstraction for different pricing data sources with a clear
hierarchy: JSON files → API endpoints → Static fallback.

Example:
    >>> from quadkit.ai.llm.pricing_sources import JSONFilePricingSource
    >>>
    >>> source = JSONFilePricingSource(Path("pricing.json"))
    >>> pricing = await source.get_pricing("gpt-4-turbo")

"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from pathlib import Path
from typing import Any

from aiohttp import ClientError as AiohttpClientError

from quadkit.ai.llm.http.client import ResilientHTTPClient
from quadkit.ai.llm.pricing.types import ModelPricing
from quadkit.contracts.exceptions.base import QuadkitError
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import loads

logger = get_logger(__name__)

# Every pricing source is best-effort: an unreachable or failing endpoint must
# never propagate (a pricing outage must not abort application startup), so
# sources degrade to empty pricing.  ``HttpStatusError`` from
# ``ResilientHTTPClient.raise_for_status`` and the rich aiohttp connection
# errors are NOT ``OSError`` subclasses and must be caught explicitly.
_PRICING_FETCH_ERRORS: tuple[type[BaseException], ...] = (
    OSError,
    ValueError,
    TypeError,
    QuadkitError,
    AiohttpClientError,
)


class AbstractPricingSource(ABC):
    """Abstract base class for pricing data sources.

    All pricing sources must implement get_pricing() to return ModelPricing
    for a given model name, or None if not found.

    """

    @abstractmethod
    async def get_pricing(self, model: str) -> ModelPricing | None:
        """Get pricing for a specific model.

        Args:
            model: Model identifier (e.g., "gpt-4-turbo").

        Returns:
            ModelPricing if found, None otherwise.

        """

    @abstractmethod
    async def get_all_pricing(self) -> dict[str, ModelPricing]:
        """Get all available pricing data.

        Returns:
            Dictionary mapping model names to pricing.

        """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Get the name of this pricing source.

        Returns:
            Human-readable source name.

        """


class JSONFilePricingSource(AbstractPricingSource):
    """Pricing source from local JSON file.

    This is the fastest and most reliable source as it doesn't require
    network calls and works offline.

    Attributes:
        file_path: Path to JSON pricing file.
        cache: In-memory cache of loaded pricing.

    Example:
        >>> source = JSONFilePricingSource(Path("custom_pricing.json"))
        >>> pricing = await source.get_pricing("gpt-4-turbo")

    """

    def __init__(self, file_path: Path):
        """Initialize JSON file pricing source.

        Args:
            file_path: Path to JSON file containing pricing data.

        """
        self.file_path = file_path
        self._cache: dict[str, ModelPricing] | None = None

    async def _load_cache(self) -> dict[str, ModelPricing]:
        """Load pricing data from JSON file.

        Returns:
            Dictionary of model name to pricing.

        """
        if self._cache is not None:
            return self._cache

        exists = await asyncio.to_thread(self.file_path.exists)
        if not exists:
            logger.warning("json_pricing_file_not_found")
            return {}

        try:

            def _read_json() -> Any:
                with open(self.file_path, "rb") as f:
                    return f.read()

            content = await asyncio.to_thread(_read_json)
            data = loads(content)

            pricing = {}

            # Load regular models
            for model_name, model_data in data.get("models", {}).items():
                pricing[model_name.lower()] = ModelPricing(
                    model=model_name,
                    prompt_per_1m=model_data.get("prompt_per_1m", 1.0),
                    completion_per_1m=model_data.get("completion_per_1m", 2.0),
                    provider=model_data.get("provider", "unknown"),
                    source="json",
                )
        except _PRICING_FETCH_ERRORS as e:
            logger.warning(
                "Failed to load pricing from JSON",
                error_type=type(e).__name__,
            )
            return {}
        else:
            self._cache = pricing
            logger.info("json_pricing_loaded", model_count=len(pricing))
            return pricing

    async def get_pricing(self, model: str) -> ModelPricing | None:
        """Get pricing for a specific model.

        Args:
            model: Model identifier.

        Returns:
            ModelPricing if found, None otherwise.

        """
        cache = await self._load_cache()
        return cache.get(model.lower())

    async def get_all_pricing(self) -> dict[str, ModelPricing]:
        """Get all pricing data.

        Returns:
            All pricing data from JSON file.

        """
        return await self._load_cache()

    @property
    def source_name(self) -> str:
        """Get source name."""
        return "JSON File"

    def invalidate_cache(self) -> None:
        """Clear cached pricing data to force reload."""
        self._cache = None


class APIPricingSource(AbstractPricingSource):
    """Pricing source from HTTP API endpoint.

    Fetches pricing data from a remote API. Useful for getting the latest
    pricing updates, but requires network connectivity.

    Attributes:
        endpoint: API endpoint URL.
        timeout: Request timeout in seconds.

    Example:
        >>> source = APIPricingSource(
        ...     "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
        ... )
        >>> pricing = await source.get_pricing("gpt-4")

    """

    def __init__(self, endpoint: str, timeout: float = 10.0):
        """Initialize API pricing source.

        Args:
            endpoint: URL to fetch pricing from.
            timeout: Request timeout in seconds (default: 10).

        """
        self.endpoint = endpoint
        self.timeout = timeout
        self._cache: dict[str, ModelPricing] | None = None

    async def _fetch_pricing(self) -> dict[str, ModelPricing]:
        """Fetch pricing from API endpoint.

        Returns:
            Dictionary of model pricing.

        """
        if self._cache is not None:
            return self._cache

        try:
            async with ResilientHTTPClient(
                timeout=self.timeout,
                name="pricing-api",
            ) as client:
                response = await client.get(self.endpoint)
                response.raise_for_status()

                data: Any = response.json
                if asyncio.iscoroutine(data):
                    data = await data
                pricing = {}

                for model_name, model_data in (data or {}).items():
                    # Extract pricing (LiteLLM format stores per-token, convert to per-1M)
                    input_cost = model_data.get("input_cost_per_token", 0) * 1_000_000
                    output_cost = model_data.get("output_cost_per_token", 0) * 1_000_000

                    if input_cost > 0:
                        # Infer provider from model name
                        provider = self._infer_provider(model_name)

                        pricing[model_name.lower()] = ModelPricing(
                            model=model_name,
                            prompt_per_1m=input_cost,
                            completion_per_1m=output_cost,
                            provider=provider,
                            source="api",
                        )

                self._cache = pricing
                logger.info("pricing_api_loaded", model_count=len(pricing))
                return pricing

        except _PRICING_FETCH_ERRORS as e:
            logger.warning(
                "Failed to fetch pricing",
                error_type=type(e).__name__,
            )
            return {}

    def _infer_provider(self, model_name: str) -> str:
        """Infer provider from model name.

        Args:
            model_name: Model identifier.

        Returns:
            Provider name.

        """
        model_lower = model_name.lower()
        if "gpt" in model_lower or "openai" in model_lower:
            return "openai"
        if "claude" in model_lower or "anthropic" in model_lower:
            return "anthropic"
        if "gemini" in model_lower:
            return "google"
        if "mistral" in model_lower or "mixtral" in model_lower:
            return "mistral"
        if "command" in model_lower or "cohere" in model_lower:
            return "cohere"
        if "llama" in model_lower and "groq" not in model_lower:
            return "meta"
        return "unknown"

    async def get_pricing(self, model: str) -> ModelPricing | None:
        """Get pricing for a specific model.

        Args:
            model: Model identifier.

        Returns:
            ModelPricing if found, None otherwise.

        """
        cache = await self._fetch_pricing()
        return cache.get(model.lower())

    async def get_all_pricing(self) -> dict[str, ModelPricing]:
        """Get all pricing data.

        Returns:
            All pricing data from API.

        """
        return await self._fetch_pricing()

    @property
    def source_name(self) -> str:
        """Get source name."""
        return "API source"

    def invalidate_cache(self) -> None:
        """Clear cached pricing data to force refresh."""
        self._cache = None


class OpenRouterPricingSource(AbstractPricingSource):
    """Pricing source from the OpenRouter models API.

    Fetches ``https://openrouter.ai/api/v1/models`` (no API key required)
    and maps each model's per-token USD prices to :class:`ModelPricing`.
    OpenRouter prices reflect what you actually pay for OpenAI, Anthropic,
    Google, Meta, Cohere, DeepSeek, xAI, and Qwen models and are updated
    continuously by OpenRouter.

    Each model is indexed under its full slug (e.g. ``openai/gpt-4o``) and,
    when unambiguous, under its bare name (e.g. ``gpt-4o``) so callers can
    look up prices by either form.

    Attributes:
        endpoint: Models API endpoint URL.
        timeout: Request timeout in seconds.
        cache: In-memory cache of fetched pricing.

    Example:
        >>> source = OpenRouterPricingSource()
        >>> pricing = await source.get_pricing("gpt-4o")

    """

    def __init__(
        self,
        endpoint: str | None = None,
        timeout: float = 10.0,
    ):
        """Initialize OpenRouter pricing source.

        Args:
            endpoint: Models API URL. Defaults to
                ``https://openrouter.ai/api/v1/models``.
            timeout: Request timeout in seconds (default: 10).
        """
        self.endpoint = endpoint or "https://openrouter.ai/api/v1/models"
        self.timeout = timeout
        self._cache: dict[str, ModelPricing] | None = None

    async def _fetch_pricing(self) -> dict[str, ModelPricing]:
        """Fetch pricing from the OpenRouter models API.

        Returns:
            Dictionary of model name to pricing.

        """
        if self._cache is not None:
            return self._cache

        try:
            async with ResilientHTTPClient(
                timeout=self.timeout,
                name="openrouter-pricing",
            ) as client:
                response = await client.get(self.endpoint)
                response.raise_for_status()

                data: Any = response.json
                if asyncio.iscoroutine(data):
                    data = await data

                pricing: dict[str, ModelPricing] = {}
                for model in (data or {}).get("data", []):
                    model_id = str(model.get("id") or "").strip().lower()
                    if not model_id:
                        continue

                    prices = model.get("pricing") or {}
                    prompt_per_token = self._to_float(prices.get("prompt"))
                    completion_per_token = self._to_float(prices.get("completion"))
                    if prompt_per_token is None and completion_per_token is None:
                        continue

                    provider = model_id.split("/", 1)[0] or "unknown"
                    entry = ModelPricing(
                        model=model_id,
                        prompt_per_1m=(prompt_per_token or 0.0) * 1_000_000,
                        completion_per_1m=(completion_per_token or 0.0) * 1_000_000,
                        provider=provider,
                        source="api:openrouter",
                    )
                    pricing[model_id] = entry

                    # Bare-name alias when unambiguous (e.g. "gpt-4o").
                    parts = model_id.split("/", 1)
                    if len(parts) == 2 and parts[1] not in pricing:
                        pricing[parts[1]] = entry

                self._cache = pricing
                logger.info("pricing_api_loaded", model_count=len(pricing))
                return pricing

        except _PRICING_FETCH_ERRORS as e:
            logger.warning(
                "pricing_api_fetch_failed",
                error_type=type(e).__name__,
            )
            return {}

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Convert a pricing value to float, tolerating None/empty strings.

        Args:
            value: Raw pricing value (string, number, or None).

        Returns:
            Float value, or ``None`` when absent or unparseable.
        """
        if value is None:
            return None
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    async def get_pricing(self, model: str) -> ModelPricing | None:
        """Get pricing for a specific model.

        Args:
            model: Model identifier (full slug or bare name).

        Returns:
            ModelPricing if found, None otherwise.
        """
        cache = await self._fetch_pricing()
        return cache.get(model.lower())

    async def get_all_pricing(self) -> dict[str, ModelPricing]:
        """Get all pricing data.

        Returns:
            All pricing data from the OpenRouter API.
        """
        return await self._fetch_pricing()

    @property
    def source_name(self) -> str:
        """Get source name."""
        return "OpenRouter API"

    def invalidate_cache(self) -> None:
        """Clear cached pricing data to force refresh."""
        self._cache = None


def __getattr__(name: str) -> Any:
    """Get ``StaticPricingSource``, lazily imported from its sibling module."""
    if name == "StaticPricingSource":
        from quadkit.ai.llm.pricing.pricing_source_static import StaticPricingSource

        return StaticPricingSource
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
