from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import Stat, StatContent
from quadkit.contracts.ai.llm import LLMClientProtocol
from quadkit.contracts.ai.providers import ProviderRegistryProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class LlmOverviewPage:
    """Dashboard overview for /admin/ai/llm."""

    def __init__(
        self,
        registry: ProviderRegistryProtocol | None = None,
        client: LLMClientProtocol | None = None,
    ) -> None:
        self._registry = registry
        self._client = client

    async def handle(self, request: Any) -> PageContent:
        provider_count: str | int = "N/A"
        active_model: str = "N/A"
        client_status: str = "N/A"

        if self._registry is not None:
            try:
                providers = self._registry.list_providers()
                provider_count = len(providers)
            except Exception:
                provider_count = "N/A"

            try:
                models = self._registry.list_models()
                active_model = models[0].display_name if models else "None"
            except Exception:
                active_model = "N/A"

        if self._client is not None:
            try:
                result = await self._client.health_check()
                client_status = f"{result.duration_ms:.0f}ms"
            except Exception:
                client_status = "error"

        return PageContent(
            title="AI / LLM",
            body=StatContent(
                stats=(
                    Stat(
                        label="Providers",
                        value=str(provider_count),
                        icon="server",
                    ),
                    Stat(
                        label="Active Model",
                        value=str(active_model),
                        icon="cpu",
                    ),
                    Stat(
                        label="Client Latency",
                        value=str(client_status),
                        icon="activity",
                    ),
                )
            ),
        )
