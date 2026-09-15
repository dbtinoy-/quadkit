"""Concurrency enums for Quadkit Framework."""

from __future__ import annotations

from enum import StrEnum


class ConcurrencyStrategy(StrEnum):
    """Strategies for parallel task execution."""

    GATHER = "gather"
    RACE = "race"
    AS_COMPLETED = "as_completed"
    ALL_SETTLED = "all_settled"


ExecutionStrategy = ConcurrencyStrategy


__all__ = ["ConcurrencyStrategy", "ExecutionStrategy"]
