from __future__ import annotations

from typing import Any

import pytest

from quadkit.ai.llm.admin.contributor import LlmAdminContributor
from quadkit.ai.llm.routing.config import LLMConfig, ProviderConfig
from quadkit.ai.llm.routing.types import InferenceLog, InferenceResult
from quadkit.ai.llm.routing import InferenceError
from quadkit.contracts.admin.types import WidgetParams
from quadkit.contracts.admin.widget_content import (
    MessageContent,
    StatContent,
    TableContent,
    Tone,
)
from quadkit.contracts.ai.routing import (
    InferenceLoggerProtocol,
    LLMRouterProtocol,
)
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.result import Ok


class FakeProviderRouter:
    def __init__(
        self,
        *,
        providers: list[ProviderConfig],
        clients: dict[str, Any],
    ) -> None:
        self._config = LLMConfig(providers=providers)
        self._clients = clients


class FakeLogger:
    def __init__(self, logs: list[InferenceLog]) -> None:
        self._logs = logs

    async def get_recent(self, limit: int = 100) -> list[InferenceLog]:
        return self._logs


class FakeContainer:
    def __init__(
        self,
        *,
        router: Any = None,
        logger: Any = None,
    ) -> None:
        self._router = router
        self._logger = logger

    async def resolve(self, service_type: type) -> Any:
        if service_type is LLMRouterProtocol:
            return self._router
        if service_type is InferenceLoggerProtocol:
            return self._logger
        raise AssertionError(f"unexpected protocol: {service_type}")


