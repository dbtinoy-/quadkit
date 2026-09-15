"""Domain value objects for idempotency data."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime


class IdempotencyStatus(StrEnum):
    """Lifecycle status for idempotency records."""

    PENDING = auto()
    COMPLETE = auto()
    EXPIRED = auto()


@dataclass(frozen=True)
class IdempotencyRecord:
    """Immutable snapshot of an idempotency entry."""

    key: str
    result: Any
    created_at: datetime
    expires_at: datetime
    status: IdempotencyStatus = field(default=IdempotencyStatus.PENDING)


__all__ = [
    "IdempotencyRecord",
    "IdempotencyStatus",
]
