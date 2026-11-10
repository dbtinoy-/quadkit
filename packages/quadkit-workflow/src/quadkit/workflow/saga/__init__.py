"""SagaProtocol orchestration primitives for quadkit-workflow."""

from __future__ import annotations

from quadkit.contracts.workflow.protocols import SagaState, SagaStoreProtocol
from quadkit.contracts.workflow.steps import SagaStepError
from quadkit.workflow.saga.base import AbstractSaga, SagaError, SagaStep
from quadkit.workflow.saga.batch import SagaBatchProcessor
from quadkit.workflow.saga.content_addressed import (
    ContentAddressedSaga,
    ContentAddressedStage,
)
from quadkit.workflow.saga.hooks import (
    SagaCompensationCompletedHook,
    SagaCompensationContext,
    SagaCompensationTriggeredHook,
    SagaStepContext,
    SagaStepExecutedHook,
    SagaStepFailedHook,
)

__all__ = [
    "AbstractSaga",
    "ContentAddressedSaga",
    "ContentAddressedStage",
    "SagaBatchProcessor",
    "SagaCompensationCompletedHook",
    "SagaCompensationContext",
    "SagaCompensationTriggeredHook",
    "SagaError",
    "SagaState",
    "SagaStep",
    "SagaStepContext",
    "SagaStepError",
    "SagaStepExecutedHook",
    "SagaStepFailedHook",
    "SagaStoreProtocol",
]
