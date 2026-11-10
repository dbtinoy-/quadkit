"""Pricing data types for LLM models.

This module defines the core pricing data structures used throughout
the pricing system.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import model_serializer

from quadkit.domain import DomainModel
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class ModelPricing(DomainModel):
    """Pricing information for a specific LLM model.

    Attributes:
        model: Model identifier (e.g., "gpt-4-turbo", "claude-3-opus").
        prompt_per_1m: Cost per 1 million prompt tokens in USD.
        completion_per_1m: Cost per 1 million completion tokens in USD.
        provider: Provider name (e.g., "openai", "anthropic").
        last_updated: When pricing was last updated.
        source: Where pricing data came from (e.g., "json", "api", "static").

    Example:
        >>> pricing = ModelPricing(
        ...     model="gpt-4-turbo",
        ...     prompt_per_1m=10.00,
        ...     completion_per_1m=30.00,
        ...     provider="openai"
        ... )
        >>> print(f"${pricing.prompt_per_1m} per 1M prompt tokens")

    """

    model: str = Field(..., description="Model identifier")
    prompt_per_1m: float = Field(..., description="Cost per 1M prompt tokens (USD)")
    completion_per_1m: float = Field(
        ...,
        description="Cost per 1M completion tokens (USD)",
    )
    provider: str = Field(..., description="Provider name")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update timestamp",
    )
    source: str = Field(default="static", description="Data source")

    model_config = ConfigDict()

    @model_serializer(mode="wrap")
    def serialize_model(
        self, handler: Callable[[ModelPricing], dict[str, Any]]
    ) -> dict[str, Any]:
        """Custom serializer to handle datetime objects."""
        data = handler(self)
        # Convert datetime objects to ISO format strings
        if isinstance(data.get("last_updated"), datetime):
            data["last_updated"] = data["last_updated"].isoformat()
        return data
