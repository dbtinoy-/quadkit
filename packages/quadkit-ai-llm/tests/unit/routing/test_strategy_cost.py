from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend
from quadkit.ai.llm.routing.config import (
    GenerationDefaults,
    LLMConfig,
    ProviderConfig,
)
from quadkit.ai.llm.routing.strategies import CostOptimizedStrategy
from quadkit.ai.llm.types import AIError, Completion, TokenUsage
from quadkit.result import Err, Ok


def _make_completion(text: str = "ok", model: str = "m", tokens: int = 10) -> Completion:
    return Completion(
        content=text,
        model=model,
        usage=TokenUsage(
            prompt_tokens=tokens // 2,
            completion_tokens=tokens // 2,
            total_tokens=tokens,
        ),
    )


def _make_config(
    providers: list[ProviderConfig],
) -> LLMConfig:
    return LLMConfig(
        providers=providers,
        defaults=GenerationDefaults(temperature=0.2, max_tokens=None),
    )


def _make_provider_cfg(
    name: str,
    primary: str = "model-a",
    enabled: bool = True,
) -> ProviderConfig:
    return ProviderConfig(
        name=name,
        model=primary,
        api_key="fake-key",
        enabled=enabled,
    )


def _make_client(
    *,
    text: str = "ok",
    error: Exception | None = None,
) -> MagicMock:
    client = MagicMock()
    if error is not None:
        client.complete = AsyncMock(return_value=Err(error))
    else:
        client.complete = AsyncMock(return_value=Ok(_make_completion(text=text)))
    return client


def _quota() -> InMemoryQuotaBackend:
    return InMemoryQuotaBackend()


MESSAGES = [{"role": "user", "content": "hello"}]


class TestCostOptimizedStrategy:
    def _make_pricing_manager(self, costs: dict[str, tuple[float, float]]) -> MagicMock:
        pm = MagicMock()

        async def _get_pricing(model: str):
            if model in costs:
                p, c = costs[model]
                pricing = MagicMock()
                pricing.prompt_per_1m = p
                pricing.completion_per_1m = c
                return pricing
            raise KeyError(model)

        pm.get_pricing = _get_pricing
        return pm

    @pytest.mark.asyncio
    async def test_tries_cheapest_provider_first(self) -> None:
        call_order: list[str] = []

        async def _complete_cheap(messages, **kwargs):
            call_order.append("cheap")
            return Ok(_make_completion(text="cheap-result"))

        async def _complete_expensive(messages, **kwargs):
            call_order.append("expensive")
            return Ok(_make_completion(text="expensive-result"))

        cheap_client = MagicMock()
        cheap_client.complete = AsyncMock(side_effect=_complete_cheap)
        expensive_client = MagicMock()
        expensive_client.complete = AsyncMock(side_effect=_complete_expensive)

        providers = [
            _make_provider_cfg("expensive", primary="expensive-model"),
            _make_provider_cfg("cheap", primary="cheap-model"),
        ]
        clients = {"expensive:expensive-model": expensive_client, "cheap:cheap-model": cheap_client}
        pm = self._make_pricing_manager(
            {
                "cheap-model": (1.0, 2.0),
                "expensive-model": (10.0, 20.0),
            }
        )
        config = _make_config(providers)
        quota = _quota()

        strategy = CostOptimizedStrategy(pricing_manager=pm)
        result, _, _ = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert result.content == "cheap-result"
        assert call_order[0] == "cheap"

    @pytest.mark.asyncio
    async def test_unknown_cost_provider_tried_last(self) -> None:
        call_order: list[str] = []

        async def _complete_known(messages, **kwargs):
            call_order.append("known")
            return Ok(_make_completion(text="known"))

        async def _complete_unknown(messages, **kwargs):
            call_order.append("unknown")
            return Ok(_make_completion(text="unknown"))

        known_client = MagicMock()
        known_client.complete = AsyncMock(side_effect=_complete_known)
        unknown_client = MagicMock()
        unknown_client.complete = AsyncMock(side_effect=_complete_unknown)

        providers = [
            _make_provider_cfg("unknown-pricing", primary="no-pricing-model"),
            _make_provider_cfg("known-pricing", primary="known-model"),
        ]
        clients = {
            "unknown-pricing:no-pricing-model": unknown_client,
            "known-pricing:known-model": known_client,
        }
        pm = self._make_pricing_manager({"known-model": (1.0, 1.0)})
        config = _make_config(providers)
        quota = _quota()

        strategy = CostOptimizedStrategy(pricing_manager=pm)
        result, _, _ = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert call_order[0] == "known"

    @pytest.mark.asyncio
    async def test_falls_through_to_next_on_failure(self) -> None:
        cheap_client = _make_client(error=AIError("cheap down"))
        expensive_client = _make_client(text="expensive-result")

        providers = [
            _make_provider_cfg("cheap", primary="cheap-model"),
            _make_provider_cfg("expensive", primary="expensive-model"),
        ]
        clients = {"cheap:cheap-model": cheap_client, "expensive:expensive-model": expensive_client}
        pm = self._make_pricing_manager(
            {"cheap-model": (1.0, 1.0), "expensive-model": (5.0, 5.0)}
        )
        config = _make_config(providers)
        quota = _quota()

        strategy = CostOptimizedStrategy(pricing_manager=pm)
        result, _, _ = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert result.content == "expensive-result"
