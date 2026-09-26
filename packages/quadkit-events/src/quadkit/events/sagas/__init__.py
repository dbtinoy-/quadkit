"""SagaProtocol orchestration — SagaBase, SagaStep, SagaManagerProtocol, InMemorySagaStore.

A saga coordinates multi-step distributed transactions with compensation on failure.
"""

from __future__ import annotations

from quadkit.events.sagas.base import SagaBase, SagaStep, saga_step
from quadkit.events.sagas.context import SagaContext, SagaStepResult
from quadkit.events.sagas.manager import SagaManagerProtocol
from quadkit.events.sagas.sql import SqlSagaStore
from quadkit.events.sagas.store import InMemorySagaStore, SagaStore
from quadkit.events.sagas.types import (
    SagaRecord,
    SagaStatus,
    SagaStepRecord,
    SagaStepStatus,
)

__all__ = [
    "InMemorySagaStore",
    "SagaBase",
    "SagaContext",
    "SagaManagerProtocol",
    "SagaRecord",
    "SagaStatus",
    "SagaStep",
    "SagaStepRecord",
    "SagaStepResult",
    "SagaStepStatus",
    "SagaStore",
    "SqlSagaStore",
    "saga_step",
]