class TestLlmAdminRendering:
    @pytest.fixture
    def contributor(self) -> LlmAdminContributor:
        return LlmAdminContributor()

    async def _boot_contributor(
        self,
        contributor: LlmAdminContributor,
        *,
        logs: list[InferenceLog] | None = None,
        provider_router: Any = None,
    ) -> None:
        container = FakeContainer(
            logger=FakeLogger(logs or []) if logs is not None else None,
            router=provider_router,
        )
        await contributor.on_admin_boot(container)

    async def _error_rate_test(
        self,
        contributor: LlmAdminContributor,
        *,
        succeeded: int,
        failed: int,
    ) -> StatContent:
        logs: list[InferenceLog] = [
            self._success_log(provider="groq") for _ in range(succeeded)
        ]
        logs += [self._failure_log(provider="groq") for _ in range(failed)]
        await self._boot_contributor(contributor, logs=logs)
        result = await contributor.render_widget("error_rate", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, StatContent)
        return content

    @pytest.mark.asyncio
    async def test_error_rate_below_five_percent_is_success_tone(
        self, contributor: LlmAdminContributor
    ) -> None:
        content = await self._error_rate_test(contributor, succeeded=96, failed=4)
        rate_stat = content.stats[0]
        assert rate_stat.label == "Error Rate"
        assert rate_stat.value == "4.0%"
        assert rate_stat.tone == Tone.SUCCESS

    @pytest.mark.asyncio
    async def test_error_rate_at_five_percent_is_warning_tone(
        self, contributor: LlmAdminContributor
    ) -> None:
        content = await self._error_rate_test(contributor, succeeded=95, failed=5)
        rate_stat = content.stats[0]
        assert rate_stat.value == "5.0%"
        assert rate_stat.tone == Tone.WARNING

    @pytest.mark.asyncio
    async def test_error_rate_below_fifteen_percent_is_warning_tone(
        self, contributor: LlmAdminContributor
    ) -> None:
        content = await self._error_rate_test(contributor, succeeded=90, failed=10)
        rate_stat = content.stats[0]
        assert rate_stat.value == "10.0%"
        assert rate_stat.tone == Tone.WARNING

    @pytest.mark.asyncio
    async def test_error_rate_at_fifteen_percent_is_danger_tone(
        self, contributor: LlmAdminContributor
    ) -> None:
        content = await self._error_rate_test(contributor, succeeded=85, failed=15)
        rate_stat = content.stats[0]
        assert rate_stat.value == "15.0%"
        assert rate_stat.tone == Tone.DANGER

    @pytest.mark.asyncio
    async def test_error_rate_above_fifteen_percent_is_danger_tone(
        self, contributor: LlmAdminContributor
    ) -> None:
        content = await self._error_rate_test(contributor, succeeded=80, failed=20)
        rate_stat = content.stats[0]
        assert rate_stat.value == "20.0%"
        assert rate_stat.tone == Tone.DANGER

    @pytest.mark.asyncio
    async def test_error_rate_carries_errors_over_requests_stat(
        self, contributor: LlmAdminContributor
    ) -> None:
        content = await self._error_rate_test(contributor, succeeded=90, failed=10)
        errors_stat = content.stats[1]
        assert errors_stat.label == "Errors / Requests"
        assert errors_stat.value == "10 / 100"
        assert errors_stat.tone == Tone.DEFAULT

    @pytest.mark.asyncio
    async def test_error_rate_no_logs_returns_message_content(
        self, contributor: LlmAdminContributor
    ) -> None:
        await self._boot_contributor(contributor, logs=[])
        result = await contributor.render_widget("error_rate", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, MessageContent)
        assert content.text == "No inference data yet."

    @pytest.mark.asyncio
    async def test_error_rate_not_booted_returns_message_content(
        self, contributor: LlmAdminContributor
    ) -> None:
        result = await contributor.render_widget("error_rate", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, MessageContent)
        assert content.text == "Contributor not booted."

    @pytest.mark.asyncio
    async def test_token_usage_returns_stat_content(
        self, contributor: LlmAdminContributor
    ) -> None:
        logs = [
            self._success_log(provider="groq", prompt=1_234, completion=2_345),
            self._success_log(provider="gemini", prompt=10, completion=20),
            self._failure_log(provider="groq"),
        ]
        await self._boot_contributor(contributor, logs=logs)
        result = await contributor.render_widget("token_usage", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, StatContent)
        by_label = {stat.label: stat for stat in content.stats}
        assert by_label["Total Tokens"].value == "3,609"
        assert by_label["Prompt Tokens"].value == "1,244"
        assert by_label["Completion Tokens"].value == "2,365"
        for stat in content.stats:
            assert stat.tone == Tone.DEFAULT

    @pytest.mark.asyncio
    async def test_token_usage_no_logs_returns_message_content(
        self, contributor: LlmAdminContributor
    ) -> None:
        await self._boot_contributor(contributor, logs=[])
        result = await contributor.render_widget("token_usage", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, MessageContent)
        assert content.text == "No inference data yet."

    @pytest.mark.asyncio
    async def test_token_usage_not_booted_returns_message_content(
        self, contributor: LlmAdminContributor
    ) -> None:
        result = await contributor.render_widget("token_usage", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, MessageContent)
        assert content.text == "Contributor not booted."

    @pytest.mark.asyncio
    async def test_provider_status_returns_table_content(
        self, contributor: LlmAdminContributor
    ) -> None:
        partial = self._client(HealthStatus.DEGRADED, duration_ms=0.0)
        failing = self._client(HealthStatus.UNHEALTHY, duration_ms=25.0)
        providers = [
            ProviderConfig(name="groq", model="model-a", api_key="k"),
            ProviderConfig(name="gemini", model="model-b", api_key="k"),
            ProviderConfig(name="ollama", model="model-c", base_url="http://x"),
        ]
        router = FakeProviderRouter(
            providers=providers,
            clients={
                "groq": self._client(HealthStatus.HEALTHY, duration_ms=12.5),
                "gemini": partial,
                "ollama": failing,
            },
        )
        await self._boot_contributor(contributor, provider_router=router)
        result = await contributor.render_widget("provider_status", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, TableContent)
        assert content.columns == ("Provider", "Model", "Status", "Latency")
        assert len(content.rows) == 3

        groq, gemini, ollama = content.rows
        assert groq[0].text == "groq"
        assert groq[0].tone == Tone.DEFAULT
        assert groq[2].text == "healthy"
        assert groq[2].tone == Tone.SUCCESS
        assert groq[3].text == "12ms"
        assert gemini[2].text == "degraded"
        assert gemini[2].tone == Tone.WARNING
        assert gemini[3].text == "—"
        assert ollama[2].text == "unhealthy"
        assert ollama[2].tone == Tone.DANGER
        assert ollama[3].text == "25ms"

    @pytest.mark.asyncio
    async def test_provider_status_not_configured_row_is_default_tone(
        self, contributor: LlmAdminContributor
    ) -> None:
        providers = [
            ProviderConfig(name="groq", model="model-a", api_key="k"),
            ProviderConfig(name="gemini", model="model-b", api_key="k", enabled=False),
        ]
        router = FakeProviderRouter(
            providers=providers,
            clients={"groq": self._client(HealthStatus.HEALTHY, duration_ms=1.0)},
        )
        await self._boot_contributor(contributor, provider_router=router)
        result = await contributor.render_widget("provider_status", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, TableContent)
        groq, gemini = content.rows
        assert gemini[2].text == "not configured"
        assert gemini[2].tone == Tone.DEFAULT
        assert gemini[3].text == "—"
        assert groq[2].text == "healthy"

    @pytest.mark.asyncio
    async def test_provider_status_error_row_is_danger_tone(
        self, contributor: LlmAdminContributor
    ) -> None:
        class RaisingClient:
            async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
                raise RuntimeError("boom")

        providers = [
            ProviderConfig(name="groq", model="model-a", api_key="k"),
        ]
        router = FakeProviderRouter(
            providers=providers,
            clients={"groq": RaisingClient()},
        )
        await self._boot_contributor(contributor, provider_router=router)
        result = await contributor.render_widget("provider_status", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, TableContent)
        row = content.rows[0]
        assert row[2].text == "error"
        assert row[2].tone == Tone.DANGER
        assert row[3].text == "—"

    @pytest.mark.asyncio
    async def test_provider_status_no_providers_returns_message_content(
        self, contributor: LlmAdminContributor
    ) -> None:
        router = FakeProviderRouter(providers=[], clients={})
        await self._boot_contributor(contributor, provider_router=router)
        result = await contributor.render_widget("provider_status", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, MessageContent)
        assert content.text == "No providers configured."

    @pytest.mark.asyncio
    async def test_provider_status_not_booted_returns_message_content(
        self, contributor: LlmAdminContributor
    ) -> None:
        result = await contributor.render_widget("provider_status", WidgetParams())
        assert result.is_ok()
        content = result.unwrap().content
        assert isinstance(content, MessageContent)
        assert content.text == "Contributor not booted."

    @staticmethod
    def _success_log(
        provider: str = "groq",
        prompt: int = 100,
        completion: int = 50,
    ) -> InferenceLog:
        return InferenceLog(
            result=InferenceResult(
                provider=provider,
                model="model-a",
                content="ok",
                prompt_tokens=prompt,
                completion_tokens=completion,
            ),
            providers_tried=[provider],
            total_attempts=1,
        )

    @staticmethod
    def _failure_log(provider: str = "groq") -> InferenceLog:
        return InferenceLog(
            error=InferenceError(
                message="boom",
                providers_tried=[provider],
                last_status_code=503,
            ),
            providers_tried=[provider],
            total_attempts=1,
        )

    @staticmethod
    def _client(status: HealthStatus, duration_ms: float = 0.0) -> Any:
        class _FakeClient:
            def __init__(self, s: HealthStatus, d: float) -> None:
                self._status = s
                self._duration = d

            async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
                return HealthCheckResult(
                    component="llm",
                    status=self._status,
                    duration_ms=self._duration,
                )

        return _FakeClient(status, duration_ms)
