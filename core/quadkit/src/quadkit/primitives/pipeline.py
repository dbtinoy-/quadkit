"""Core pipeline abstractions — PipelineStep base class and PipelineContext.

These primitives live in the core ``quadkit`` package so that any extension
package can build pipeline-compatible steps without depending on
``the optional provider``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.infra.resilience import ResiliencePipelineProtocol

T = TypeVar("T")


class StepStatus(StrEnum):
    """Pipeline step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepExecutionResult(Generic[T]):
    """Result of executing a single pipeline step."""

    step_name: str
    status: StepStatus
    result: T | None = None
    error: Exception | None = None
    duration: float | None = None
    metadata: dict[str, Any] | None = None
    skipped_reason: str | None = None


@dataclass
class PipelineContext:
    """Context passed through pipeline execution, accumulating step results and metadata."""

    pipeline_name: str
    step_results: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    start_time: float | None = None
    end_time: float | None = None

    def get_step_result(self, step_name: str, default: Any = None) -> Any:
        """Get result from a completed step.

        Args:
            step_name: The name of the step whose result to retrieve.
            default: Value to return if the step has no recorded result.

        Returns:
            The recorded step result, or *default* if not found.
        """
        return self.step_results.get(step_name, default)

    def set_step_result(self, step_name: str, result: Any) -> None:
        """Set result for a step.

        Args:
            step_name: The name of the step.
            result: The result value to record.
        """
        self.step_results[step_name] = result

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the context.

        Args:
            key: Metadata key.
            value: Metadata value.
        """
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from the context.

        Args:
            key: Metadata key to look up.
            default: Value to return if the key is absent.

        Returns:
            The metadata value, or *default* if not found.
        """
        return self.metadata.get(key, default)

    @property
    def duration(self) -> float:
        """Total duration of pipeline execution in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or asyncio.get_event_loop().time()
        return end - self.start_time

    @property
    def failed_steps(self) -> list[StepExecutionResult]:
        """List of failed step results."""
        results = self.get_metadata("step_results", [])
        return [r for r in results if r.status == StepStatus.FAILED]

    @property
    def successful_steps(self) -> list[StepExecutionResult]:
        """List of successfully completed step results."""
        results = self.get_metadata("step_results", [])
        return [r for r in results if r.status == StepStatus.COMPLETED]

    def has_failed(self) -> bool:
        """Check if any steps in the pipeline failed.

        Returns:
            ``True`` if at least one step has a FAILED status.
        """
        return len(self.failed_steps) > 0


class PipelineStep(ABC):
    """Abstract base class for pipeline steps.

    Non-``execute`` helpers are deliberately simple: they return plain
    values and may raise exceptions.  This keeps user implementations
    lightweight and avoids the noise of wrapping every result in
    ``Result``. Helpers are responsible for handling their own errors;
    the pipeline driver will catch and convert them into failed step
    records if necessary.

    Steps may specify an optional ``timeout`` (in seconds). When set, the
    :func:`execute` invocation will be wrapped with ``asyncio.wait_for``
    so that a long-running or hung step is interrupted and treated as a
    failure. The timeout does **not** apply to ``should_skip``,
    ``on_error`` or ``cleanup`` helpers.
    """

    def __init__(
        self,
        name: str,
        dependencies: list[str] | None = None,
        timeout: float | None = None,
        resilience: ResiliencePipelineProtocol | None = None,
    ) -> None:
        self.name = name
        self.dependencies = dependencies or []
        self.timeout = timeout
        self.resilience = resilience

    @abstractmethod
    async def execute(self, context: PipelineContext) -> Result[Any, Exception]:
        """Execute the pipeline step.

        Args:
            context: The shared pipeline context carrying inter-step data.

        Returns:
            A ``Result`` wrapping the step's output or a failure.
        """
        ...

    async def should_skip(self, context: PipelineContext) -> Result[bool, Exception]:
        """Determine whether to skip this step.

        Args:
            context: The current pipeline context.

        Returns:
            ``Ok(True)`` to skip, ``Ok(False)`` to execute, or ``Err(e)``
            on failure while evaluating the condition.

        The default implementation always returns ``Ok(False)``.
        """
        del context
        return Ok(False)

    async def on_error(
        self,
        context: PipelineContext,
        error: Exception,
    ) -> Any:
        """Handle errors raised during ``execute``.

        Args:
            context: The current pipeline context.
            error: The exception that caused the step to fail.

        The default behaviour is to re-raise the error, which causes the
        step (and pipeline) to fail.  Custom handlers may return a value
        to recover and continue the pipeline.
        """
        del context
        raise error

    async def cleanup(self, context: PipelineContext) -> Result[None, Exception]:
        """Cleanup resources after step execution.

        Args:
            context: The current pipeline context.

        Called regardless of success or failure.  The default implementation
        does nothing.  Exceptions are logged but not propagated.
        """
        del context
        return Ok(None)


__all__ = [
    "PipelineContext",
    "PipelineStep",
    "StepExecutionResult",
    "StepStatus",
]
