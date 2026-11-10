"""Round-55 pins: paid fallback routing strategy.

``PaidFallbackStrategy`` is the last line of the LLM routing chain —
free providers are exhausted, then this strategy burns through the
paid provider's model list in order.  It is billing-relevant (every
attempt here costs money) and previously had no dedicated coverage.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend
from quadkit.ai.llm.routing.config import (
    GenerationDefaults,
    LLMConfig,
    ProviderConfig,
)
from quadkit.ai.llm.routing.strategies.paid_fallback import (
    PaidFallbackConfig,
    PaidFallbackStrategy,
)
from quadkit.ai.llm.types import AIError, Completion, TokenUsage
from quadkit.result import Err, Ok

MESSAGES = [{"role": "user", "content": "hello"}]


def _make_completion(text: str = "ok", model: str = "paid-model") -> Completion:
    return Completion(
        content=text,
        model=model,
        usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
    )


def _make_client(
    *outcomes: Completion | Exception,
) -> MagicMock:
    """Client whose successive ``complete`` calls return *outcomes* in order."""
    client = MagicMock()
    values = [Ok(outcome) if isinstance(outcome, Completion) else Err(outcome) for outcome in outcomes]
    client.complete = AsyncMock(side_effect=values)
    return client


def _config() -> LLMConfig:
    providers = [
        ProviderConfig(name="free", model="free-model", api_key="fake", enabled=True)
    ]
    return LLMConfig(
        providers=providers,
        defaults=GenerationDefaults(temperature=0.1, max_tokens=64),
    )


def _strategy(client: MagicMock, paid: PaidFallbackConfig) -> PaidFallbackStrategy:
    return PaidFallbackStrategy(client, paid)


PAID = PaidFallbackConfig(provider="openai", models=["gpt-a", "gpt-b"])


class TestPaidFallbackConfig:
    def test_usable_requires_provider_and_models(self) -> None:
        assert PaidFallbackConfig(provider="openai", models=["m"]).is_usable
        assert not PaidFallbackConfig(provider="", models=["m"]).is_usable
        assert not PaidFallbackConfig(provider="openai", models=[]).is_usable


class TestPaidFallbackStrategy:
    @pytest.mark.asyncio
    async def test_unusable_config_short_circuits_without_calling_client(self) -> None:
        client = MagicMock()
        client.complete = AsyncMock()
        strategy = _strategy(client, PaidFallbackConfig(provider="", models=[]))
        result, tried, attempts = await strategy.execute(
            providers=[],
            clients={},
            quota=InMemoryQuotaBackend(),
            config=_config(),
            messages=MESSAGES,
            kwargs={},
        )
        assert result is None
        assert tried == []
        assert attempts == 0
        client.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_first_model_success_is_marked_paid(self) -> None:
        client = _make_client(_make_completion(text="from-paid", model="gpt-a"))
        strategy = _strategy(client, PAID)
        result, tried, attempts = await strategy.execute(
            providers=[],
            clients={},
            quota=InMemoryQuotaBackend(),
            config=_config(),
            messages=MESSAGES,
            kwargs={},
        )
        assert result is not None
        assert result.is_paid is True
        assert result.provider == "openai"
        assert result.model == "gpt-a"
        assert result.content == "from-paid"
        assert tried == ["paid:openai"]
        assert attempts == 1

    @pytest.mark.asyncio
    async def test_falls_through_to_next_model_on_ai_error(self) -> None:
        client = _make_client(
            AIError("rate limited"),
            _make_completion(text="from-second", model="gpt-b"),
        )
        strategy = _strategy(client, PAID)
        result, tried, attempts = await strategy.execute(
            providers=[],
            clients={},
            quota=InMemoryQuotaBackend(),
            config=_config(),
            messages=MESSAGES,
            kwargs={},
        )
        assert result is not None
        assert result.model == "gpt-b"
        assert result.content == "from-second"
        assert tried == ["paid:openai", "paid:openai"]
        assert attempts == 2

    @pytest.mark.asyncio
    async def test_all_models_failing_returns_none(self) -> None:
        client = _make_client(AIError("a"), AIError("b"))
        strategy = _strategy(client, PAID)
        result, tried, attempts = await strategy.execute(
            providers=[],
            clients={},
            quota=InMemoryQuotaBackend(),
            config=_config(),
            messages=MESSAGES,
            kwargs={},
        )
        assert result is None
        assert tried == ["paid:openai", "paid:openai"]
        assert attempts == 2

    @pytest.mark.asyncio
    async def test_non_ai_error_propagates(self) -> None:
        # Only AIError is swallowed per-model; infrastructure failures
        # fail fast instead of silently consuming the whole paid list.
        client = _make_client(RuntimeError("socket blown"))
        strategy = _strategy(client, PaidFallbackConfig(provider="openai", models=["m1"]))
        with pytest.raises(RuntimeError, match="socket blown"):
            await strategy.execute(
                providers=[],
                clients={},
                quota=InMemoryQuotaBackend(),
                config=_config(),
                messages=MESSAGES,
                kwargs={},
            )
