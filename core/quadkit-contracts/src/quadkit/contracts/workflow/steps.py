"""Pipeline step execution result types.

Moved from ``quadkit.contracts.execution`` — step results are a workflow
concern, not a generic execution or Result concern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from quadkit.contracts.core.result import Result

__all__ = [
    "SagaStep",
    "SagaStepError",
]


class SagaStepError(Exception):
    """Represents a recoverable failure from a single saga step action.

    SagaProtocol step actions must return ``Result[T, SagaStepError]`` so that the
    orchestration layer can detect failures without catching exceptions.

    Attributes:
        step_name: Identifier of the failing step (set by the orchestrator).
        detail: Human-readable description of what went wrong.
    """

    _code: str = "QK_ERR_WF_002"

    def __init__(self, detail: str, step_name: str = "") -> None:
        super().__init__(detail)
        self.detail = detail
        self.step_name = step_name

    def __repr__(self) -> str:
        """Return developer-friendly repr."""
        return f"{type(self).__name__}(step={self.step_name!r}, detail={self.detail!r})"


@dataclass(frozen=True)
class SagaStep:
    """Descriptor for a single saga orchestration step.

    Shared across ``the optional provider`` and ``the optional provider`` via contracts.

    The ``action`` callable **must** return ``Result[Any, SagaStepError]``.
    The ``compensation`` callable is called only when the saga is unwinding
    and may raise exceptions freely (infrastructure failures in compensation
    should propagate).

    Attributes:
        name: Unique step identifier within the saga.
        action: Async callable returning ``Result[Any, SagaStepError]``.
        compensation: Async callable to undo the step on failure.
        max_retries: Maximum retry attempts if action returns ``Err``.
        retry_delay: Seconds to wait between retry attempts.
        idempotent: Whether the compensation is safe to call multiple times.
    """

    name: str
    action: Callable[..., Awaitable[Result[Any, SagaStepError]]]
    compensation: Callable[..., Awaitable[None]] | None = None
    max_retries: int = 3
    retry_delay: float = 1.0
    idempotent: bool = field(default=False)
