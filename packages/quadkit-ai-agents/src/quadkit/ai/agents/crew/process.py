"""Process enum - defines how crew tasks are executed."""

from __future__ import annotations

from enum import StrEnum


class Process(StrEnum):
    """Execution process for crew tasks.

    Sequential: Tasks run one after another, later tasks see prior outputs.
    Hierarchical: Manager LLM assigns tasks to workers.
    """

    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"
