"""Agent executor service using Result pattern."""

from __future__ import annotations

from quadkit.contracts.ai.agents import AgentError
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


class AgentExecutorWithResultPattern:
    """Agent executor using Result pattern."""

    async def execute(
        self, agent_name: str, task: str, tools: list | None = None
    ) -> Result[dict, AgentError]:
        """Execute an agent."""
        try:
            if not agent_name:
                return Err(AgentError("Agent name cannot be empty"))
            if not task:
                return Err(AgentError("Task cannot be empty"))
            result = {"agent": agent_name, "task": task, "result": "completed"}
            logger.info("agent_executed", tools=len(tools or []))
            return Ok(result)
        except Exception as exc:  # noqa: BLE001 — any execution failure is an Err result
            error_type = type(exc).__name__
            logger.error(
                "agent_execution_failed",
                error_type=error_type,
            )
            return Err(
                AgentError(
                    "Agent execution failed",
                    details={"error_type": error_type},
                ),
            )


__all__ = ["AgentExecutorWithResultPattern"]
