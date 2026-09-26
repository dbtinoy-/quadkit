"""JobProtocol template system for scheduled tasks

This module provides job templates for reusable job configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.tasks.models.job import JobProtocol


@dataclass
class JobTemplateProtocol:
    """Template for creating scheduled jobs

    JobTemplateProtocol defines a reusable job configuration that can be
    instantiated multiple times with different IDs.

    Attributes:
        name: JobProtocol name/type
        args: Positional arguments
        kwargs: Keyword arguments
        priority: Execution priority
        max_retries: Maximum retry attempts
        timeout: Execution timeout
        depends_on: JobProtocol dependencies template
    """

    name: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    max_retries: int = 3
    timeout: float | None = None
    depends_on: list[str] = field(default_factory=list)

    def create_job(self, job_id: str = "") -> JobProtocol:
        """Create a JobProtocol instance from this template

        Args:
            job_id: JobProtocol ID (generated if empty)

        Returns:
            New JobProtocol instance
        """
        return JobProtocol(
            id=job_id,
            name=self.name,
            args=self.args,
            kwargs=self.kwargs,
            priority=self.priority,
            max_retries=self.max_retries,
            timeout=self.timeout,
            depends_on=self.depends_on.copy() if self.depends_on else [],
        )

    @classmethod
    def from_job(cls, job: JobProtocol) -> JobTemplateProtocol:
        """Create template from existing job

        Args:
            job: JobProtocol to convert to template

        Returns:
            JobTemplateProtocol instance
        """
        return cls(
            name=job.name,
            args=job.args,
            kwargs=job.kwargs,
            priority=job.priority,
            max_retries=job.max_retries,
            timeout=job.timeout,
            depends_on=job.depends_on.copy() if job.depends_on else [],
        )
