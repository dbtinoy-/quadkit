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
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.web import HttpResponse, HttpStatusError
from quadkit.result import Err


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
async def test_router_returns_err_when_all_providers_fail():
    failing_client = AsyncMock()
    failing_client.complete = AsyncMock(return_value=Err(AIError("failed")))

    config = _make_config([_make_provider_cfg("groq")])
    router = _make_router({"groq:model-a": failing_client}, config)

    result = await router.route(messages=[])

    assert result.is_err()
    error = result.unwrap_err()
    assert "exhausted" in error.message.lower()
    assert "groq" in error.providers_tried


@pytest.mark.asyncio
async def test_router_returns_err_with_no_providers_configured():
    config = _make_config([])
    router = _make_router({}, config)

    result = await router.route(messages=[])

    assert result.is_err()


@pytest.mark.asyncio
async def test_router_health_probe_uses_client_health_check_without_inference_side_effects():
    client = AsyncMock()
    client.health_check = AsyncMock(
        return_value=HealthCheckResult(
            component="groq",
            status=HealthStatus.HEALTHY,
            duration_ms=12.5,
        )
    )
    client.complete = AsyncMock(
        side_effect=AssertionError("complete should not be called")
    )

    quota_backend = InMemoryQuotaBackend()
    logger = InMemoryInferenceLogger()
    config = _make_config([_make_provider_cfg("groq")])
    router = LLMRouter(
        clients={"groq:model-a": client},
        quota_backend=quota_backend,
        inference_logger=logger,
        config=config,
    )

    result = await router.health_probe()

    assert result.is_ok()
    log = result.unwrap()
    client.health_check.assert_awaited_once_with(timeout=5.0)
    client.complete.assert_not_called()
    assert log.result is not None
    assert log.result.provider == "groq"
    assert log.result.model == "model-a"
    assert log.result.content == "health_probe"
    assert log.result.prompt_tokens == 0
    assert log.result.completion_tokens == 0
    assert log.total_attempts == 1
    assert log.context == {"health_probe": True}
    assert await logger.get_recent() == []
    assert await quota_backend.get_usage("groq") is None


@pytest.mark.asyncio
async def test_router_health_probe_continues_when_health_check_raises_http_status_error():
    groq_client = AsyncMock()
    groq_client.health_check = AsyncMock(
        side_effect=HttpStatusError(
            "HTTP 503 for GET https://api.groq.test/health",
            status=503,
            response=HttpResponse(
                status=503,
                url="https://api.groq.test/health",
                method="GET",
            ),
        )
    )
    groq_client.complete = AsyncMock(
        side_effect=AssertionError("complete should not be called")
    )

    gemini_client = AsyncMock()
    gemini_client.health_check = AsyncMock(
        return_value=HealthCheckResult(
            component="gemini",
            status=HealthStatus.HEALTHY,
            duration_ms=7.5,
        )
    )
    gemini_client.complete = AsyncMock(
        side_effect=AssertionError("complete should not be called")
    )

    quota_backend = InMemoryQuotaBackend()
    logger = InMemoryInferenceLogger()
    config = _make_config(
        [
            _make_provider_cfg("groq"),
            _make_provider_cfg("gemini"),
        ]
    )
    router = LLMRouter(
        clients={"groq:model-a": groq_client, "gemini:model-a": gemini_client},
        quota_backend=quota_backend,
        inference_logger=logger,
        config=config,
    )

    result = await router.health_probe()

    assert result.is_ok()
    log = result.unwrap()
    assert log.result is not None
    assert log.result.provider == "gemini"
    assert log.providers_tried == ["groq", "gemini"]
    groq_client.health_check.assert_awaited_once_with(timeout=5.0)
    gemini_client.health_check.assert_awaited_once_with(timeout=5.0)
    groq_client.complete.assert_not_called()
    gemini_client.complete.assert_not_called()
    assert await logger.get_recent() == []
    assert await quota_backend.get_usage("groq") is None
    assert await quota_backend.get_usage("gemini") is None


@pytest.mark.asyncio
async def test_router_health_probe_continues_when_health_check_returns_malformed_result():
    groq_client = AsyncMock()
    groq_client.health_check = AsyncMock(return_value={})
    groq_client.complete = AsyncMock(
        side_effect=AssertionError("complete should not be called")
    )

    gemini_client = AsyncMock()
    gemini_client.health_check = AsyncMock(
        return_value=HealthCheckResult(
            component="gemini",
            status=HealthStatus.HEALTHY,
            duration_ms=7.5,
        )
    )
    gemini_client.complete = AsyncMock(
        side_effect=AssertionError("complete should not be called")
    )

    quota_backend = InMemoryQuotaBackend()
    logger = InMemoryInferenceLogger()
    config = _make_config(
        [
            _make_provider_cfg("groq"),
            _make_provider_cfg("gemini"),
        ]
    )
    router = LLMRouter(
        clients={"groq:model-a": groq_client, "gemini:model-a": gemini_client},
        quota_backend=quota_backend,
        inference_logger=logger,
        config=config,
    )

    result = await router.health_probe()

    assert result.is_ok()
    log = result.unwrap()
    assert log.result is not None
    assert log.result.provider == "gemini"
    assert log.providers_tried == ["groq", "gemini"]
    groq_client.health_check.assert_awaited_once_with(timeout=5.0)
    gemini_client.health_check.assert_awaited_once_with(timeout=5.0)
    groq_client.complete.assert_not_called()
    gemini_client.complete.assert_not_called()
    assert await logger.get_recent() == []
    assert await quota_backend.get_usage("groq") is None
    assert await quota_backend.get_usage("gemini") is None


