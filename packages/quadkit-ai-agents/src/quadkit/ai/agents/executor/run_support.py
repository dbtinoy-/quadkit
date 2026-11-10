"""Private pipeline-stage helpers for :class:`AgentExecutorImpl.run`.

Each helper mirrors one numbered stage of the run pipeline and receives the
executor instance as its first argument, mirroring the module-function
pattern used by ``executor.streaming``. Behavior, log events, and error
mapping are identical to the inlined originals.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from quadkit.ai.agents.exceptions import BudgetExceededError
from quadkit.contracts.ai.agents import AgentError, AgentResponse
from quadkit.contracts.ai.llm import ChatMessage, Role
from quadkit.logging import get_logger, safe_error_type
from quadkit.result import Err, Result

if TYPE_CHECKING:
    from quadkit.ai.agents.executor.executor import AgentExecutorImpl
    from quadkit.contracts.ai.agents import AgentProtocol
    from quadkit.contracts.ai.guards import GuardPipelineProtocol

logger = get_logger(__name__)


async def check_request_governance(
    self: AgentExecutorImpl,
    agent: AgentProtocol,
    user_id: str | None,
) -> Result[AgentResponse, AgentError] | None:
    """Check governance; ``Err(BudgetExceededError)`` on denial, else ``None``."""
    if not self._governance:
        return None

    model = getattr(self._llm, "model", "unknown")
    provider = getattr(self._llm, "provider", "unknown")
    try:
        allowed = await self._governance.check_request(
            model=model,
            provider=provider,
            user_id=user_id,
        )
        if not allowed:
            self._metrics.record_governance_denied(agent.name)
            logger.warning("agent_governance_denied")
            await self._publish_event(
                "AgentExecutionFailed",
                {
                    "agent_name": agent.name,
                    "error": "Governance denied",
                    "error_type": "BudgetExceededError",
                },
            )
            return Err(
                BudgetExceededError(
                    "Agent request denied by governance policy",
                )
            )
    except Exception as exc:  # noqa: BLE001 — governance check is best-effort
        logger.warning(
            "governance_check_failed",
            error_type=safe_error_type(exc),
        )

    return None


async def check_input_guard(
    self: AgentExecutorImpl,
    agent: AgentProtocol,
    guard_pipeline: GuardPipelineProtocol | None,
    message: str,
    session_id: str | None,
    user_id: str | None,
) -> tuple[Result[AgentResponse, AgentError] | None, str]:
    """Run input guards; returns ``(short_circuit_err_or_none, message)``."""
    if not guard_pipeline:
        return None, message

    try:
        guard_res = await guard_pipeline.check_input(
            content=message,
            metadata={"session_id": session_id, "user_id": user_id},
        )
        if not guard_res.is_ok():
            guard_error = guard_res.unwrap_err()
            error_type = safe_error_type(guard_error)
            logger.warning(
                "input_guard_evaluation_failed",
                error_type=error_type,
            )
            return (
                Err(
                    AgentError(
                        "Input safety checks are temporarily unavailable.",
                        details={"error_type": error_type},
                    ),
                ),
                message,
            )

        agg = guard_res.unwrap()
        action = str(getattr(agg, "action", "pass"))
        blocked = bool(getattr(agg, "blocked", False)) or action == "block"
        if blocked:
            return (
                Err(AgentError("Input blocked by security guards")),
                message,
            )
        if action == "redact":
            safe_message = getattr(agg, "final_content", None)
            if not isinstance(safe_message, str):
                logger.warning("input_guard_redaction_missing_content")
                return (
                    Err(
                        AgentError(
                            "Input could not be safely redacted.",
                            details={"error_type": "MissingRedactedContent"},
                        ),
                    ),
                    message,
                )
            return None, safe_message
        if action not in {"pass", "warn"}:
            logger.warning("input_guard_unknown_action")
            return (
                Err(
                    AgentError(
                        "Input safety checks are temporarily unavailable.",
                        details={"error_type": "UnknownGuardAction"},
                    ),
                ),
                message,
            )

        safe_message = getattr(agg, "final_content", message)
        if not isinstance(safe_message, str):
            return (
                Err(
                    AgentError(
                        "Input safety checks are temporarily unavailable.",
                        details={"error_type": "InvalidGuardContent"},
                    ),
                ),
                message,
            )
        return None, safe_message
    except Exception as exc:  # noqa: BLE001 - input guard failures fail closed
        error_type = safe_error_type(exc)
        logger.error(
            "input_guard_evaluation_failed",
            error_type=error_type,
        )
        return (
            Err(
                AgentError(
                    "Input safety checks are temporarily unavailable.",
                    details={"error_type": error_type},
                ),
            ),
            message,
        )


async def resume_session(
    self: AgentExecutorImpl,
    agent: AgentProtocol,
    session_id: str | None,
    user_id: str | None,
) -> str | None:
    """Resume or create the session; returns the effective session ID."""
    if not (self._session_manager and session_id):
        return session_id

    try:
        session_state = await self._session_manager.resume(session_id)
        if session_state is None and user_id:
            session_state = await self._session_manager.create(
                user_id=user_id,
                metadata={"agent": agent.name},
            )
            session_id = session_state.session_id
        logger.debug(
            "session_loaded",
            turns=session_state.turn_count if session_state else 0,
        )
    except Exception as exc:  # noqa: BLE001 — session load degrades on any error
        logger.warning("session_load_failed", error_type=safe_error_type(exc))
    return session_id


async def assemble_history(
    self: AgentExecutorImpl,
    message: str,
    session_id: str | None,
    user_id: str | None,
) -> list[ChatMessage]:
    """Assemble context via working memory (preferred) or legacy memory."""
    history: list[ChatMessage] = []
    if self._working_memory:
        try:
            entries = await self._working_memory.assemble(
                query=message,
                token_budget=4096,
                owner_id=user_id or session_id or "anonymous",
                session_id=session_id,
            )
            history = [
                ChatMessage(role=Role(e.role), content=e.content) for e in entries
            ]
        except Exception as exc:  # noqa: BLE001 — working memory assembly degrades on any error
            logger.warning(
                "working_memory_assemble_failed",
                error_type=safe_error_type(exc),
            )
    elif self._memory and session_id:
        try:
            if hasattr(self._memory, "get_messages"):
                msgs = await self._memory.get_messages()
                history = [
                    ChatMessage(role=Role(m.role), content=m.content) for m in msgs
                ]
        except Exception as exc:  # noqa: BLE001 — memory load degrades on any error
            logger.warning("memory_load_failed", error_type=safe_error_type(exc))
    return history


async def merge_skill_tools(
    self: AgentExecutorImpl,
    tools: list[Any],
) -> None:
    """Merge skill schemas into ``tools`` in place."""
    if not self._skill_registry:
        return
    try:
        skill_schemas = self._skill_registry.get_schemas()
        tools.extend(skill_schemas)
    except Exception as exc:  # noqa: BLE001 — skill registry merge degrades on any error
        logger.warning("skill_registry_merge_failed", error_type=safe_error_type(exc))


async def execute_strategy(
    self: AgentExecutorImpl,
    strategy: Any,
    agent: AgentProtocol,
    message: str,
    session_id: str | None,
    history: list[ChatMessage],
    tools: list[Any],
    guard_pipeline: GuardPipelineProtocol | None,
    kwargs: dict[str, Any],
) -> Result[AgentResponse, AgentError]:
    """Execute the strategy under tracing, normalizing failures to Err."""
    from quadkit.ai.agents.strategies.guard_hook import (
        ToolObservationBlockedError,
        ToolObservationGuardError,
    )

    try:
        async with self._tracer.trace_execution(
            agent.name,
            message,
            session_id,
        ) as span:
            strategy_history = [{"role": m.role, "content": m.content} for m in history]

            strategy_kwargs = dict(kwargs)
            strategy_kwargs.pop("tool_registry", None)  # passed explicitly below
            result = await strategy.execute(
                message=message,
                tools=tools,
                history=strategy_history,
                llm=self._llm,
                system_prompt=agent.system_prompt,
                temperature=getattr(agent, "temperature", 0.7),
                tool_registry=kwargs.get("tool_registry"),
                memory=getattr(agent, "memory", None),
                guard_pipeline=guard_pipeline,
                **strategy_kwargs,
            )

            if span and hasattr(result, "is_ok"):
                if result.is_ok():
                    response = result.unwrap()
                    if hasattr(span, "set_attribute"):
                        span.set_attribute("agent.steps", response.step_count)
                        span.set_attribute("agent.tokens", response.total_tokens)
                        span.set_attribute("agent.tool_calls", response.tool_call_count)

    except (ToolObservationBlockedError, ToolObservationGuardError) as exc:
        error_type = safe_error_type(exc)
        is_blocked = isinstance(exc, ToolObservationBlockedError)
        message_text = (
            "Tool observation blocked by guards"
            if is_blocked
            else "Tool observation guard evaluation failed"
        )
        logger.warning(
            "agent.guard_blocked_observation",
            error_type=error_type,
        )
        self._metrics.record_error(agent.name, error_type)
        await self._publish_event(
            "AgentExecutionFailed",
            {
                "agent_name": agent.name,
                "error": message_text,
                "error_type": error_type,
            },
        )
        return Err(
            AgentError(message_text, details={"error_type": error_type}),
        )

    except Exception as exc:  # noqa: BLE001 - strategy failures are logged, never raised
        error_type = safe_error_type(exc)
        logger.error(
            "strategy_execution_failed",
            error_type=error_type,
        )
        self._metrics.record_error(agent.name, error_type)
        await self._publish_event(
            "AgentExecutionFailed",
            {
                "agent_name": agent.name,
                "error": "Agent strategy failed",
                "error_type": error_type,
            },
        )
        return Err(
            AgentError(
                "Agent strategy failed",
                details={"error_type": error_type},
            ),
        )

    if not result.is_ok():
        error = result.unwrap_err()
        error_type = safe_error_type(error)
        self._metrics.record_error(agent.name, error_type)
        await self._publish_event(
            "AgentExecutionFailed",
            {
                "agent_name": agent.name,
                "error": "Agent strategy failed",
                "error_type": error_type,
            },
        )
        return Err(
            AgentError(
                "Agent strategy failed",
                details={"error_type": error_type},
            ),
        )

    return result


async def check_output_guard(
    self: AgentExecutorImpl,
    agent: AgentProtocol,
    guard_pipeline: GuardPipelineProtocol | None,
    response: AgentResponse,
    original_input: str,
    session_id: str | None,
    user_id: str | None,
) -> tuple[Result[AgentResponse, AgentError] | None, AgentResponse]:
    """Run output guards; returns ``(short_circuit_err_or_none, response)``."""
    if not guard_pipeline:
        return None, response

    try:
        out_guard_res = await guard_pipeline.check_output(
            content=response.message,
            original_input=original_input,
            metadata={"session_id": session_id, "user_id": user_id},
        )
        if not out_guard_res.is_ok():
            guard_error = out_guard_res.unwrap_err()
            error_type = safe_error_type(guard_error)
            logger.warning(
                "output_guard_evaluation_failed",
                error_type=error_type,
            )
            return (
                Err(
                    AgentError(
                        "Output safety checks are temporarily unavailable.",
                        details={"error_type": error_type},
                    ),
                ),
                response,
            )

        agg = out_guard_res.unwrap()
        action = str(getattr(agg, "action", "pass"))
        blocked = bool(getattr(agg, "blocked", False)) or action == "block"
        if blocked:
            return Err(AgentError("Output blocked by security guards")), response

        if action == "redact":
            safe_output = getattr(agg, "final_content", None)
            if not isinstance(safe_output, str):
                logger.warning("output_guard_redaction_missing_content")
                return (
                    Err(
                        AgentError(
                            "Output could not be safely redacted.",
                            details={"error_type": "MissingRedactedContent"},
                        ),
                    ),
                    response,
                )
        elif action in {"pass", "warn"}:
            safe_output = getattr(agg, "final_content", response.message)
            if not isinstance(safe_output, str):
                return (
                    Err(
                        AgentError(
                            "Output safety checks are temporarily unavailable.",
                            details={"error_type": "InvalidGuardContent"},
                        ),
                    ),
                    response,
                )
        else:
            logger.warning("output_guard_unknown_action")
            return (
                Err(
                    AgentError(
                        "Output safety checks are temporarily unavailable.",
                        details={"error_type": "UnknownGuardAction"},
                    ),
                ),
                response,
            )

        return None, replace(response, message=safe_output)
    except Exception as exc:  # noqa: BLE001 - output guard failures fail closed
        error_type = safe_error_type(exc)
        logger.error(
            "output_guard_evaluation_failed",
            error_type=error_type,
        )
        return (
            Err(
                AgentError(
                    "Output safety checks are temporarily unavailable.",
                    details={"error_type": error_type},
                ),
            ),
            response,
        )


async def persist_conversation(
    self: AgentExecutorImpl,
    response: AgentResponse,
    message: str,
    session_id: str | None,
    user_id: str | None,
) -> None:
    """Save the exchange to working memory, session turns, and legacy memory."""
    if self._working_memory:
        try:
            from quadkit.contracts.ai.memory import MemoryEntry

            owner = user_id or session_id or "anonymous"
            user_entry = MemoryEntry(
                id=f"{session_id or 'no-session'}-user-{response.step_count}",
                owner_id=owner,
                content=message,
                role="user",
                timestamp=datetime.now(UTC),
            )
            assistant_entry = MemoryEntry(
                id=f"{session_id or 'no-session'}-assistant-{response.step_count}",
                owner_id=owner,
                content=response.message,
                role="assistant",
                timestamp=datetime.now(UTC),
            )
            await self._working_memory.add(user_entry)
            await self._working_memory.add(assistant_entry)
        except Exception as exc:  # noqa: BLE001 — working memory save degrades on any error
            logger.warning(
                "working_memory_save_failed", error_type=safe_error_type(exc)
            )

    if self._session_manager and session_id:
        try:
            from quadkit.contracts.ai.session import SessionTurn

            user_turn = SessionTurn(
                turn_id=f"{session_id}-user-{response.step_count}",
                role="user",
                content=message,
                timestamp=datetime.now(UTC),
            )
            assistant_turn = SessionTurn(
                turn_id=f"{session_id}-assistant-{response.step_count}",
                role="assistant",
                content=response.message,
                timestamp=datetime.now(UTC),
                tokens_used=response.total_tokens,
                tool_calls=[
                    {"name": tc.tool_name, "result": tc.result}
                    for tc in response.tool_calls
                ],
            )
            await self._session_manager.add_turn(session_id, user_turn)
            await self._session_manager.add_turn(session_id, assistant_turn)
        except Exception as exc:  # noqa: BLE001 — session turn save degrades on any error
            logger.warning("session_turn_save_failed", error_type=safe_error_type(exc))

    if self._memory and session_id:
        try:
            if hasattr(self._memory, "add"):
                await self._memory.add("user", message)
                await self._memory.add("assistant", response.message)
            elif hasattr(self._memory, "add_message"):
                from quadkit.contracts.ai.llm import ChatMessage, Role

                await self._memory.add_message(
                    ChatMessage(role=Role.USER, content=message),
                )
                await self._memory.add_message(
                    ChatMessage(role=Role.ASSISTANT, content=response.message),
                )
        except Exception as exc:  # noqa: BLE001 — memory save degrades on any error
            logger.warning("memory_save_failed", error_type=safe_error_type(exc))


def datetime_now_utc() -> Any:
    """Current wall-clock time as a timezone-aware datetime (UTC)."""
    from datetime import datetime

    return datetime.now(UTC)


async def track_cost(
    self: AgentExecutorImpl,
    response: AgentResponse,
    user_id: str | None,
) -> AgentResponse:
    """Track cost when an estimator is configured; returns the response."""
    if not (self._governance and self._cost_estimator and response.total_tokens > 0):
        return response

    try:
        model = getattr(self._llm, "model", "unknown")
        estimated_cost = self._cost_estimator.estimate_cost(
            model=model,
            total_tokens=response.total_tokens,
            provider=getattr(self._llm, "provider", None),
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )
        await self._governance.track_cost(
            cost=estimated_cost,
            model=model,
            user_id=user_id,
        )
        return replace(response, total_cost=estimated_cost)
    except Exception as exc:  # noqa: BLE001 — cost tracking is best-effort
        logger.warning("cost_tracking_failed", error_type=safe_error_type(exc))
    return response
