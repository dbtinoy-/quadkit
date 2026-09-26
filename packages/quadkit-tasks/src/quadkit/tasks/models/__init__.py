"""Task models and data structures."""

from __future__ import annotations

from quadkit.contracts.infra.tasks import JobStatus
from quadkit.tasks.models.job import JobProtocol, JobResult

__all__ = ["JobProtocol", "JobResult", "JobStatus"]