@pytest.mark.asyncio
async def test_router_health_probe_continues_when_health_check_raises_runtime_exception(
    capsys,
):
    secret = "ROUTER_HEALTH_SECRET_SENTINEL"
    groq_client = AsyncMock()
    groq_client.health_check = AsyncMock(side_effect=TimeoutError(secret))
    groq_client.complete = AsyncMock(
        side_effect=AssertionError("complete should not be called")
    )

    gemini_client = AsyncMock()
    gemini_client.health_check = AsyncMock(
        return_value=HealthCheckResult(
            component="gemini",
            status=HealthStatus.UNHEALTHY,
            error="gemini unavailable",
        )
    )
    gemini_client.complete = AsyncMock(
        side_effect=AssertionError("complete should not be called")
    )

    quota_backend = InMemoryQuotaBackend()
    logger = InMemoryInferenceLogger()
    config = _make_config(
        [
            _make_provider_cfg("groq"),
            _make_provider_cfg("gemini"),
        ]
    )
    router = LLMRouter(
        clients={"groq:model-a": groq_client, "gemini:model-a": gemini_client},
        quota_backend=quota_backend,
        inference_logger=logger,
        config=config,
    )

    result = await router.health_probe()

    assert result.is_err()
    error = result.unwrap_err()
    assert error.providers_tried == ["groq", "gemini"]
    assert "healthy" in error.message.lower()
    groq_client.health_check.assert_awaited_once_with(timeout=5.0)
    gemini_client.health_check.assert_awaited_once_with(timeout=5.0)
    groq_client.complete.assert_not_called()
    gemini_client.complete.assert_not_called()
    assert await logger.get_recent() == []
    assert await quota_backend.get_usage("groq") is None
    assert await quota_backend.get_usage("gemini") is None
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err


@pytest.mark.asyncio
async def test_router_health_probe_returns_err_with_attempted_providers_only(
    capsys,
):
    secret = "ROUTER_HEALTH_RESULT_SECRET_SENTINEL"
    disabled_client = AsyncMock()
    disabled_client.health_check = AsyncMock()

    groq_client = AsyncMock()
    groq_client.health_check = AsyncMock(
        return_value=HealthCheckResult(
            component="groq",
            status=HealthStatus.UNHEALTHY,
            error=secret,
        )
    )
    groq_client.complete = AsyncMock(
        side_effect=AssertionError("complete should not be called")
    )

    gemini_client = AsyncMock()
    gemini_client.health_check = AsyncMock(
        return_value=HealthCheckResult(
            component="gemini",
            status=HealthStatus.DEGRADED,
            message="warming up",
        )
    )
    gemini_client.complete = AsyncMock(
        side_effect=AssertionError("complete should not be called")
    )

    config = _make_config(
        [
            ProviderConfig(
                name="disabled",
                model="disabled-model",
                api_key="fake-key",
                enabled=False,
            ),
            _make_provider_cfg("missing"),
            _make_provider_cfg("groq"),
            _make_provider_cfg("gemini"),
        ]
    )
    router = _make_router(
        {
            "disabled": disabled_client,
            "groq:model-a": groq_client,
            "gemini:model-a": gemini_client,
        },
        config,
    )

    result = await router.health_probe()

    assert result.is_err()
    error = result.unwrap_err()
    assert error.providers_tried == ["groq", "gemini"]
    assert "healthy" in error.message.lower()
    disabled_client.health_check.assert_not_called()
    groq_client.health_check.assert_awaited_once_with(timeout=5.0)
    gemini_client.health_check.assert_awaited_once_with(timeout=5.0)
    groq_client.complete.assert_not_called()
    gemini_client.complete.assert_not_called()
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err


@pytest.mark.asyncio
async def test_router_close_calls_close_on_all_clients():
    client_a = AsyncMock()
    client_a.close = AsyncMock()
    client_b = AsyncMock()
    client_b.close = AsyncMock()

    config = _make_config([])
    router = _make_router({"a": client_a, "b": client_b}, config)

    await router.close()

    client_a.close.assert_called_once()
    client_b.close.assert_called_once()


class TestStrategyFromConfig:
    def test_cost_optimized_uses_default_pricing_sources(self) -> None:
        from quadkit.ai.llm.routing.strategies import CostOptimizedStrategy

        cfg = LLMConfig(strategy="cost_optimized")
        strategy = LLMRouter._strategy_from_config(cfg)

        assert isinstance(strategy, CostOptimizedStrategy)
        assert strategy._pricing.sources, "expected at least one default pricing source"
