"""Admin contributor for quadkit-ai-llm — surfaces token usage, provider
status, and error-rate widgets into the Quadkit admin dashboard.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

from quadkit.contracts.admin.contributor import BaseAdminContributor
from quadkit.contracts.admin.errors import (
    AdminError,
    HealthCheckNotFoundError,
    WidgetNotFoundError,
)
from quadkit.contracts.admin.health_payload import HealthCheckPayload
from quadkit.contracts.admin.types import (
    AdminActionDefinition,
    AdminHealthDefinition,
    DashboardWidgetDefinition,
    ManagementPageDefinition,
    NavigationContribution,
    PageCategory,
    WidgetCategory,
    WidgetKind,
    WidgetParams,
    WidgetSize,
    WidgetViewModel,
)
from quadkit.contracts.admin.widget_content import (
    MessageContent,
    Stat,
    StatContent,
    TableCell,
    TableContent,
    Tone,
)
from quadkit.contracts.ai.routing import InferenceLoggerProtocol, LLMRouterProtocol
from quadkit.contracts.core.health import HealthStatus
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol

_WIDGETS: tuple[DashboardWidgetDefinition, ...] = (
    DashboardWidgetDefinition(
        name="token_usage",
        title="Token Usage",
        contributor="ai-llm",
        render_endpoint="/admin/ai-llm/widgets/token_usage",
        size=WidgetSize.LARGE,
        category=WidgetCategory.METRICS,
        view_kind=WidgetKind.STAT,
        description="Prompt and completion token consumption across all providers.",
    ),
    DashboardWidgetDefinition(
        name="provider_status",
        title="Provider Status",
        contributor="ai-llm",
        render_endpoint="/admin/ai-llm/widgets/provider_status",
        size=WidgetSize.SMALL,
        category=WidgetCategory.HEALTH,
        view_kind=WidgetKind.TABLE,
        description="Reachability and latency for each configured LLM provider.",
    ),
    DashboardWidgetDefinition(
        name="error_rate",
        title="Error Rate",
        contributor="ai-llm",
        render_endpoint="/admin/ai-llm/widgets/error_rate",
        size=WidgetSize.SMALL,
        category=WidgetCategory.METRICS,
        view_kind=WidgetKind.STAT,
        description="LLM API error rate over the last rolling window.",
    ),
)

_NAV_ITEMS: tuple[NavigationContribution, ...] = (
    NavigationContribution(
        label="AI",
        url="/admin/ai/llm",
        icon="sparkles",
        group="ai",
        order=50,
        children=(
            NavigationContribution(
                label="Usage",
                url="/admin/ai/llm/usage",
                icon="bar-chart-2",
                group="ai",
                order=10,
            ),
            NavigationContribution(
                label="Providers",
                url="/admin/ai/llm/providers",
                icon="server",
                group="ai",
                order=20,
            ),
        ),
    ),
)

_HEALTH_DEFS: tuple[AdminHealthDefinition, ...] = (
    AdminHealthDefinition(
        name="ai.llm.provider",
        contributor="ai-llm",
        component="LLM Provider",
        check_endpoint="/admin/ai-llm/health/provider",
        description="Verifies the primary LLM provider is reachable and responding.",
    ),
)

_ACTIONS: tuple[AdminActionDefinition, ...] = (
    AdminActionDefinition(
        name="rotate_api_key",
        title="Rotate API Key",
        contributor="ai-llm",
        handler="quadkit.ai.llm.admin.actions:rotate_api_key",
        icon="refresh-cw",
        confirmation_message="This will invalidate the current API key. Are you sure?",
        destructive=True,
        category="security",
    ),
)


class LlmAdminContributor(BaseAdminContributor):
    """Admin contributor for the quadkit-ai-llm package."""

    name = "ai-llm"
    display_name = "AI / LLM"
    group = "ai"
    icon = "sparkles"
    priority = 50

    def __init__(self) -> None:
        self._container: ContainerResolverProtocol | None = None

    async def on_admin_boot(self, container: ContainerResolverProtocol) -> None:
        self._container = container

    def get_dashboard_widgets(self) -> Sequence[DashboardWidgetDefinition]:
        return list(_WIDGETS)

    def get_navigation_items(self) -> Sequence[NavigationContribution]:
        return list(_NAV_ITEMS)

    def get_health_definitions(self) -> Sequence[AdminHealthDefinition]:
        return list(_HEALTH_DEFS)

    def get_actions(self) -> Sequence[AdminActionDefinition]:
        return list(_ACTIONS)

    def get_management_pages(self) -> Sequence[ManagementPageDefinition]:
        return [
            ManagementPageDefinition(
                name="llm_overview",
                title="LLM Overview",
                contributor="ai-llm",
                route_path="/ai/llm",
                handler="quadkit.ai.llm.admin.pages.overview:LlmOverviewPage",
                category=PageCategory.AI,
                icon="sparkles",
                description="Overview of LLM providers, active model, and client status",
                order=10,
            ),
            ManagementPageDefinition(
                name="llm_usage",
                title="LLM Usage",
                contributor="ai-llm",
                route_path="/ai/llm/usage",
                handler="quadkit.ai.llm.admin.pages.usage:LlmUsagePage",
                category=PageCategory.AI,
                icon="bar-chart-2",
                description="Token usage statistics and cost estimates",
                order=20,
            ),
            ManagementPageDefinition(
                name="llm_providers",
                title="LLM Providers",
                contributor="ai-llm",
                route_path="/ai/llm/providers",
                handler="quadkit.ai.llm.admin.pages.providers:LlmProvidersPage",
                category=PageCategory.AI,
                icon="server",
                description="Configured LLM provider status and health",
                order=30,
            ),
        ]

    async def _render_error_rate(self) -> WidgetViewModel:
        if self._container is None:
            return WidgetViewModel(
                content=MessageContent(text="Contributor not booted.")
            )

        logger = await self._container.resolve(InferenceLoggerProtocol)
        logs = await logger.get_recent(limit=500)

        if not logs:
            return WidgetViewModel(
                content=MessageContent(text="No inference data yet.")
            )

        total = len(logs)
        errors = sum(1 for log in logs if not log.succeeded)
        rate = (errors / total * 100) if total > 0 else 0.0

        tone = Tone.SUCCESS if rate < 5 else Tone.WARNING if rate < 15 else Tone.DANGER

        return WidgetViewModel(
            content=StatContent(
                stats=(
                    Stat(
                        label="Error Rate",
                        value=f"{rate:.1f}%",
                        tone=tone,
                    ),
                    Stat(
                        label="Errors / Requests",
                        value=f"{errors} / {total}",
                    ),
                )
            )
        )

    async def _render_provider_status(self) -> WidgetViewModel:
        if self._container is None:
            return WidgetViewModel(
                content=MessageContent(text="Contributor not booted.")
            )

        router = await self._container.resolve(LLMRouterProtocol)

        rows: list[tuple[TableCell, ...]] = []
        for provider_cfg in router._config.providers:
            client = router._clients.get(provider_cfg.name)
            if client is None or not provider_cfg.enabled:
                rows.append(
                    (
                        TableCell(text=provider_cfg.name),
                        TableCell(text=provider_cfg.model),
                        TableCell(text="not configured"),
                        TableCell(text="—"),
                    )
                )
                continue

            try:
                result = await client.health_check(timeout=5.0)
            except Exception:
                rows.append(
                    (
                        TableCell(text=provider_cfg.name),
                        TableCell(text=provider_cfg.model),
                        TableCell(text="error", tone=Tone.DANGER),
                        TableCell(text="—"),
                    )
                )
                continue

            if result.status == HealthStatus.HEALTHY:
                status_label = "healthy"
                status_tone = Tone.SUCCESS
            elif result.status == HealthStatus.DEGRADED:
                status_label = "degraded"
                status_tone = Tone.WARNING
            else:
                status_label = result.status.value
                status_tone = Tone.DANGER

            latency = f"{result.duration_ms:.0f}ms" if result.duration_ms > 0 else "—"

            rows.append(
                (
                    TableCell(text=provider_cfg.name),
                    TableCell(text=provider_cfg.model),
                    TableCell(text=status_label, tone=status_tone),
                    TableCell(text=latency),
                )
            )

        if not rows:
            return WidgetViewModel(
                content=MessageContent(text="No providers configured.")
            )

        return WidgetViewModel(
            content=TableContent(
                columns=("Provider", "Model", "Status", "Latency"),
                rows=tuple(rows),
            )
        )

    async def _render_token_usage(self) -> WidgetViewModel:
        if self._container is None:
            return WidgetViewModel(
                content=MessageContent(text="Contributor not booted.")
            )

        logger = await self._container.resolve(InferenceLoggerProtocol)
        logs = await logger.get_recent(limit=1000)

        by_provider: dict[str, dict[str, int]] = {}
        for log in logs:
            if log.result is None:
                continue
            provider = log.result.provider
            if provider not in by_provider:
                by_provider[provider] = {"prompt": 0, "completion": 0, "count": 0}
            by_provider[provider]["prompt"] += log.result.prompt_tokens
            by_provider[provider]["completion"] += log.result.completion_tokens
            by_provider[provider]["count"] += 1

        if not by_provider:
            return WidgetViewModel(
                content=MessageContent(text="No inference data yet.")
            )

        prompt_total = sum(v["prompt"] for v in by_provider.values())
        completion_total = sum(v["completion"] for v in by_provider.values())
        total = prompt_total + completion_total

        return WidgetViewModel(
            content=StatContent(
                stats=(
                    Stat(label="Total Tokens", value=f"{total:,}"),
                    Stat(label="Prompt Tokens", value=f"{prompt_total:,}"),
                    Stat(label="Completion Tokens", value=f"{completion_total:,}"),
                )
            )
        )

    async def render_health_check(
        self,
        check_name: str,
    ) -> Result[HealthCheckPayload, AdminError]:
        """Aggregate health across all enabled LLM providers.

        Delegates to ``LLMRouterProtocol.health_probe()`` — the same
        ``client.health_check()`` calls the provider-status widget makes,
        aggregated at the protocol boundary (no private router attrs).

        Args:
            check_name: Name of the health check requested.

        Returns:
            Ok(HealthCheckPayload) — HEALTHY when at least one enabled
            provider passes its health probe, UNHEALTHY when none does.
            Err(HealthCheckNotFoundError) for unknown check names or when
            the contributor was never booted.
        """
        if check_name != "provider" or self._container is None:
            not_found: Result[HealthCheckPayload, AdminError] = cast(
                "Result[HealthCheckPayload, AdminError]",
                Err(HealthCheckNotFoundError(self.name, check_name)),
            )
            return not_found

        router = await self._container.resolve(LLMRouterProtocol)
        result = await router.health_probe()
        if result.is_ok():
            return Ok(
                HealthCheckPayload(
                    status=HealthStatus.HEALTHY,
                    component="LLM Provider",
                )
            )
        return Ok(
            HealthCheckPayload(
                status=HealthStatus.UNHEALTHY,
                component="LLM Provider",
                detail="no healthy provider",
            )
        )

    async def render_widget(
        self,
        widget_name: str,
        params: WidgetParams,
        resolver: ContainerResolverProtocol | None = None,
    ) -> Result[WidgetViewModel, AdminError]:
        widget_names = {w.name for w in _WIDGETS}
        if widget_name not in widget_names:
            return cast(
                "Result[WidgetViewModel, AdminError]",
                Err(WidgetNotFoundError(self.name, widget_name)),
            )

        if widget_name == "token_usage":
            vm = await self._render_token_usage()
            return Ok(vm)

        if widget_name == "provider_status":
            vm = await self._render_provider_status()
            return Ok(vm)

        if widget_name == "error_rate":
            vm = await self._render_error_rate()
            return Ok(vm)

        return cast(
            "Result[WidgetViewModel, AdminError]",
            Err(WidgetNotFoundError(self.name, widget_name)),
        )


__all__ = ["LlmAdminContributor"]
