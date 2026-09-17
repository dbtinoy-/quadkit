"""Convention followed: **Provider lifecycle** — ``register()`` declares
singletons (including the controller, as a class binding), ``boot()``
builds the outbound client from typed config and rebinds the wired
controller, ``shutdown()`` closes the client, ``health_check()`` reports
readiness; ``config_key``/``config_model`` wire the typed yaml section
into ``self.config``.

Lifecycle wiring for the AI Assistant demo: the outbound client is the
injection seam — production binds ``HttpAssistantClient`` (from typed
config), tests bind a fake through the same constructor argument.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_assistant.config import AIAssistantConfig
from ai_assistant.controllers.api import ChatController
from ai_assistant.services.client import HttpAssistantClient
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.provider import Provider

if TYPE_CHECKING:
    from ai_assistant.services.client import AssistantClient


class AIAssistantProvider(Provider):
    """Own the assistant client and the controller wiring."""

    name = "ai_assistant"
    config_key: str | None = "ai_assistant"
    config_model: type | None = AIAssistantConfig

    def __init__(self, client: AssistantClient | None = None) -> None:
        super().__init__()
        self._client_override = client
        self._client: HttpAssistantClient | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config
            if isinstance(self.config, AIAssistantConfig)
            else AIAssistantConfig()
        )
        container.singleton(AIAssistantConfig, config)
        container.singleton(ChatController, ChatController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        if self._client_override is not None:
            # Test seam: a fake client bound through the same constructor.
            container.bind(ChatController, ChatController(self._client_override))
            return
        config = await container.resolve(AIAssistantConfig)
        client = HttpAssistantClient(
            base_url=config.gateway_url,
            api_key=config.api_key.get_secret_value(),
            model=config.model,
        )
        self._client = client
        container.bind(ChatController, ChatController(client))

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        ready = self._client is not None or self._client_override is not None
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY if ready else HealthStatus.UNHEALTHY,
            details={
                "demo": "ai-assistant",
                "client_bound": ready,
                "gateway_configured": self._client is not None,
            },
        )


__all__ = ["AIAssistantProvider"]
