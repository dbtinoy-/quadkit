"""Dead-letter handling for failed task jobs.

Routes permanently failed jobs to the dead letter queue, falling back to
a DLQ-prefixed re-enqueue when no dedicated DLQ service is configured.
"""

from __future__ import annotations

from typing import Any

from quadkit.tasks.models.job import JobProtocol
from quadkit.tasks.safe_errors import safe_failure_message

__all__ = ["send_to_dlq"]


async def send_to_dlq(
    dlq: Any | None,
    queue: Any,
    job: JobProtocol,
    error_msg: str,
    *,
    worker_id: str,
    logger_instance: Any,
) -> None:
    """Send a failed job to the dead letter queue.

    Uses the configured DeadLetterQueue when present; otherwise falls
    back to re-enqueueing under a ``dlq:``-prefixed name, preferring a
    dedicated ``enqueue_dlq`` backend method when supported.

    Args:
        dlq: Configured dead letter queue service, or ``None``.
        queue: The task queue used for the fallback re-enqueue path.
        job: Failed job to send to DLQ
        error_msg: Optional error message from the failure
        worker_id: Identifier of the worker reporting the failure.
        logger_instance: Bound logger for the reporting worker.
    """
    del worker_id  # retained for compatibility; worker identifiers are not logged
    safe_error = safe_failure_message(error_msg)
    if dlq is not None:
        # Use the proper DeadLetterQueue class with a redacted failure reason.
        dlq.add(
            job=job,
            error=safe_error,
            attempt_count=job.retry_count,
        )
        logger_instance.info("worker_job_added_to_dlq")
        return

    # Fallback: re-enqueue under a DLQ-prefixed name
    dlq_name = f"dlq:{job.name}"
    dlq_job = JobProtocol(
        id=f"dlq:{job.id}",
        name=dlq_name,
        args=job.args,
        kwargs=job.kwargs,
        priority=job.priority,
        max_retries=0,  # No retries in DLQ
        status=job.status,
        created_at=job.created_at,
        retry_count=job.retry_count,
        last_error=safe_error,
    )
    # Prefer a dedicated DLQ enqueue method if the backend supports it
    enqueue_dlq = getattr(queue, "enqueue_dlq", None)
    if enqueue_dlq is not None and callable(enqueue_dlq):
        await enqueue_dlq(dlq_job)
    else:
        await queue.enqueue(dlq_job)
    logger_instance.info("worker_job_sent_to_dlq")
