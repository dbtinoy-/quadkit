"""AbstractRepository module for aggregate persistence.

This module provides:
- EventSourcingRepository: AbstractRepository with snapshot-accelerated loading
- AbstractRepository: Base repository protocol
- AbstractReadOnlyRepository: Read-only repository interface
"""

from __future__ import annotations

from quadkit.events.repository.base import (
    AbstractReadOnlyRepository,
    AbstractRepository,
)
from quadkit.events.repository.event_sourcing import EventSourcingRepository

__all__ = [
    "AbstractReadOnlyRepository",
    "AbstractRepository",
    "EventSourcingRepository",
]
