from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend
from quadkit.ai.llm.routing.config import (
    GenerationDefaults,
    LLMConfig,
    ProviderConfig,
)
from quadkit.ai.llm.routing.strategies import LatencyOptimizedStrategy
from quadkit.ai.llm.types import Completion, TokenUsage
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


class TestLatencyOptimizedStrategy:
    @pytest.mark.asyncio
    async def test_unknown_latency_providers_tried_first(self) -> None:
        call_order: list[str] = []

        async def _a(messages, **kwargs):
            call_order.append("a")
            return Ok(_make_completion(text="a"))

        async def _b(messages, **kwargs):
            call_order.append("b")
            return Ok(_make_completion(text="b"))

        client_a = MagicMock()
        client_a.complete = AsyncMock(side_effect=_a)
        client_b = MagicMock()
        client_b.complete = AsyncMock(side_effect=_b)

        providers = [
            _make_provider_cfg("known-latency"),
            _make_provider_cfg("unknown-latency"),
        ]
        clients = {"known-latency:model-a": client_a, "unknown-latency:model-a": client_b}
        config = _make_config(providers)
        quota = _quota()

        strategy = LatencyOptimizedStrategy(skip_unhealthy=False)
        strategy.record_latency("known-latency:model-a", 500.0)

        result, _, _ = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert call_order[0] == "b"

    @pytest.mark.asyncio
    async def test_lower_latency_provider_tried_first(self) -> None:
        call_order: list[str] = []

        async def _fast(messages, **kwargs):
            call_order.append("fast")
            return Ok(_make_completion(text="fast"))

        async def _slow(messages, **kwargs):
            call_order.append("slow")
            return Ok(_make_completion(text="slow"))

        fast_client = MagicMock()
        fast_client.complete = AsyncMock(side_effect=_fast)
        slow_client = MagicMock()
        slow_client.complete = AsyncMock(side_effect=_slow)

        providers = [
            _make_provider_cfg("slow-p"),
            _make_provider_cfg("fast-p"),
        ]
        clients = {"slow-p:model-a": slow_client, "fast-p:model-a": fast_client}
        config = _make_config(providers)
        quota = _quota()

        strategy = LatencyOptimizedStrategy(skip_unhealthy=False)
        strategy.record_latency("slow-p:model-a", 800.0)
        strategy.record_latency("fast-p:model-a", 100.0)

        result, _, _ = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert call_order[0] == "fast"

    @pytest.mark.asyncio
    async def test_skip_unhealthy_bypasses_unhealthy_provider(self) -> None:
        unhealthy_client = MagicMock()
        health_result = MagicMock()
        health_result.status = "unhealthy"
        unhealthy_client.health_check = AsyncMock(return_value=health_result)
        unhealthy_client.complete = AsyncMock(return_value=Ok(_make_completion(text="x")))

        healthy_client = MagicMock()

        async def _hc_ok(**kwargs):
            r = MagicMock()
            r.status = "healthy"
            return r

        healthy_client.health_check = AsyncMock(side_effect=_hc_ok)
        healthy_client.complete = AsyncMock(return_value=Ok(_make_completion(text="healthy-ok")))

        providers = [
            _make_provider_cfg("unhealthy-p"),
            _make_provider_cfg("healthy-p"),
        ]
        clients = {"unhealthy-p:model-a": unhealthy_client, "healthy-p:model-a": healthy_client}
        config = _make_config(providers)
        quota = _quota()

        strategy = LatencyOptimizedStrategy(skip_unhealthy=True, health_timeout=1.0)
        result, tried, _ = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert result.content == "healthy-ok"
        unhealthy_client.complete.assert_not_awaited()

    def test_record_latency_tracks_rolling_window(self) -> None:
        strategy = LatencyOptimizedStrategy(window_size=3)
        strategy.record_latency("p", 100.0)
        strategy.record_latency("p", 200.0)
        strategy.record_latency("p", 300.0)
        strategy.record_latency("p", 400.0)

        avg = strategy._avg_latency("p")
        assert avg == pytest.approx((200.0 + 300.0 + 400.0) / 3)

    def test_avg_latency_returns_minus_one_for_unknown_provider(self) -> None:
        strategy = LatencyOptimizedStrategy()
        assert strategy._avg_latency("new-provider") == -1.0
