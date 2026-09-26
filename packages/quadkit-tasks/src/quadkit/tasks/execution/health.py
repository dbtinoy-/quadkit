"""Health monitoring for task processing

This module provides health check and statistics interfaces for task processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class TaskHealth:
    """Health status for task processing system

    Aggregates health information from queue, workers, and scheduler.
    """

    status: str  # healthy, degraded, unhealthy
    message: str
    timestamp: float = field(default_factory=time.time)
    queue_size: int = 0
    worker_count: int = 0
    active_workers: int = 0
    total_jobs_processed: int = 0
    total_jobs_succeeded: int = 0
    total_jobs_failed: int = 0
    scheduler_enabled: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Check if system is healthy"""
        return self.status == "healthy"

    @property
    def success_rate(self) -> float:
        """Calculate job success rate"""
        total = self.total_jobs_processed
        if total == 0:
            return 100.0
        return (self.total_jobs_succeeded / total) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp,
            "metrics": {
                "queue_size": self.queue_size,
                "worker_count": self.worker_count,
                "active_workers": self.active_workers,
                "total_jobs_processed": self.total_jobs_processed,
                "total_jobs_succeeded": self.total_jobs_succeeded,
                "total_jobs_failed": self.total_jobs_failed,
                "success_rate": self.success_rate,
            },
            "scheduler_enabled": self.scheduler_enabled,
            "details": self.details,
        }
