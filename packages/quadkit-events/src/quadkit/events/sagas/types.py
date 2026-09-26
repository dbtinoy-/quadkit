"""SagaProtocol status and record types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class SagaStatus(StrEnum):
    """Overall status of a saga execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


class SagaStepStatus(StrEnum):
    """Status of an individual saga step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


@dataclass
class SagaStepRecord:
    """Persisted record of a step execution."""

    step_name: str
    status: SagaStepStatus = SagaStepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    attempts: int = 0


@dataclass
class SagaRecord:
    """Persisted record of a full saga execution."""

    saga_id: str
    saga_name: str
    status: SagaStatus = SagaStatus.PENDING
    data: dict[str, Any] = field(default_factory=dict)
    steps: dict[str, SagaStepRecord] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error: str | None = None
