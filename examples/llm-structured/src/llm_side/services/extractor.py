"""Convention followed: **Service layer** — structured LLM parsing, prompt
caching, and token cost attribution live in a service; controllers stay thin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from llm_side.domains.tickets import TicketBrief
from quadkit.ai.llm import LLMCache, complete_with_schema
from quadkit.ai.llm.pricing import ModelPricing, PricingCostEstimator
from quadkit.contracts.exceptions import ValidationError
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.ai import LLMClientProtocol


class TicketExtractionService:
    """Extract typed ``TicketBrief`` records with caching and cost tracking."""

    def __init__(
        self,
        *,
        llm: LLMClientProtocol,
        cache: LLMCache,
        model: str,
        cache_ttl: float,
    ) -> None:
        self._llm = llm
        self._cache = cache
        self._model = model
        self._cache_ttl = cache_ttl
        self._estimator = PricingCostEstimator(
            {
                model: ModelPricing(
                    model=model,
                    provider="deterministic",
                    prompt_per_1m=3.0,
                    completion_per_1m=15.0,
                )
            }
        )
        self._total_cost_usd = 0.0
        self._extractions = 0

    async def extract(
        self, text: str
    ) -> Result[dict[str, Any], ValidationError]:
        """Parse *text* into a validated ``TicketBrief``."""
        cleaned = text.strip()
        if not cleaned:
            return Err(ValidationError("text is required"))

        cached_entry = await self._cache.get(cleaned)
        if cached_entry is not None:
            return Ok(
                {
                    "brief": cached_entry,
                    "cached": True,
                    "model": self._model,
                    "estimated_cost_usd": 0.0,
                }
            )

        brief = await complete_with_schema(
            self._llm,
            cleaned,
            schema=TicketBrief,
        )
        brief_dict = {
            "category": brief.category,
            "severity": brief.severity,
            "summary": brief.summary,
            "action_items": list(brief.action_items),
        }
        await self._cache.set(cleaned, brief_dict, ttl=self._cache_ttl)

        prompt_tokens = max(12, len(cleaned.split()) * 2)
        completion_tokens = 32
        cost = self._estimator.estimate_cost(
            model=self._model,
            total_tokens=prompt_tokens + completion_tokens,
            provider="deterministic",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        self._total_cost_usd += cost
        self._extractions += 1

        return Ok(
            {
                "brief": brief_dict,
                "cached": False,
                "model": self._model,
                "estimated_cost_usd": round(cost, 6),
            }
        )

    def stats(self) -> dict[str, Any]:
        """Return cache statistics and cumulative token cost."""
        cache_stats = self._cache.get_stats()
        return {
            "model": self._model,
            "extractions": self._extractions,
            "total_cost_usd": round(self._total_cost_usd, 6),
            "cache": {
                "hits": cache_stats.hits,
                "misses": cache_stats.misses,
                "total_entries": cache_stats.total_entries,
            },
        }


__all__ = ["TicketExtractionService"]
