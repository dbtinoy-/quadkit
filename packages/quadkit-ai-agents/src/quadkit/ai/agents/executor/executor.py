"""AgentExecutorImpl — runs agents with governance, memory, tracing, and metrics.

The executor is the bridge between the agent framework and the rest
of the Quadkit infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from quadkit.ai.agents.executor.run_support import (
    assemble_history,
    check_input_guard,
    check_output_guard,
    check_request_governance,
    execute_strategy,
    merge_skill_tools,
    persist_conversation,
    resume_session,
    track_cost,
)
from quadkit.ai.agents.executor.streaming import astream as _astream
from quadkit.ai.agents.observability import AgentMetrics, AgentTracer
from quadkit.contracts.ai.agents import (
    AgentError,
    AgentExecutorProtocol,
    AgentProtocol,
    AgentResponse,
    MemoryProtocol,
)
from quadkit.contracts.ai.governance import AIGovernanceProtocol
from quadkit.contracts.ai.guards import GuardPipelineProtocol
from quadkit.contracts.ai.llm import (
    CostEstimatorProtocol,
    LLMClientProtocol,
)
from quadkit.contracts.ai.memory import WorkingMemoryProtocol
from quadkit.contracts.ai.session import SessionManagerProtocol
from quadkit.contracts.ai.skills import (
    SkillExecutorProtocol,
    SkillRegistryProtocol,
)
from quadkit.contracts.events.protocols import EventBusProtocol
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


@dataclass
class AgentObservability:
    """Composite for agent observability components.

    Groups metrics, tracing, and event publishing into a single injectable unit.
    """

    metrics: AgentMetrics | None = None
    tracer: AgentTracer | None = None
    event_bus: EventBusProtocol | None = None


@dataclass
class AgentSafetyInfra:
    """Composite for agent safety infrastructure.

    Groups governance and guard pipeline into a single injectable unit.
    """

    governance: AIGovernanceProtocol | None = None
    guard_pipeline: GuardPipelineProtocol | None = None


class AgentExecutorImpl(AgentExecutorProtocol):
    """Runs an agent with full infrastructure integration.

    Wraps agent strategy execution with:
    1. **Governance** — budget/rate limit checks
    2. **Memory** — conversation history load/save (legacy + working memory)
    3. **Metrics** — execution duration, tokens, tool calls
    4. **Tracing** — distributed spans per execution and tool call
    5. **Events** — domain events for agent lifecycle
    6. **Resilience** — circuit breakers on tool calls (via ToolRegistry)
    7. **Sessions** — stateful multi-turn conversation management
    8. **Skills** — composable skill execution and discovery

    Usage::

        executor = AgentExecutorImpl(llm=llm_client)
        result = await executor.run(
            agent=my_agent,
            message="Where is my order?",
            session_id="session-123",
        )
    """

    def __init__(
        self,
        llm: LLMClientProtocol | None = None,
        memory: MemoryProtocol | None = None,
        working_memory: WorkingMemoryProtocol | None = None,
        session_manager: SessionManagerProtocol | None = None,
        skill_executor: SkillExecutorProtocol | None = None,
        skill_registry: SkillRegistryProtocol | None = None,
        observability: AgentObservability | None = None,
        safety: AgentSafetyInfra | None = None,
        cost_estimator: CostEstimatorProtocol | None = None,
    ) -> None:
        """Initialize the agent executor.

        Args:
            llm: LLM client for agent reasoning.
            memory: Conversation memory for multi-turn sessions (legacy).
            working_memory: Working memory for context assembly.
            session_manager: Session manager for stateful conversations.
            skill_executor: Skill executor for running skills.
            skill_registry: Skill registry for discovering available skills.
            observability: Composite for metrics, tracer, and event bus.
                Defaults to isolated ``AgentMetrics`` and ``AgentTracer``.
            safety: Composite for governance and guard pipeline.
            cost_estimator: Estimates monetary cost of LLM usage for
                governance tracking. When omitted, cost is not tracked
                (no fabricated estimates).
        """
        self._llm = llm
        self._memory = memory
        self._working_memory = working_memory
        self._session_manager = session_manager
        self._skill_executor = skill_executor
        self._skill_registry = skill_registry
        self._cost_estimator = cost_estimator

        self._metrics = (
            observability.metrics
            if observability and observability.metrics
            else AgentMetrics()
        )
        self._tracer = (
            observability.tracer
            if observability and observability.tracer
            else AgentTracer()
        )
        self._event_bus = observability.event_bus if observability else None
        self._governance = safety.governance if safety else None
        self._guard_pipeline = safety.guard_pipeline if safety else None

    async def run(
        self,
        agent: AgentProtocol,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> Result[AgentResponse, AgentError]:
        """Execute an agent with full infrastructure integration.

        Args:
            agent: The agent to execute.
            message: User's input message.
            session_id: Session ID for multi-turn memory.
            user_id: User ID for governance tracking.
            **kwargs: Additional parameters passed to the strategy.

        Returns:
            ``Ok(AgentResponse)`` on success,
            ``Err(AgentError)`` on failure.
        """
        logger.info(
            "agent_execution_start",
            message_length=len(message),
        )

        # Publish start event
        await self._publish_event(
            "AgentExecutionStarted",
            {
                "agent_name": agent.name,
                "session_id": session_id,
                "user_id": user_id,
            },
        )

        # 1. Governance check
        denied = await check_request_governance(self, agent, user_id)
        if denied is not None:
            return denied

        # Agent-level pipeline (AgentBuilder.with_guard_pipeline) wins over the
        # DI-provided one; the DI pipeline remains the standard default.
        agent_pipeline = getattr(agent, "guard_pipeline", None)
        guard_pipeline = (
            agent_pipeline if agent_pipeline is not None else self._guard_pipeline
        )

        # 1.5 Guard check for input
        guard_err, message = await check_input_guard(
            self, agent, guard_pipeline, message, session_id, user_id
        )
        if guard_err is not None:
            return guard_err

        # 2a. Resume or create session
        session_id = await resume_session(self, agent, session_id, user_id)

        # 2b. Assemble context via working memory (preferred) or legacy memory
        history = await assemble_history(self, message, session_id, user_id)

        # 2c. Merge skills as additional tools
        tools: list[Any] = list(agent.tools) if agent.tools else []
        await merge_skill_tools(self, tools)

        # 3. Execute strategy with tracing
        strategy = getattr(agent, "strategy", None)
        if strategy is None:
            from quadkit.ai.agents.strategies.react import ReActStrategy

            strategy = ReActStrategy()

        if self._llm is None:
            logger.error("agent_executor_missing_llm")
            await self._publish_event(
                "AgentExecutionFailed",
                {
                    "agent_name": agent.name,
                    "error": "No LLM client configured",
                    "error_type": "ConfigurationError",
                },
            )
            return Err(AgentError("Agent executor has no LLM client configured"))

        result = await execute_strategy(
            self,
            strategy,
            agent,
            message,
            session_id,
            history,
            tools,
            guard_pipeline,
            kwargs,
        )
        if result.is_err():
            return result

        response = result.unwrap()

        # 3.5 Guard check for output
        out_err, response = await check_output_guard(
            self, agent, guard_pipeline, response, message, session_id, user_id
        )
        if out_err is not None:
            return out_err

        # 4. Record metrics
        self._metrics.record_execution(agent.name, response)
        for tc in response.tool_calls:
            self._metrics.record_tool_call(agent.name, tc)

        # 5. Save to memory (working memory, session, and/or legacy)
        await persist_conversation(self, response, message, session_id, user_id)

        # 6. Track cost (only when a real estimator is configured)
        response = await track_cost(self, response, user_id)

        response = replace(response, session_id=session_id)

        # 7. Publish completion event
        await self._publish_event(
            "AgentExecutionCompleted",
            {
                "agent_name": agent.name,
                "session_id": session_id,
                "steps": response.step_count,
                "tool_calls": response.tool_call_count,
                "total_tokens": response.total_tokens,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_cost": response.total_cost,
                "duration_ms": response.duration_ms,
            },
        )

        logger.info(
            "agent_execution_complete",
            steps=response.step_count,
            tool_calls=response.tool_call_count,
            tokens=response.total_tokens,
            duration_ms=round(response.duration_ms, 2),
        )

        return Ok(response)

    async def astream(
        self,
        agent: AgentProtocol,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ):
        """Stream agent execution events.

        Yields AgentEvent objects as the agent executes, enabling
        real-time monitoring of thoughts, tool calls, and messages.

        Args:
            agent: The agent to execute.
            message: User's input message.
            session_id: Session ID for multi-turn memory.
            user_id: User ID for governance tracking.
            **kwargs: Additional parameters passed to the strategy.

        Yields:
            AgentEvent objects with type, data, and run_id.
        """
        async for event in _astream(
            self,
            agent,
            message,
            session_id,
            user_id,
            **kwargs,
        ):
            yield event

    async def _publish_event(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Publish an agent domain event if EventBusProtocol is available."""
        if not self._event_bus:
            return

        try:
            from quadkit.ai.agents import events as agent_events

            event_cls = getattr(agent_events, event_type, None)
            if event_cls:
                event_obj = event_cls(**data)
                await self._event_bus.publish(event_obj)
        except (ImportError, AttributeError):
            pass
        except Exception as exc:  # noqa: BLE001 — event publishing is best-effort
            logger.debug(
                "event_publish_failed",
                event_type=event_type,
                error_type=type(exc).__name__,
            )
