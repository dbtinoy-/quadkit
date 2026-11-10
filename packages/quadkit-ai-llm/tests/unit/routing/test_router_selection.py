from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend
from quadkit.ai.llm.routing.config import (
    GenerationDefaults,
    LLMConfig,
    ProviderConfig,
)
from quadkit.ai.llm.routing.loggers.memory import InMemoryInferenceLogger
from quadkit.ai.llm.routing.router import LLMRouter
from quadkit.ai.llm.types import AIError, Completion, TokenUsage
from quadkit.result import Err, Ok


def _make_completion(text: str = "hello") -> Completion:
    return Completion(
        content=text,
        model="test-model",
        usage=TokenUsage(prompt_tokens=5, completion_tokens=10, total_tokens=15),
    )


def _make_config(
    providers: list[ProviderConfig],
) -> LLMConfig:
    return LLMConfig(
        providers=providers,
        defaults=GenerationDefaults(temperature=0.2),
    )


def _make_provider_cfg(name: str, primary: str = "model-a") -> ProviderConfig:
    return ProviderConfig(
        name=name,
        model=primary,
        api_key="fake-key",
    )


def _make_router(
    clients: dict,
    config: LLMConfig,
) -> LLMRouter:
    return LLMRouter(
        clients=clients,
        quota_backend=InMemoryQuotaBackend(),
        inference_logger=InMemoryInferenceLogger(),
        config=config,
    )


@pytest.mark.asyncio
async def test_router_returns_ok_on_first_provider_success():
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=Ok(_make_completion("hi")))

    config = _make_config([_make_provider_cfg("groq")])
    router = _make_router({"groq:model-a": mock_client}, config)

    result = await router.route(messages=[{"role": "user", "content": "hello"}])

    assert result.is_ok()
    log = result.unwrap()
    assert log.result is not None
    assert log.result.provider == "groq"
    assert log.result.content == "hi"
    assert log.succeeded is True


@pytest.mark.asyncio
async def test_router_logs_successful_inference():
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=Ok(_make_completion("hi")))

    logger = InMemoryInferenceLogger()
    config = _make_config([_make_provider_cfg("groq")])
    router = LLMRouter(
        clients={"groq:model-a": mock_client},
        quota_backend=InMemoryQuotaBackend(),
        inference_logger=logger,
        config=config,
    )

    await router.route(messages=[{"role": "user", "content": "hello"}])
    recent = await logger.get_recent()
    assert len(recent) == 1
    assert recent[0].succeeded is True


@pytest.mark.asyncio
async def test_router_keeps_context_for_correlation_without_forwarding_to_provider():
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=Ok(_make_completion("hi")))
    logger = InMemoryInferenceLogger()
    router = LLMRouter(
        clients={"groq:model-a": mock_client},
        quota_backend=InMemoryQuotaBackend(),
        inference_logger=logger,
        config=_make_config([_make_provider_cfg("groq")]),
    )

    result = await router.route(
        messages=[{"role": "user", "content": "hello"}],
        context={"analysis_id": "analysis-123"},
    )

    assert result.is_ok()
    recent = await logger.get_recent()
    assert recent[0].context == {"analysis_id": "analysis-123"}
    assert "context" not in mock_client.complete.await_args.kwargs


@pytest.mark.asyncio
async def test_router_falls_through_to_second_provider_on_error():
    failing_client = AsyncMock()
    failing_client.complete = AsyncMock(return_value=Err(AIError("boom")))

    succeeding_client = AsyncMock()
    succeeding_client.complete = AsyncMock(
        return_value=Ok(_make_completion("ok from gemini"))
    )

    config = _make_config(
        [
            _make_provider_cfg("groq"),
            _make_provider_cfg("gemini"),
        ]
    )
    router = _make_router(
        {"groq:model-a": failing_client, "gemini:model-a": succeeding_client}, config
    )

    result = await router.route(messages=[{"role": "user", "content": "hello"}])

    assert result.is_ok()
    log = result.unwrap()
    assert log.result.provider == "gemini"
    assert log.total_attempts == 2


@pytest.mark.asyncio
async def test_router_skips_exhausted_provider():
    backend = InMemoryQuotaBackend()
    await backend.mark_exhausted("groq:model-a")

    succeeding_client = AsyncMock()
    succeeding_client.complete = AsyncMock(return_value=Ok(_make_completion("ok")))

    config = _make_config(
        [
            _make_provider_cfg("groq"),
            _make_provider_cfg("gemini"),
        ]
    )
    router = LLMRouter(
        clients={"groq:model-a": AsyncMock(), "gemini:model-a": succeeding_client},
        quota_backend=backend,
        inference_logger=InMemoryInferenceLogger(),
        config=config,
    )

    result = await router.route(messages=[{"role": "user", "content": "hello"}])

    assert result.is_ok()
    log = result.unwrap()
    assert log.result.provider == "gemini"
    assert log.total_attempts == 1


@pytest.mark.asyncio
async def test_router_tries_single_model_per_provider():
    call_count = 0

    async def complete_side_effect(messages, model, **kwargs):
        nonlocal call_count
        call_count += 1
        return Ok(_make_completion(f"ok from {model}"))

    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(side_effect=complete_side_effect)

    config = _make_config([_make_provider_cfg("groq", primary="model-a")])
    router = _make_router({"groq:model-a": mock_client}, config)

    result = await router.route(messages=[])

    assert result.is_ok()
    assert call_count == 1
    log = result.unwrap()
    assert log.result.content == "ok from model-a"


@pytest.mark.asyncio
async def test_router_skips_disabled_provider():
    disabled_cfg = ProviderConfig(
        name="groq",
        model="model-a",
        api_key="key",
        enabled=False,
    )
    succeeding = AsyncMock()
    succeeding.complete = AsyncMock(return_value=Ok(_make_completion("ok")))

    config = _make_config([disabled_cfg, _make_provider_cfg("gemini")])
    router = _make_router(
        {"groq:model-a": AsyncMock(), "gemini:model-a": succeeding}, config
    )

    result = await router.route(messages=[])

    assert result.is_ok()
    log = result.unwrap()
    assert log.result.provider == "gemini"
    assert "groq" not in log.providers_tried
