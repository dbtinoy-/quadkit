from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
    Tone,
)
from quadkit.contracts.ai.providers import ProviderRegistryProtocol
from quadkit.contracts.core.health import HealthStatus
from quadkit.logging import get_logger

logger = get_logger(__name__)


class LlmProvidersPage:
    """Provider status table for /admin/ai/llm/providers."""

    def __init__(
        self,
        registry: ProviderRegistryProtocol | None = None,
    ) -> None:
        self._registry = registry

    async def handle(self, request: Any) -> PageContent:
        if self._registry is None:
            return PageContent(
                title="LLM Providers",
                body=EmptyContent(
                    title="Provider Registry Unavailable",
                    message="No provider registry is configured. Provider status cannot be displayed.",
                    icon="server",
                ),
            )

        provider_names: list[str] = []
        try:
            provider_names = self._registry.list_providers()
        except Exception:
            provider_names = []

        if not provider_names:
            return PageContent(
                title="LLM Providers",
                body=EmptyContent(
                    title="No Providers",
                    message="No LLM providers are configured.",
                    icon="server",
                ),
            )

        all_models: list[Any] = []
        try:
            all_models = self._registry.list_models()
        except Exception:
            all_models = []

        model_map: dict[str, str] = {}
        for m in all_models:
            if m.provider not in model_map:
                model_map[m.provider] = m.model_id

        provider_data: list[tuple[str, str, str, Tone, str]] = []
        for name in provider_names:
            model_name = model_map.get(name, "\u2014")
            status_label = "unknown"
            status_tone = Tone.WARNING
            latency = "\u2014"

            try:
                client = await self._registry.get_client(name)
            except Exception:
                client = None

            if client is not None:
                try:
                    result = await client.health_check(timeout=5.0)
                    if result.status == HealthStatus.HEALTHY:
                        status_label = "healthy"
                        status_tone = Tone.SUCCESS
                    elif result.status == HealthStatus.DEGRADED:
                        status_label = "degraded"
                        status_tone = Tone.WARNING
                    else:
                        status_label = result.status.value
                        status_tone = Tone.DANGER
                    latency = (
                        f"{result.duration_ms:.0f}ms"
                        if result.duration_ms > 0
                        else "\u2014"
                    )
                except Exception:
                    status_label = "error"
                    status_tone = Tone.DANGER
                    latency = "\u2014"
            else:
                status_label = "not configured"
                status_tone = Tone.WARNING

            provider_data.append((name, model_name, status_label, status_tone, latency))

        rows = tuple(
            (
                TableCell(text=name),
                TableCell(text=model_name),
                TableCell(text=status_label, tone=status_tone),
                TableCell(text=latency),
            )
            for name, model_name, status_label, status_tone, latency in provider_data
        )

        return PageContent(
            title="LLM Providers",
            body=TableContent(
                columns=("Provider", "Model", "Status", "Latency"),
                rows=rows,
            ),
        )
