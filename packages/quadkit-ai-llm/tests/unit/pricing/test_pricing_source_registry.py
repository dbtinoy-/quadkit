"""Tests for PricingSourceRegistry."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.config import PricingSourceConfig
from quadkit.ai.llm.pricing.pricing_source_registry import (
    PricingSourceRegistry,
)
from quadkit.ai.llm.pricing.pricing_source_static import StaticPricingSource
from quadkit.ai.llm.pricing.sources import (
    APIPricingSource,
    JSONFilePricingSource,
    OpenRouterPricingSource,
)


def test_registry_has_all_default_source_types() -> None:
    """with_defaults registers the four built-in pricing source types."""
    registry = PricingSourceRegistry.with_defaults()
    assert set(registry.source_types()) == {"litellm", "openrouter", "json", "static"}


def test_create_litellm() -> None:
    """litellm dispatches to APIPricingSource with the default endpoint."""
    source = PricingSourceRegistry.with_defaults().create_source(
        PricingSourceConfig(type="litellm")
    )
    assert isinstance(source, APIPricingSource)
    assert "BerriAI/litellm" in source.endpoint


def test_create_openrouter() -> None:
    """openrouter dispatches to OpenRouterPricingSource."""
    source = PricingSourceRegistry.with_defaults().create_source(
        PricingSourceConfig(type="openrouter")
    )
    assert isinstance(source, OpenRouterPricingSource)


def test_create_json_requires_file_path() -> None:
    """A json source without file_path raises the existing ValueError."""
    with pytest.raises(ValueError, match="file_path"):
        PricingSourceRegistry.with_defaults().create_source(
            PricingSourceConfig(type="json")
        )


def test_create_json_with_file_path() -> None:
    """A json source with file_path dispatches to JSONFilePricingSource."""
    source = PricingSourceRegistry.with_defaults().create_source(
        PricingSourceConfig(type="json", file_path="pricing/custom.json")
    )
    assert isinstance(source, JSONFilePricingSource)


def test_create_static() -> None:
    """A static source dispatches to StaticPricingSource."""
    source = PricingSourceRegistry.with_defaults().create_source(
        PricingSourceConfig(
            type="static",
            models={"internal": {"prompt_per_1m": 0.5, "completion_per_1m": 1.5}},
        )
    )
    assert isinstance(source, StaticPricingSource)


def test_create_unknown_source_raises() -> None:
    """An unknown source type raises the existing full-message ValueError."""
    with pytest.raises(ValueError, match=r"Unknown pricing source type 'bogus'"):
        PricingSourceRegistry.with_defaults().create_source(
            PricingSourceConfig(type="bogus")
        )
