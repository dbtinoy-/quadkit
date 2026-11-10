from __future__ import annotations

from typing import Any

import pytest

from quadkit.ai.llm.admin.contributor import LlmAdminContributor
from quadkit.ai.llm.routing import InferenceError
from quadkit.ai.llm.routing.config import LLMConfig, ProviderConfig
from quadkit.contracts.admin.errors import (
    HealthCheckNotFoundError,
    WidgetNotFoundError,
)
from quadkit.contracts.admin.health_payload import HealthCheckPayload
from quadkit.contracts.admin.types import WidgetParams, WidgetViewModel
from quadkit.contracts.ai.routing import (
    InferenceLoggerProtocol,
    LLMRouterProtocol,
)
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.result import Err, Ok, Result


class FakeRouter:
    def __init__(
        self,
        *,
        healthy: bool,
    ) -> None:
        if healthy:
            self._outcome: Result[Any, InferenceError] = Ok(object())
        else:
            self._outcome = Err(
                InferenceError(
                    message="no healthy provider",
                    providers_tried=["fake"],
                    last_status_code=503,
                )
            )

    async def health_probe(self) -> Result[Any, InferenceError]:
        return self._outcome


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


class TestLlmAdminRegistration:
    @pytest.fixture
    def contributor(self) -> LlmAdminContributor:
        return LlmAdminContributor()

    @pytest.mark.asyncio
    async def test_render_widget_token_usage(
        self, contributor: LlmAdminContributor
    ) -> None:
        result = await contributor.render_widget("token_usage", WidgetParams())
        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm, WidgetViewModel)

    @pytest.mark.asyncio
    async def test_unknown_widget_returns_not_found(
        self, contributor: LlmAdminContributor
    ) -> None:
        result = await contributor.render_widget("nonexistent", WidgetParams())
        assert result.is_err()
        assert isinstance(result.unwrap_err(), WidgetNotFoundError)

    def test_get_dashboard_widgets_returns_three(
        self, contributor: LlmAdminContributor
    ) -> None:
        widgets = contributor.get_dashboard_widgets()
        assert len(widgets) == 3
        widget_names = {w.name for w in widgets}
        assert widget_names == {"token_usage", "provider_status", "error_rate"}

    @pytest.mark.asyncio
    async def test_render_health_check_returns_healthy_when_all_providers_healthy(
        self,
    ) -> None:
        contributor = LlmAdminContributor()
        await contributor.on_admin_boot(FakeContainer(router=FakeRouter(healthy=True)))

        result = await contributor.render_health_check("provider")

        assert result.is_ok()
        payload = result.unwrap()
        assert isinstance(payload, HealthCheckPayload)
        assert payload.status == HealthStatus.HEALTHY
        assert payload.component == "LLM Provider"

    @pytest.mark.asyncio
    async def test_render_health_check_returns_healthy_when_at_least_one_provider_healthy(
        self,
    ) -> None:
        contributor = LlmAdminContributor()
        await contributor.on_admin_boot(FakeContainer(router=FakeRouter(healthy=True)))

        result = await contributor.render_health_check("provider")

        assert result.is_ok()
        payload = result.unwrap()
        assert payload.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_render_health_check_returns_unhealthy_when_no_provider_healthy(
        self,
    ) -> None:
        contributor = LlmAdminContributor()
        await contributor.on_admin_boot(FakeContainer(router=FakeRouter(healthy=False)))

        result = await contributor.render_health_check("provider")

        assert result.is_ok()
        payload = result.unwrap()
        assert payload.status == HealthStatus.UNHEALTHY
        assert payload.component == "LLM Provider"
        assert payload.detail == "no healthy provider"

    @pytest.mark.asyncio
    async def test_render_health_check_returns_not_found_for_unknown_check_name(
        self,
    ) -> None:
        result = await LlmAdminContributor().render_health_check("something_else")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), HealthCheckNotFoundError)
