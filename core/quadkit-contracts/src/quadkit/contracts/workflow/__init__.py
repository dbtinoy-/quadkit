"""Workflow contracts — pipeline, bulk, and saga orchestration protocols."""

from __future__ import annotations

from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
    ContentCheckpointStoreProtocol,
)
from quadkit.contracts.workflow.errors import SagaVersionMismatchError
from quadkit.contracts.workflow.protocols import (
    ApprovalProtocol,
    BulkProcessorProtocol,
    ExecutionProtocol,
    PipelineContextProtocol,
    PipelineProtocol,
    PipelineStepProtocol,
    SagaManagerProtocol,
    SagaProtocol,
    SagaState,
    SagaStoreProtocol,
    StateMachineProtocol,
    StatePersistenceProtocol,
    StateTransitionRecord,
    WorkflowGraphProtocol,
    WorkflowNodeProtocol,
)
from quadkit.contracts.workflow.steps import SagaStep, SagaStepError

__all__ = [
    "ApprovalProtocol",
    "BulkProcessorProtocol",
    "ContentCheckpointEntry",
    "ContentCheckpointKey",
    "ContentCheckpointStoreProtocol",
    "ExecutionProtocol",
    "PipelineContextProtocol",
    "PipelineProtocol",
    "PipelineStepProtocol",
    "SagaManagerProtocol",
    "SagaProtocol",
    "SagaState",
    "SagaStep",
    "SagaStepError",
    "SagaStoreProtocol",
    "SagaVersionMismatchError",
    "StateMachineProtocol",
    "StatePersistenceProtocol",
    "StateTransitionRecord",
    "WorkflowGraphProtocol",
    "WorkflowNodeProtocol",
]
