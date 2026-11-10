"""Convention followed: **Provider lifecycle** — ``register()`` binds the
``LLMClientProtocol`` implementation, ``LLMCache``, and controller class;
``boot()`` resolves ``LLMClientProtocol`` and wires the extraction service.
"""

from __future__ import annotations

from llm_side.config import LlmSideConfig
from llm_side.controllers.api import TicketExtractionController
from llm_side.services.deterministic_llm import DeterministicExtractionLLMClient
from llm_side.services.extractor import TicketExtractionService
from quadkit.ai.llm import LLMCache
from quadkit.contracts.ai import LLMClientProtocol
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.provider import Provider


class LlmSideProvider(Provider):
    """Bind the offline ``LLMClientProtocol``, ``LLMCache``, and service."""

    name = "llm_side"
    config_key: str | None = "llm_side"
    config_model: type | None = LlmSideConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config
            if isinstance(self.config, LlmSideConfig)
            else LlmSideConfig()
        )
        container.singleton(LlmSideConfig, config)
        container.singleton(LLMCache, LLMCache(ttl=config.cache_ttl))
        container.singleton(TicketExtractionController, TicketExtractionController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        config = await container.resolve(LlmSideConfig)
        llm: LLMClientProtocol = DeterministicExtractionLLMClient(model=config.model)
        container.bind(LLMClientProtocol, llm)
        cache = await container.resolve(LLMCache)
        service = TicketExtractionService(
            llm=llm,
            cache=cache,
            model=config.model,
            cache_ttl=config.cache_ttl,
        )
        container.bind(
            TicketExtractionController,
            TicketExtractionController(service=service),
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        _ = timeout
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"demo": "llm-structured"},
        )


__all__ = ["LlmSideProvider"]
