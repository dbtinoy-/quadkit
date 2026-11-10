"""Pricing source registry — registry-based dispatch of pricing sources."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.ai.llm.config import PricingSourceConfig

from quadkit.ai.llm.pricing.sources import AbstractPricingSource

_LITELLM_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)

PricingSourceBuilder = Callable[["PricingSourceConfig"], AbstractPricingSource]


class PricingSourceRegistry:
    """Registry of pricing-source builders, keyed by source type.

    Each source type maps to a builder that constructs the corresponding
    pricing source from a :class:`~quadkit.ai.llm.config.PricingSourceConfig`.

    Usage::

        registry = PricingSourceRegistry.with_defaults()
        source = registry.create_source(PricingSourceConfig(type="litellm"))
    """

    def __init__(self) -> None:
        """Initialise an empty source registry."""
        self._builders: dict[str, PricingSourceBuilder] = {}

    @classmethod
    def with_defaults(cls) -> PricingSourceRegistry:
        """Return a registry populated with the built-in pricing sources.

        Returns:
            A :class:`PricingSourceRegistry` pre-registered for litellm,
            openrouter, json, and static.
        """
        from quadkit.ai.llm.pricing.pricing_source_static import (
            StaticPricingSource,
        )
        from quadkit.ai.llm.pricing.sources import (
            APIPricingSource,
            JSONFilePricingSource,
            OpenRouterPricingSource,
        )
        from quadkit.ai.llm.pricing.types import ModelPricing

        registry = cls()

        def _litellm(cfg: Any) -> AbstractPricingSource:
            return APIPricingSource(cfg.endpoint or _LITELLM_URL, cfg.timeout)

        def _openrouter(cfg: Any) -> AbstractPricingSource:
            return OpenRouterPricingSource(cfg.endpoint, cfg.timeout)

        def _json(cfg: Any) -> AbstractPricingSource:
            if not cfg.file_path:
                msg = "pricing source of type 'json' requires 'file_path'"
                raise ValueError(msg)
            return JSONFilePricingSource(Path(cfg.file_path))

        def _static(cfg: Any) -> AbstractPricingSource:
            static: dict[str, ModelPricing] = {}
            for model_name, prices in cfg.models.items():
                static[model_name] = ModelPricing(
                    model=model_name,
                    prompt_per_1m=float(prices.get("prompt_per_1m", 0.0)),
                    completion_per_1m=float(prices.get("completion_per_1m", 0.0)),
                    provider=str(prices.get("provider", "custom")),
                    source="static:config",
                )
            return StaticPricingSource(static)

        registry.register("litellm", _litellm)
        registry.register("openrouter", _openrouter)
        registry.register("json", _json)
        registry.register("static", _static)
        return registry

    def register(self, source_type: str, builder: PricingSourceBuilder) -> None:
        """Register a builder under a source type.

        Args:
            source_type: Source type (e.g. ``"litellm"``).
            builder: Callable ``(PricingSourceConfig) -> AbstractPricingSource``.
        """
        self._builders[source_type] = builder

    def create_source(self, cfg: Any) -> AbstractPricingSource:
        """Build a pricing source for a config.

        Args:
            cfg: Config describing the source type and options.

        Returns:
            An instantiated pricing source.

        Raises:
            ValueError: If the source type is not registered.
        """
        source_type = cfg.type.strip().lower()
        builder = self._builders.get(source_type)
        if builder is None:
            msg = (
                f"Unknown pricing source type {cfg.type!r}. "
                "Supported types: litellm, openrouter, json, static"
            )
            raise ValueError(msg)
        return builder(cfg)

    def source_types(self) -> list[str]:
        """Return the registered source types.

        Returns:
            List of source types in registration order.
        """
        return list(self._builders.keys())

    def __contains__(self, source_type: str) -> bool:
        return source_type in self._builders


__all__ = ["PricingSourceBuilder", "PricingSourceRegistry"]
