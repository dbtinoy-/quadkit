"""Workflow runner — wraps WorkflowEngine with optional retry logic."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger, safe_error_type
from quadkit.result import Err, Result
from quadkit.workflow.graph.state import WorkflowState

if TYPE_CHECKING:
    from quadkit.workflow.exceptions import GraphExecutionError
    from quadkit.workflow.graph.engine import WorkflowEngine
    from quadkit.workflow.types import GraphResult

logger = get_logger(__name__)


class WorkflowRunner:
    """Execute a WorkflowEngine with retry and optional checkpointing.

    Args:
        engine: The WorkflowEngine to run.
        max_retries: Maximum attempts after the first failure.
        retry_delay: Seconds to wait between attempts.
        checkpoint: Optional WorkflowCheckpoint instance.
    """

    def __init__(
        self,
        engine: WorkflowEngine,
        *,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        checkpoint: Any | None = None,
    ) -> None:
        self._engine = engine
        self._max_retries = max(0, max_retries)
        self._retry_delay = max(0.0, retry_delay)
        self._checkpoint = checkpoint

    async def run(
        self,
        input: str,
        *,
        state: dict[str, Any] | WorkflowState | None = None,
    ) -> Result[GraphResult, GraphExecutionError]:
        """Execute the workflow, retrying on transient failures.

        Args:
            input: Workflow input string.
            state: Optional pre-populated WorkflowState.

        Returns:
            Ok(GraphResult) on success or Err(GraphExecutionError) on
            permanent failure.

        Raises:
            HumanInputRequiredError: When a HumanNode pauses execution.
        """
        attempts = 0
        last_error: GraphExecutionError | None = None

        while attempts <= self._max_retries:
            if attempts > 0:
                logger.info(
                    "workflow_runner_retry",
                    attempt=attempts + 1,
                )
                await asyncio.sleep(self._retry_delay)

            initial_state = (
                state.as_dict() if isinstance(state, WorkflowState) else state
            )
            result = await self._engine.execute(input, state=initial_state)

            attempts += 1

            if result.is_ok():
                logger.debug(
                    "workflow_runner_success",
                    attempts=attempts,
                )
                return result

            last_error = result.unwrap_err()
            logger.warning(
                "workflow_runner_attempt_failed",
                attempt=attempts,
                error_type=safe_error_type(last_error),
            )

        logger.error(
            "workflow_runner_exhausted",
            attempts=attempts,
        )
        assert last_error is not None  # noqa: S101  # exhaustion path always records an error
        return Err(last_error)

    async def resume(
        self,
        human_response: str,
        *,
        state: WorkflowState,
        response_key: str | None = None,
    ) -> Result[GraphResult, GraphExecutionError]:
        """Resume a paused HITL workflow by injecting the human response.

        Delegates to ``WorkflowEngine.resume`` so the definition-version
        guard applies and execution continues from the paused node (not
        the entry).  The caller's state is not mutated.

        Args:
            human_response: The operator response to inject into state.
            state: The WorkflowState from the paused point.
            response_key: Optional explicit state key for the response.
                When omitted, the paused node's ``resume_key`` decides.

        Returns:
            Ok(GraphResult) on success or Err(GraphExecutionError).
        """
        return await self._engine.resume(
            state.as_dict(),
            human_response,
            response_key=response_key,
        )


__all__ = ["WorkflowRunner"]
