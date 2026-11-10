from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend
from quadkit.ai.llm.routing.config import (
    GenerationDefaults,
    LLMConfig,
    ProviderConfig,
)
from quadkit.ai.llm.routing.strategies import ParallelRaceStrategy
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


class TestParallelRaceStrategy:
    @pytest.mark.asyncio
    async def test_returns_first_completing_provider(self) -> None:
        p1 = _make_client(text="provider1")
        p2 = _make_client(text="provider2")
        providers = [_make_provider_cfg("p1"), _make_provider_cfg("p2")]
        clients = {"p1:model-a": p1, "p2:model-a": p2}
        config = _make_config(providers)
        quota = _quota()

        strategy = ParallelRaceStrategy()
        result, tried, total = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert result.provider in ("p1", "p2")
        assert len(tried) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_all_providers_fail(self) -> None:
        error = AIError("down")
        providers = [_make_provider_cfg("p1"), _make_provider_cfg("p2")]
        clients = {
            "p1:model-a": _make_client(error=error),
            "p2:model-a": _make_client(error=error),
        }
        config = _make_config(providers)
        quota = _quota()

        strategy = ParallelRaceStrategy()
        result, _, _ = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_skips_exhausted_providers(self) -> None:
        p1 = _make_client(text="p1")
        p2 = _make_client(text="p2")
        providers = [_make_provider_cfg("p1"), _make_provider_cfg("p2")]
        clients = {"p1:model-a": p1, "p2:model-a": p2}
        quota = _quota()
        await quota.mark_exhausted("p1:model-a")
        config = _make_config(providers)

        strategy = ParallelRaceStrategy()
        result, _, total = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert result.provider == "p2"
        assert total == 1
        p1.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_eligible_providers(self) -> None:
        quota = _quota()
        providers = [_make_provider_cfg("p1")]
        clients = {"p1:model-a": _make_client()}
        await quota.mark_exhausted("p1:model-a")
        config = _make_config(providers)

        strategy = ParallelRaceStrategy()
        result, _, total = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is None
        assert total == 0
