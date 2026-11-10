"""Lifecycle hooks for saga execution — intercepted at specific execution points.

Hooks are callable signatures invoked when sagas and their steps reach specific
lifecycle events (e.g., step executed, compensation triggered). They differ from
domain events (immutable event records on an event bus) and decorators (function
wrappers).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class SagaStepContext:
    """Context passed to saga step lifecycle hooks.

    Attributes:
        saga_id: The unique identifier for the saga instance.
        step_name: The name of the saga step.
        attempt: The current attempt number (1-based).
    """

    saga_id: str
    step_name: str
    attempt: int


@dataclass(frozen=True)
class SagaCompensationContext:
    """Context passed to saga compensation lifecycle hooks.

    Attributes:
        saga_id: The unique identifier for the saga instance.
        step_name: The name of the step being compensated.
        original_error: String representation of the error that triggered compensation.
    """

    saga_id: str
    step_name: str
    original_error: str


SagaStepExecutedHook = Callable[[SagaStepContext], None]
"""Hook invoked when a saga step completes successfully."""

SagaStepFailedHook = Callable[[SagaStepContext], None]
"""Hook invoked when a saga step fails."""

SagaCompensationTriggeredHook = Callable[[SagaCompensationContext], None]
"""Hook invoked when saga compensation begins."""

SagaCompensationCompletedHook = Callable[[SagaCompensationContext], None]
"""Hook invoked when saga compensation completes."""
