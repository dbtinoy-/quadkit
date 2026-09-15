"""Task and job queue enums for Quadkit Framework."""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """JobProtocol execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class OnErrorPolicy(StrEnum):
    """Controls what happens when a scheduled worker cycle raises.

    Attributes:
        LOG_AND_CONTINUE: Log the error, then resume the normal schedule.
        BACKOFF: Log the error and double the sleep before the next cycle
            (up to ``10 * interval_seconds``).
        STOP: Log the error and stop the worker permanently.
    """

    LOG_AND_CONTINUE = "LOG_AND_CONTINUE"
    BACKOFF = "BACKOFF"
    STOP = "STOP"


__all__ = ["JobStatus", "OnErrorPolicy"]
