"""Streaming support for AgentExecutorImpl.

Provides the astream() method for streaming agent execution events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from quadkit.contracts.ai.agents import AgentEvent, AgentEventType
from quadkit.logging import get_logger, safe_error_type

logger = get_logger(__name__)

if TYPE_CHECKING:
    from quadkit.ai.agents.executor.executor import AgentExecutorImpl
    from quadkit.contracts.ai.agents import AgentProtocol
    from quadkit.contracts.ai.guards import GuardPipelineProtocol


async def astream(
    self: AgentExecutorImpl,
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
    run_id = str(uuid.uuid4())

    yield AgentEvent(
        type=AgentEventType.STARTED,
        data={
            "agent_name": agent.name,
            "session_id": session_id,
            "user_id": user_id,
            "message_length": len(message),
        },
        run_id=run_id,
    )

    governance_ok = await _check_governance(self, agent, user_id)
    if not governance_ok:
        yield AgentEvent(
            type=AgentEventType.ERROR,
            data={
                "error": "Governance denied request",
                "agent_name": agent.name,
            },
            run_id=run_id,
        )
        yield AgentEvent(
            type=AgentEventType.FINISHED,
            data={
                "agent_name": agent.name,
                "success": False,
                "error": "Governance denied",
            },
            run_id=run_id,
        )
        return

    # Agent-level pipeline (AgentBuilder.with_guard_pipeline) wins over the
    # DI-provided one; the DI pipeline remains the standard default.
    agent_pipeline = getattr(agent, "guard_pipeline", None)
    guard_pipeline = (
        agent_pipeline if agent_pipeline is not None else self._guard_pipeline
    )

    guard_ok, message = await _check_guard_input(
        self, guard_pipeline, message, session_id, user_id
    )
    if not guard_ok:
        yield AgentEvent(
            type=AgentEventType.ERROR,
            data={
                "error": "Input blocked by guard pipeline",
                "agent_name": agent.name,
            },
            run_id=run_id,
        )
        yield AgentEvent(
            type=AgentEventType.FINISHED,
            data={
                "agent_name": agent.name,
                "success": False,
                "error": "Input blocked",
            },
            run_id=run_id,
        )
        return

    try:
        strategy = getattr(agent, "strategy", None)
        if strategy is None:
            from quadkit.ai.agents.strategies.react import ReActStrategy

            strategy = ReActStrategy()

        history = await _load_history(self, message, session_id)
        tools = list(agent.tools) if agent.tools else []
        await _merge_skills(self, tools)

        strategy_history = [{"role": m.role, "content": m.content} for m in history]

        strategy_kwargs = dict(kwargs)
        strategy_kwargs.pop("tool_registry", None)  # passed explicitly below
        result = await strategy.execute(
            message=message,
            tools=tools,
            history=strategy_history,
            llm=self._llm,  # type: ignore[arg-type]
            system_prompt=agent.system_prompt,
            temperature=getattr(agent, "temperature", 0.7),
            tool_registry=kwargs.get("tool_registry"),
            memory=getattr(agent, "memory", None),
            guard_pipeline=guard_pipeline,
            **strategy_kwargs,
        )

        if result.is_err():
            error = result.unwrap_err()
            error_type = safe_error_type(error)
            logger.warning(
                "astream_strategy_failed",
                error_type=error_type,
            )
            yield AgentEvent(
                type=AgentEventType.ERROR,
                data={
                    "error": "Agent strategy failed",
                    "error_type": error_type,
                    "agent_name": agent.name,
                },
                run_id=run_id,
            )
            yield AgentEvent(
                type=AgentEventType.FINISHED,
                data={
                    "agent_name": agent.name,
                    "success": False,
                    "error": "Agent strategy failed",
                    "error_type": error_type,
                },
                run_id=run_id,
            )
            return

        response = result.unwrap()

        guard_ok, safe_output = await _check_guard_output(
            self, guard_pipeline, response.message, message, session_id, user_id
        )
        if not guard_ok:
            yield AgentEvent(
                type=AgentEventType.ERROR,
                data={
                    "error": "Output blocked by guard pipeline",
                    "agent_name": agent.name,
                },
                run_id=run_id,
            )
            yield AgentEvent(
                type=AgentEventType.FINISHED,
                data={
                    "agent_name": agent.name,
                    "success": False,
                    "error": "Output blocked",
                },
                run_id=run_id,
            )
            return

        yield AgentEvent(
            type=AgentEventType.MESSAGE,
            data={
                "message": safe_output,
                "agent_name": agent.name,
            },
            run_id=run_id,
        )

        yield AgentEvent(
            type=AgentEventType.FINISHED,
            data={
                "agent_name": agent.name,
                "success": True,
                "message": safe_output,
                "steps": response.step_count,
                "tool_calls": response.tool_call_count,
                "total_tokens": response.total_tokens,
                "duration_ms": response.duration_ms,
            },
            run_id=run_id,
        )

    except Exception as exc:
        error_type = safe_error_type(exc)
        logger.error(
            "astream_execution_failed",
            error_type=error_type,
        )
        yield AgentEvent(
            type=AgentEventType.ERROR,
            data={
                "error": "Agent execution failed",
                "error_type": error_type,
                "agent_name": agent.name,
            },
            run_id=run_id,
        )
        yield AgentEvent(
            type=AgentEventType.FINISHED,
            data={
                "agent_name": agent.name,
                "success": False,
                "error": "Agent execution failed",
                "error_type": error_type,
            },
            run_id=run_id,
        )


async def _check_governance(
    self: AgentExecutorImpl,
    agent: AgentProtocol,
    user_id: str | None,
) -> bool:
    """Check governance and emit events."""
    if not self._governance:
        return True

    try:
        model = getattr(self._llm, "model", "unknown")
        provider = getattr(self._llm, "provider", "unknown")
        allowed = await self._governance.check_request(
            model=model,
            provider=provider,
            user_id=user_id,
        )
        if not allowed:
            logger.warning("agent_governance_denied")
            return False
    except Exception as exc:
        logger.warning(
            "governance_check_failed",
            error_type=safe_error_type(exc),
        )

    return True


async def _check_guard_input(
    self: AgentExecutorImpl,
    guard_pipeline: GuardPipelineProtocol | None,
    message: str,
    session_id: str | None,
    user_id: str | None,
) -> tuple[bool, str]:
    """Check input and propagate redacted content before strategy execution."""
    if not guard_pipeline:
        return True, message

    try:
        guard_res = await guard_pipeline.check_input(
            content=message,
            metadata={"session_id": session_id, "user_id": user_id},
        )
        if not guard_res.is_ok():
            logger.warning("guard_input_check_failed", reason="guard_error_result")
            return False, message

        agg = guard_res.unwrap()
        action = str(getattr(agg, "action", "pass"))
        blocked = bool(getattr(agg, "blocked", False)) or action == "block"
        if blocked:
            logger.warning("input_blocked")
            return False, message
        if action == "redact":
            safe_message = getattr(agg, "final_content", None)
            if not isinstance(safe_message, str):
                logger.warning("guard_input_redaction_missing_content")
                return False, message
            return True, safe_message
        if action not in {"pass", "warn"}:
            logger.warning("guard_input_unknown_action")
            return False, message

        safe_message = getattr(agg, "final_content", message)
        if not isinstance(safe_message, str):
            logger.warning("guard_input_invalid_final_content")
            return False, message
        return True, safe_message
    except Exception as exc:  # noqa: BLE001 - input guard errors fail closed
        logger.warning(
            "guard_input_check_failed",
            error_type=safe_error_type(exc),
        )
        return False, message


async def _check_guard_output(
    self: AgentExecutorImpl,
    guard_pipeline: GuardPipelineProtocol | None,
    output: str,
    original_input: str,
    session_id: str | None,
    user_id: str | None,
) -> tuple[bool, str]:
    """Check output and propagate redacted content before streaming it."""
    if not guard_pipeline:
        return True, output

    try:
        guard_res = await guard_pipeline.check_output(
            content=output,
            original_input=original_input,
            metadata={"session_id": session_id, "user_id": user_id},
        )
        if not guard_res.is_ok():
            logger.warning("guard_output_check_failed", reason="guard_error_result")
            return False, output

        agg = guard_res.unwrap()
        action = str(getattr(agg, "action", "pass"))
        blocked = bool(getattr(agg, "blocked", False)) or action == "block"
        if blocked:
            logger.warning("output_blocked")
            return False, output
        if action == "redact":
            safe_output = getattr(agg, "final_content", None)
            if not isinstance(safe_output, str):
                logger.warning("guard_output_redaction_missing_content")
                return False, output
            return True, safe_output
        if action not in {"pass", "warn"}:
            logger.warning("guard_output_unknown_action")
            return False, output

        safe_output = getattr(agg, "final_content", output)
        if not isinstance(safe_output, str):
            logger.warning("guard_output_invalid_final_content")
            return False, output
        return True, safe_output
    except Exception as exc:  # noqa: BLE001 - output guard errors fail closed
        logger.warning(
            "guard_output_check_failed",
            error_type=safe_error_type(exc),
        )
        return False, output


async def _load_history(
    self: AgentExecutorImpl,
    message: str,
    session_id: str | None,
) -> list[Any]:
    """Load conversation history."""
    from quadkit.contracts.ai.llm import ChatMessage, Role

    history: list[ChatMessage] = []

    if self._working_memory:
        try:
            entries = await self._working_memory.assemble(
                query=message,
                token_budget=4096,
                owner_id=session_id or "anonymous",
            )
            history = [
                ChatMessage(role=Role(e.role), content=e.content) for e in entries
            ]
        except Exception as exc:
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
        except Exception as exc:
            logger.warning(
                "memory_load_failed",
                error_type=safe_error_type(exc),
            )

    return history


async def _merge_skills(
    self: AgentExecutorImpl,
    tools: list[Any],
) -> None:
    """Merge skills as additional tools."""
    if not self._skill_registry:
        return

    try:
        skill_schemas = self._skill_registry.get_schemas()
        tools.extend(skill_schemas)
    except Exception as exc:
        logger.warning(
            "skill_registry_merge_failed",
            error_type=safe_error_type(exc),
        )
