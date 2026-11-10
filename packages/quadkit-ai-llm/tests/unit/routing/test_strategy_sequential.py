from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend
from quadkit.ai.llm.routing.config import (
    GenerationDefaults,
    LLMConfig,
    ProviderConfig,
)
from quadkit.ai.llm.routing.strategies import SequentialCascadeStrategy
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


class TestSequentialCascadeStrategy:
    @pytest.mark.asyncio
    async def test_returns_first_provider_result_on_success(self) -> None:
        client = _make_client(text="from-groq")
        providers = [_make_provider_cfg("groq")]
        clients = {"groq:model-a": client}
        config = _make_config(providers)
        quota = _quota()

        strategy = SequentialCascadeStrategy()
        result, tried, attempts = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert result.provider == "groq"
        assert result.content == "from-groq"
        assert "groq" in tried
        assert attempts == 1

    @pytest.mark.asyncio
    async def test_falls_through_to_second_provider_on_failure(self) -> None:
        failing = _make_client(error=AIError("quota"))
        working = _make_client(text="from-gemini")
        providers = [
            _make_provider_cfg("groq"),
            _make_provider_cfg("gemini"),
        ]
        clients = {"groq:model-a": failing, "gemini:model-a": working}
        config = _make_config(providers)
        quota = _quota()

        strategy = SequentialCascadeStrategy()
        result, tried, attempts = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert result.provider == "gemini"

    @pytest.mark.asyncio
    async def test_skips_exhausted_provider(self) -> None:
        groq = _make_client(text="groq-would-succeed")
        gemini = _make_client(text="from-gemini")
        providers = [
            _make_provider_cfg("groq"),
            _make_provider_cfg("gemini"),
        ]
        clients = {"groq:model-a": groq, "gemini:model-a": gemini}
        quota = _quota()
        await quota.mark_exhausted("groq:model-a")
        config = _make_config(providers)

        strategy = SequentialCascadeStrategy()
        result, tried, attempts = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert result.provider == "gemini"
        groq.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_none_when_all_providers_fail(self) -> None:
        error = AIError("down")
        providers = [
            _make_provider_cfg("p1"),
            _make_provider_cfg("p2"),
        ]
        clients = {"p1:model-a": _make_client(error=error), "p2:model-a": _make_client(error=error)}
        config = _make_config(providers)
        quota = _quota()

        strategy = SequentialCascadeStrategy()
        result, tried, attempts = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_skips_disabled_provider(self) -> None:
        disabled = _make_client(text="should-not-appear")
        enabled = _make_client(text="enabled")
        providers = [
            _make_provider_cfg("disabled-p", enabled=False),
            _make_provider_cfg("enabled-p"),
        ]
        clients = {"disabled-p:model-a": disabled, "enabled-p:model-a": enabled}
        config = _make_config(providers)
        quota = _quota()

        strategy = SequentialCascadeStrategy()
        result, _, _ = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is not None
        assert result.provider == "enabled-p"
        disabled.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_model_failure_exhausts_provider(self) -> None:
        attempts_args: list[dict] = []

        async def _complete(messages, **kwargs):
            model = kwargs.get("model", "unknown")
            attempts_args.append({"model": model})
            return Err(AIError("model down"))

        client = MagicMock()
        client.complete = AsyncMock(side_effect=_complete)

        providers = [
            _make_provider_cfg("groq", primary="primary-model")
        ]
        clients = {"groq:primary-model": client}
        config = _make_config(providers)
        quota = _quota()

        strategy = SequentialCascadeStrategy()
        result, _, attempts = await strategy.execute(
            providers=providers,
            clients=clients,
            quota=quota,
            config=config,
            messages=MESSAGES,
            kwargs={},
        )

        assert result is None
        assert attempts == 1
