"""Decorator utilities for creating pipeline steps from functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.workflow.pipeline.steps import (
    ConditionalStep,
    FunctionStep,
    ParallelStep,
    PipelineStep,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from quadkit.primitives.pipeline import PipelineContext
    from quadkit.result import Result


def step(
    name: str,
    func: Callable[[PipelineContext], Awaitable[Result[Any, Exception]]],
    dependencies: list[str] | None = None,
    timeout: float | None = None,
) -> FunctionStep:
    """Create a function-based pipeline step.

    ``timeout`` is an optional per-step timeout in seconds; it is forwarded
    to :class:`FunctionStep`.
    """
    return FunctionStep(name, func, dependencies, timeout=timeout)


def conditional(
    name: str,
    condition: Callable[[PipelineContext], Awaitable[Result[bool, Exception]]],
    true_step: PipelineStep,
    false_step: PipelineStep | None = None,
    dependencies: list[str] | None = None,
    timeout: float | None = None,
) -> ConditionalStep:
    """Create a conditional pipeline step."""
    return ConditionalStep(
        name,
        condition,
        true_step,
        false_step,
        dependencies,
        timeout=timeout,
    )


def parallel(
    name: str,
    steps: list[PipelineStep],
    dependencies: list[str] | None = None,
    *,
    fail_fast: bool = True,
    timeout: float | None = None,
) -> ParallelStep:
    """Create a parallel execution step."""
    return ParallelStep(
        name,
        steps,
        dependencies,
        fail_fast=fail_fast,
        timeout=timeout,
    )


def pipeline_step(
    dependencies: list[str] | None = None,
) -> Callable[
    [Callable[[PipelineContext], Awaitable[Result[Any, Exception]]]],
    FunctionStep,
]:
    """Decorator to convert a function into a pipeline step."""

    def decorator(
        func: Callable[[PipelineContext], Awaitable[Result[Any, Exception]]],
    ) -> FunctionStep:
        return FunctionStep(func.__name__, func, dependencies)

    return decorator


__all__ = [
    "conditional",
    "parallel",
    "pipeline_step",
    "step",
]
