"""Regression tests for safe failure handling in in-memory and persistent DLQs."""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

import quadkit.tasks.dlq.core as core_module
import quadkit.tasks.dlq.persistent as persistent_module
from quadkit.tasks.dlq.backend import InMemoryDLQBackend
from quadkit.tasks.dlq.core import DeadLetterQueue, FailureRecord
from quadkit.tasks.dlq.persistent import PersistentDeadLetterQueue
from quadkit.tasks.models.job import JobProtocol

_PRIVATE_ERROR = "failure for /srv/app/users/user-42 job-993 traceback=secret"
_PRIVATE_TRACEBACK = "Traceback at /srv/app/private.py for user-42"


def _job(job_id: str = "job-secret-42") -> JobProtocol:
    return JobProtocol(id=job_id, name="private-user-task")


def test_in_memory_dlq_sanitizes_failure_details_and_identifiers_from_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DLQ records and logs must not retain exception text or tracebacks."""
    logger = MagicMock()
    monkeypatch.setattr(core_module, "logger", logger)
    dlq = DeadLetterQueue()
    job = _job()

    dlq.add(job, error=_PRIVATE_ERROR, traceback=_PRIVATE_TRACEBACK)

    record = dlq.get(job.id)
    assert record is not None
    assert record.error == "Task failed"
    assert record.traceback is None
    serialized = record.to_dict()
    assert serialized["error"] == "Task failed"
    assert serialized["traceback"] is None
    assert _PRIVATE_ERROR not in repr(serialized)
    assert _PRIVATE_TRACEBACK not in repr(serialized)

    logger.info.assert_called_once_with("dlq.job_added")
    assert "job-secret-42" not in repr(logger.mock_calls)
    assert "private-user-task" not in repr(logger.mock_calls)
    assert _PRIVATE_ERROR not in repr(logger.mock_calls)


def test_in_memory_dlq_eviction_and_retry_logs_omit_job_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eviction and retry events use static messages without job identifiers."""
    logger = MagicMock()
    monkeypatch.setattr(core_module, "logger", logger)
    dlq = DeadLetterQueue(max_size=1)

    dlq.add(_job("private-job-1"), error="Task failed (ValueError)")
    dlq.add(_job("private-job-2"), error="Task failed (ValueError)")
    assert dlq.retry("private-job-2") is not None

    logger.debug.assert_called_once_with("dlq.oldest_record_evicted")
    logger.info.assert_has_calls(
        [
            call("dlq.job_added"),
            call("dlq.job_added"),
            call("dlq.job_retry_requested"),
        ]
    )
    assert "private-job-1" not in repr(logger.mock_calls)
    assert "private-job-2" not in repr(logger.mock_calls)


@pytest.mark.asyncio
async def test_persistent_dlq_sanitizes_new_and_legacy_failure_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Writes and reads redact raw failure details from persistent DLQ records."""
    logger = MagicMock()
    monkeypatch.setattr(persistent_module, "logger", logger)
    backend = InMemoryDLQBackend()
    dlq = PersistentDeadLetterQueue(backend=backend)
    job = _job("private-persistent-job")

    await dlq.add(job, error=_PRIVATE_ERROR, traceback=_PRIVATE_TRACEBACK)
    stored = await backend.get(job.id)
    assert stored is not None
    assert stored["error"] == "Task failed"
    assert stored["traceback"] is None
    assert _PRIVATE_ERROR not in repr(stored)
    assert _PRIVATE_TRACEBACK not in repr(stored)

    # Records written by an older version may still contain arbitrary text.
    legacy = FailureRecord(
        job=_job("legacy-private-job"), error="safe placeholder"
    ).to_dict()
    legacy["error"] = _PRIVATE_ERROR
    legacy["traceback"] = _PRIVATE_TRACEBACK
    await backend.add("legacy-private-job", legacy)

    listed = await dlq.list_failed()
    legacy_result = next(item for item in listed if item["job_id"] == job.id)
    assert legacy_result["error"] == "Task failed"
    assert legacy_result["traceback"] is None
    assert _PRIVATE_ERROR not in repr(listed)
    assert _PRIVATE_TRACEBACK not in repr(listed)

    loaded = await dlq.get("legacy-private-job")
    assert loaded is not None
    assert loaded.error == "Task failed"
    assert loaded.traceback is None

    logger.info.assert_called_once_with("persistent_dlq.job_added")
    assert "private-persistent-job" not in repr(logger.mock_calls)
    assert "private-user-task" not in repr(logger.mock_calls)
    assert _PRIVATE_ERROR not in repr(logger.mock_calls)
