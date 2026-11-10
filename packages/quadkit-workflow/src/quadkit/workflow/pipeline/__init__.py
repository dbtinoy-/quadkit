"""Pipeline pattern implementation for quadkit-workflow.

The Pipeline pattern provides a declarative way to compose complex business
workflows with proper error handling, context propagation, and async execution.
"""

from __future__ import annotations

from quadkit.primitives.pipeline import (
    PipelineContext,
    StepExecutionResult,
    StepStatus,
)
from quadkit.workflow.pipeline.decorators import (
    conditional,
    parallel,
    pipeline_step,
    step,
)
from quadkit.workflow.pipeline.executor import Pipeline
from quadkit.workflow.pipeline.steps import (
    ConditionalStep,
    FunctionStep,
    ParallelStep,
    PipelineStep,
)

__all__ = [
    "ConditionalStep",
    "FunctionStep",
    "ParallelStep",
    "Pipeline",
    "PipelineContext",
    "PipelineStep",
    "StepExecutionResult",
    "StepStatus",
    "conditional",
    "parallel",
    "pipeline_step",
    "step",
]
