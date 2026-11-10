"""Convention followed: **Provider pattern** — ``register()`` declares singletons, ``boot()`` resolves contracts, ``health_check()`` reports readiness.

DI wiring for the support-agent demo.

A Provider tells the DI container *what* exists and *how* to build it.
Two-phase lifecycle: ``register()`` binds, ``boot()`` initializes.

Simplest patterns for new users:

- ``container.singleton(Thing, instance=Thing())`` — already built, hand it over
- ``container.singleton(Thing, factory=lambda: ...)`` — build lazily on first resolve
- ``container.singleton(Thing, factory=self._build_thing)`` — async factory for complex wiring

The LLM binding MUST happen in ``register()``: ``AgentsProvider.boot()``
performs a required resolve of ``LLMClientProtocol`` — if it is missing,
the agent subsystem fails to start.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.ai.agents import AgentExecutorProtocol
from quadkit.contracts.ai.llm import LLMClientProtocol
from quadkit.contracts.core.health import (
    HealthCheckResult,
    HealthStatus,
)
from quadkit.di.provider import Provider

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

from support_agent.config import SupportAgentConfig
from support_agent.repository.scripted_llm import ScriptedLLM
from support_agent.services.support_service import SupportAgent, build_support_agent

__all__ = ["AgentSupportProvider"]


class AgentSupportProvider(Provider):
    """Demo-specific DI registrations — your app replaces this.

    Provider lifecycle: register() → boot() → shutdown().
    register() binds services (no I/O); boot() initializes after freeze.
    """

    name = "agent-support"
    config_key: str | None = "support_agent"
    config_model: type | None = SupportAgentConfig

    def __init__(self) -> None:
        super().__init__()
        self._llm = ScriptedLLM()
        self._support: SupportAgent | None = None

    def _get_llm(self) -> ScriptedLLM:
        """Registered eagerly so freeze-time validation sees it."""
        return self._llm

    def _get_support(self) -> SupportAgent:
        """Valid only after boot() has assembled the facade."""
        if self._support is None:
            raise RuntimeError("AgentSupportProvider has not been booted yet")
        return self._support

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind singletons; collaborators resolve only in boot().

        ``container.singleton(Thing, instance=Thing())`` for already-built objects.
        ``container.singleton(Thing, factory=async_fn)`` for services that need
        other services resolved first (async factories run during resolve).
        """
        cfg = self.config or SupportAgentConfig()
        container.singleton(SupportAgentConfig, instance=cfg)

        # --- LLM client: the scripted stand-in ---
        # AgentsProvider.boot() resolves LLMClientProtocol — it MUST be
        # registered before the container freezes.  Both the concrete type
        # (for direct import in tests) and the protocol (for framework
        # resolution) point to the same instance.
        container.singleton(ScriptedLLM, instance=self._llm)
        container.singleton(LLMClientProtocol, factory=self._get_llm)

        # --- SupportAgent facade: assembled in boot() ---
        # The facade needs AgentExecutorProtocol, which AgentsProvider
        # wires during its own boot().  We register a factory that will
        # return the assembled instance after our boot() runs.
        container.singleton(SupportAgent, factory=self._get_support)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Assemble the facade from the executor wired by AgentsModule.

        boot() runs AFTER register() completes and the container is frozen.
        This is where you resolve services and do initialization work
        (seeding data, warming caches, connecting to external services).
        """
        executor = await container.resolve(AgentExecutorProtocol)
        self._support = SupportAgent(
            executor=executor,
            agent=build_support_agent(),
        )

    async def shutdown(self) -> None:
        """Drop the booted facade; framework modules own their collaborators."""
        self._support = None

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report local facade readiness, not external dependency health."""
        cfg = (
            self.config
            if isinstance(self.config, SupportAgentConfig)
            else SupportAgentConfig()
        )
        ready = self._support is not None
        state = "ready" if ready else "not ready"
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY if ready else HealthStatus.UNHEALTHY,
            message=f"{cfg.service_name} provider {state}",
            details={"ready": ready, "scripted_remaining": self._llm.remaining},
        )
