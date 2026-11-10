"""AgentsProvider — registers agent infrastructure with full integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.ai.agents.config import AgentConfig
from quadkit.ai.agents.speculation.draft_verify import DraftVerifyExecutor
from quadkit.ai.agents.speculation.predictor import KeywordToolCallPredictor
from quadkit.ai.agents.speculation.prefetcher import SpeculativeToolPreFetcher
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.provider import Provider
from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


class AgentsProvider(Provider):
    """Registers agent infrastructure with full Quadkit integration.

    Registers:
    - ``ToolRegistry`` — tool storage with module visibility
    - ``AgentExecutorImpl`` — execution engine with governance, memory,
      metrics, tracing, and events
    - ``AgentMetrics`` — agent metrics collector
    - ``AgentTracer`` — agent distributed tracing

    Auto-discovers at boot:
    - ``LLMClientProtocol`` (required)
    - ``AIGovernanceManager`` (optional — budget/rate control)
    - ``ConversationBuffer`` (optional — multi-turn memory)
    - ``MetricsRecorderProtocol`` (optional — from quadkit-monitor)
    - ``TracerProtocol`` (optional — from quadkit-monitor)
    - ``EventBusProtocol`` (optional — from quadkit-events)
    - ``CompiledModuleGraph`` (optional — for tool visibility)
    """

    name = "ai-agents"
    priority = ProviderPriority.DOMAIN
    config_key: str | None = "ai_agents"
    config_model: type | None = AgentConfig

    def __init__(
        self,
        config: AgentConfig | None = None,
        enable_multi_agent: bool = False,
    ) -> None:
        """Initialise the provider.

        Args:
            config: Agent configuration. Defaults to ``AgentConfig()``.
            enable_multi_agent: Enable multi-agent orchestration support.
        """
        super().__init__()
        self._requested_config = config
        self._config = config or AgentConfig()
        self.enable_multi_agent = enable_multi_agent

    @classmethod
    def from_config(cls, config: AgentConfig, **context: object) -> AgentsProvider:
        """Create an AgentsProvider from the resolved config."""
        return cls(config=config)

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register agent infrastructure."""
        from quadkit.contracts.ai import (
            AgentExecutorProtocol,
            ToolRegistryProtocol,
        )

        self._config = self._requested_config or self._config or AgentConfig()
        container.singleton(AgentConfig, self._config)

        if not self._config.enabled:
            logger.info("agents_disabled", reason="AgentConfig.enabled=False")
            return

        from quadkit.ai.agents.executor.executor import (
            AgentExecutorImpl,
        )
        from quadkit.ai.agents.observability import AgentMetrics, AgentTracer
        from quadkit.ai.agents.tools.registry import ToolRegistryImpl

        # Register a shared registry instance for both tokens so boot-time
        # mutations (module graph wiring) are visible from protocol resolution.
        tool_registry = ToolRegistryImpl()
        container.singleton(ToolRegistryImpl, tool_registry)
        container.singleton(ToolRegistryProtocol, tool_registry)
        container.singleton(AgentExecutorImpl, AgentExecutorImpl)
        container.singleton(AgentExecutorProtocol, AgentExecutorImpl)
        container.singleton(AgentMetrics, AgentMetrics)
        container.singleton(AgentTracer, AgentTracer)
        from quadkit.ai.agents.strategies.strategy_registry import (
            AgentStrategyRegistry,
        )

        strategy_registry = AgentStrategyRegistry.with_defaults()
        container.singleton(AgentStrategyRegistry, strategy_registry)

        container.singleton(KeywordToolCallPredictor, KeywordToolCallPredictor)
        container.singleton(SpeculativeToolPreFetcher, SpeculativeToolPreFetcher)
        container.singleton(DraftVerifyExecutor, DraftVerifyExecutor)

        await self._discover_strategies(container)

        logger.info("agents_provider_registered")

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Boot agent infrastructure — resolve all integrations."""
        if not self._config.enabled:
            return

        from quadkit.ai.agents.executor.executor import (
            AgentExecutorImpl,
            AgentObservability,
            AgentSafetyInfra,
        )
        from quadkit.ai.agents.observability import AgentMetrics, AgentTracer
        from quadkit.ai.agents.tools.registry import ToolRegistryImpl
        from quadkit.contracts.ai import AgentExecutorProtocol
        from quadkit.contracts.ai.llm import LLMClientProtocol

        # Required: LLM client
        resolver = cast("Any", container)

        llm = await resolver.resolve(LLMClientProtocol)

        # Optional: governance
        governance = None
        try:
            from quadkit.contracts.ai.governance import AIGovernanceProtocol

            governance = await resolver.resolve_optional(AIGovernanceProtocol)
            logger.debug("agents_governance_available")
        except Exception:  # noqa: BLE001 — optional governance registration degrades
            logger.debug("agents_governance_not_available")

        # Optional: guard pipeline (from the optional provider)
        guard_pipeline = None
        try:
            from quadkit.contracts.ai.guards import GuardPipelineProtocol

            guard_pipeline = await resolver.resolve_optional(GuardPipelineProtocol)
            logger.debug("agents_guard_pipeline_available")
        except Exception:  # noqa: BLE001 — optional guard pipeline registration degrades
            logger.debug("agents_guard_pipeline_not_available")

        # Optional: memory
        memory = None
        try:
            from quadkit.contracts.ai.memory import WorkingMemoryProtocol

            memory = await resolver.resolve_optional(WorkingMemoryProtocol)
            logger.debug("agents_memory_initialized")
        except Exception:  # noqa: BLE001 — optional dependency resolution degrades
            logger.debug("agents_memory_not_available")

        # Optional: metrics
        metrics_recorder = None
        try:
            from quadkit.contracts.observability.metrics import MetricsRecorderProtocol

            metrics_recorder = await resolver.resolve_optional(MetricsRecorderProtocol)
            logger.debug("agents_metrics_available")
        except Exception:  # noqa: BLE001 — optional metrics registration degrades
            logger.debug("agents_metrics_not_available")

        agent_metrics = AgentMetrics(recorder=metrics_recorder)
        if hasattr(resolver, "bind"):
            resolver.bind(AgentMetrics, agent_metrics)

        # Optional: tracing
        tracer = None
        try:
            from quadkit.contracts.observability.tracing import TracerProtocol

            tracer = await resolver.resolve_optional(TracerProtocol)
            logger.debug("agents_tracing_available")
        except Exception:  # noqa: BLE001 — optional tracing registration degrades
            logger.debug("agents_tracing_not_available")

        agent_tracer = AgentTracer(tracer=tracer)
        if hasattr(resolver, "bind"):
            resolver.bind(AgentTracer, agent_tracer)

        # Optional: event bus
        event_bus = None
        try:
            from quadkit.contracts.events.protocols import EventBusProtocol

            event_bus = await resolver.resolve_optional(EventBusProtocol)
            logger.debug("agents_event_bus_available")
        except Exception:  # noqa: BLE001 — optional event bus registration degrades
            logger.debug("agents_event_bus_not_available")

        # Optional: module graph for tool visibility
        tool_registry = await resolver.resolve(ToolRegistryImpl)
        try:
            from quadkit.di.module import CompiledModuleGraph

            graph = await resolver.resolve_optional(CompiledModuleGraph)
            maybe_set = tool_registry.set_module_graph(graph)
            if hasattr(maybe_set, "__await__"):
                await maybe_set
            logger.debug("agents_module_graph_available")
        except Exception:  # noqa: BLE001 — optional module graph registration degrades
            logger.debug("agents_module_graph_not_available")

        # Optional: working memory (from the optional provider)
        working_memory = None
        try:
            from quadkit.contracts.ai.memory import WorkingMemoryProtocol

            working_memory = await resolver.resolve_optional(WorkingMemoryProtocol)
            logger.debug("agents_working_memory_available")
        except Exception:  # noqa: BLE001 — optional dependency resolution degrades
            logger.debug("agents_working_memory_not_available")

        # Optional: session manager (from the optional provider)
        session_manager = None
        try:
            from quadkit.contracts.ai.session import SessionManagerProtocol

            session_manager = await resolver.resolve_optional(SessionManagerProtocol)
            logger.debug("agents_session_manager_available")
        except Exception:  # noqa: BLE001 — optional dependency resolution degrades
            logger.debug("agents_session_manager_not_available")

        # Optional: skill executor (from the optional provider)
        skill_executor = None
        try:
            from quadkit.contracts.ai.skills import SkillExecutorProtocol

            skill_executor = await resolver.resolve_optional(SkillExecutorProtocol)
            logger.debug("agents_skill_executor_available")
        except Exception:  # noqa: BLE001 — optional dependency resolution degrades
            logger.debug("agents_skill_executor_not_available")

        # Optional: skill registry (from the optional provider)
        skill_registry = None
        try:
            from quadkit.contracts.ai.skills import SkillRegistryProtocol

            skill_registry = await resolver.resolve_optional(SkillRegistryProtocol)
            logger.debug("agents_skill_registry_available")
        except Exception:  # noqa: BLE001 — optional dependency resolution degrades
            logger.debug("agents_skill_registry_not_available")

        # Create executor with all integrations
        executor = AgentExecutorImpl(
            llm=llm,
            memory=memory,
            observability=AgentObservability(
                metrics=agent_metrics,
                tracer=agent_tracer,
                event_bus=event_bus,
            ),
            safety=AgentSafetyInfra(
                governance=governance,
                guard_pipeline=guard_pipeline,
            ),
            working_memory=working_memory,
            session_manager=session_manager,
            skill_executor=skill_executor,
            skill_registry=skill_registry,
        )

        if hasattr(resolver, "bind"):
            resolver.bind(AgentExecutorImpl, executor)
            resolver.bind(AgentExecutorProtocol, executor)

        logger.info(
            "agents_provider_booted",
            governance=governance is not None,
            memory=memory is not None,
            metrics=metrics_recorder is not None,
            tracing=tracer is not None,
            events=event_bus is not None,
            working_memory=working_memory is not None,
            session_manager=session_manager is not None,
            skill_executor=skill_executor is not None,
            skill_registry=skill_registry is not None,
            guard_pipeline=guard_pipeline is not None,
        )

    async def _discover_strategies(self, container: ContainerRegistrarProtocol) -> None:
        """Auto-discover agent strategy providers via entry-points."""
        import importlib.metadata as _meta

        from quadkit.di.provider import Provider as _Provider

        eps = _meta.entry_points(group="quadkit.agent.strategies")
        for ep in eps:
            try:
                candidate = ep.load()
            except Exception as exc:  # noqa: BLE001 — optional feature init degrades on any error
                logger.warning(
                    "agent_strategy_ep_load_failed",
                    error_type=type(exc).__name__,
                )
                continue
            if isinstance(candidate, type) and issubclass(candidate, _Provider):
                await candidate().register(container)
                logger.info("agent_strategy_ep_loaded")
            else:
                logger.debug("agent_strategy_ep_skipped")

    async def shutdown(self) -> None:
        """Shutdown agent infrastructure."""
        logger.info("agents_provider_shutdown")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Agent system health check."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
        )
