"""Cost-Optimized Routing Strategy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.routing.config import LLMConfig, ProviderConfig
from quadkit.ai.llm.routing.strategies.base import (
    _attempt_provider,
    _estimate_prompt_tokens,
    _gen_defaults,
    _handle_free_failure,
)
from quadkit.ai.llm.routing.types import InferenceResult
from quadkit.ai.llm.types import AIError
from quadkit.contracts.ai import LLMClientProtocol
from quadkit.contracts.ai.routing import QuotaBackendProtocol
from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.ai.llm.pricing.manager import PricingManager

logger = get_logger(__name__)


class CostOptimizedStrategy:
    """Sort providers by per-token cost and try cheapest first.

    Requires a ``PricingManager`` for cost lookups.  Providers whose
    pricing is unavailable are pushed to the end of the queue.
    """

    def __init__(self, pricing_manager: PricingManager) -> None:
        self._pricing = pricing_manager

    async def execute(
        self,
        *,
        providers: list[ProviderConfig],
        clients: dict[str, LLMClientProtocol],
        quota: QuotaBackendProtocol,
        config: LLMConfig,
        messages: list[Any],
        kwargs: dict[str, Any],
    ) -> tuple[InferenceResult | None, list[str], int]:
        temperature, max_tokens = _gen_defaults(config, kwargs)

        # Estimate token counts for cost scoring.
        estimated_prompt = _estimate_prompt_tokens(messages)
        estimated_completion = max_tokens or 500

        # Sort by estimated cost; unknown cost → infinity.
        scored: list[tuple[float, ProviderConfig]] = []
        for pcfg in providers:
            if not pcfg.enabled:
                continue
            if clients.get(pcfg.key) is None:
                continue
            try:
                pricing = await self._pricing.get_pricing(pcfg.model)
                if pricing is None:
                    cost = float("inf")
                else:
                    cost = (estimated_prompt / 1_000_000) * pricing.prompt_per_1m + (
                        estimated_completion / 1_000_000
                    ) * pricing.completion_per_1m
            except Exception:  # noqa: BLE001 — cost estimation falls back to infinity on any failure
                cost = float("inf")
            scored.append((cost, pcfg))

        scored.sort(key=lambda pair: pair[0])

        # Delegate to sequential over the cost-sorted order.
        providers_tried: list[str] = []
        total_attempts = 0

        for _cost, pcfg in scored:
            client = clients[pcfg.key]
            providers_tried.append(pcfg.name)

            if await quota.is_exhausted(pcfg.key):
                continue

            model = pcfg.model
            total_attempts += 1
            try:
                result = await _attempt_provider(
                    client=client,
                    provider_name=pcfg.name,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                await quota.increment(pcfg.key)
                logger.info("cost_strategy_provider_succeeded", cost_score=_cost)
                return result, providers_tried, total_attempts
            except AIError as exc:
                await _handle_free_failure(
                    exc=exc,
                    provider_key=pcfg.key,
                    model=model,
                    quota=quota,
                    cooldown_seconds=config.quota.cooldown_seconds,
                )

        return None, providers_tried, total_attempts
