"""Task manager with idempotency key support.

Prevents duplicate task execution using idempotency keys.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import hashlib
from typing import Any
import uuid

from quadkit.contracts.core.idempotency import IdempotencyStoreProtocol
from quadkit.contracts.exceptions import IdempotencyStoreError
from quadkit.contracts.infra.tasks import (
    IdempotencyManagerProtocol,
    IdempotencyResult,
    IdempotencyResultStatus,
    IdempotentTaskManagerProtocol,
    TaskQueueProtocol,
)
from quadkit.di.decorators import inject
from quadkit.logging import get_logger
from quadkit.result import Result
from quadkit.serialization import dumps_str
from quadkit.tasks.models.job import JobProtocol

logger = get_logger(__name__)


@inject
class IdempotencyManager(IdempotencyManagerProtocol):
    """Manages task idempotency keys.

    Stores submitted tasks and their results to detect duplicates.
    """

    def __init__(
        self,
        storage: IdempotencyStoreProtocol,
        ttl: int = 86400,  # 24 hours
    ) -> None:
        """Initialize idempotency manager.

        Args:
            storage: Storage backend for idempotency keys, resolved via DI.
            ttl: How long to keep idempotency records (seconds)
        """
        self._storage = storage
        self._ttl = ttl

    def generate_key(
        self,
        task_name: str,
        params: dict[str, Any],
        client_key: str | None = None,
    ) -> str:
        """Generate idempotency key from task parameters.

        Args:
            task_name: Task name
            params: Task parameters
            client_key: Optional client-provided key

        Returns:
            Idempotency key

        Example:
            >>> key = manager.generate_key(
            ...     "process_payment",
            ...     {"order_id": "123", "amount": 100}
            ... )
            >>> # Same params = same key
            >>> key2 = manager.generate_key(
            ...     "process_payment",
            ...     {"order_id": "123", "amount": 100}
            ... )
            >>> assert key == key2
        """
        if client_key:
            # Use client-provided key
            return f"idempotency:{client_key}"

        # Generate from task name + params
        # Sort params for consistent hashing
        canonical = dumps_str(
            {"task": task_name, "params": params},
            sort_keys=True,
            separators=(",", ":"),
        )

        hash_digest = hashlib.sha256(canonical.encode()).hexdigest()

        return f"idempotency:{task_name}:{hash_digest[:16]}"

    async def _get_existing(self, idempotency_key: str) -> Any:
        """Fetch the stored record for a key, raising on storage failure.

        Args:
            idempotency_key: Idempotency key to look up.

        Returns:
            The stored record (any shape the store persists), or ``None``
            when the key is not present or expired.

        Raises:
            IdempotencyStoreError: If the store reports a lookup failure —
            a failed lookup is never treated as "no duplicate".
        """
        existing_result: Any = await self._storage.get(idempotency_key)
        if isinstance(existing_result, Result):
            if existing_result.is_err():
                raise IdempotencyStoreError(
                    f"Idempotency store lookup failed for key {idempotency_key!r}"
                ) from existing_result.unwrap_err()
            return existing_result.unwrap()
        return existing_result

    async def check_duplicate(
        self,
        idempotency_key: str,
    ) -> IdempotencyResult | None:
        """Check if task with this key was already submitted.

        Args:
            idempotency_key: Idempotency key to check

        Returns:
            Previous task result if duplicate, None if new

        Raises:
            IdempotencyStoreError: If the idempotency store lookup fails.
        """
        # Check storage for existing task
        existing = await self._get_existing(idempotency_key)

        if existing:
            logger.info(
                "Duplicate task detected: %s. Returning previous result.",
                idempotency_key,
            )
            return IdempotencyResult(
                task_id=existing["task_id"],
                idempotency_key=existing["idempotency_key"],
                status=IdempotencyResultStatus(existing["status"]),
                created_at=datetime.fromisoformat(existing["created_at"]),
                result=existing.get("result"),
            )

        return None

    async def record_submission(
        self,
        idempotency_key: str,
        task_id: str,
        task_name: str,
        params: dict[str, Any],
    ) -> None:
        """Record task submission.

        Args:
            idempotency_key: Idempotency key
            task_id: Task ID
            task_name: Task name
            params: Task parameters
        """
        record = {
            "task_id": task_id,
            "idempotency_key": idempotency_key,
            "task_name": task_name,
            "params": params,
            "status": "submitted",
            "created_at": datetime.now(UTC).isoformat(),
            "result": None,
        }

        # Store with TTL
        await self._storage.set(
            idempotency_key,
            record,
            ttl=float(self._ttl),
        )

        logger.debug("Recorded task submission: %s", idempotency_key)

    async def record_completion(
        self,
        idempotency_key: str,
        result: Any,
    ) -> None:
        """Record task completion result.

        Args:
            idempotency_key: Idempotency key
            result: Task result

        Raises:
            IdempotencyStoreError: If the idempotency store lookup fails.
        """
        # Update existing record
        existing = await self._get_existing(idempotency_key)

        if existing:
            existing["status"] = "completed"
            existing["result"] = result
            existing["completed_at"] = datetime.now(UTC).isoformat()

            await self._storage.set(
                idempotency_key,
                existing,
                ttl=float(self._ttl),
            )

            logger.debug("Recorded task completion: %s", idempotency_key)


@inject
class IdempotentTaskManager(IdempotentTaskManagerProtocol):
    """Task manager with idempotency support."""

    def __init__(
        self,
        queue_client: TaskQueueProtocol,
        idempotency_manager: IdempotencyManagerProtocol,
    ) -> None:
        """Initialize task manager.

        Args:
            queue_client: Task queue client
            idempotency_manager: Idempotency manager
        """
        self._queue = queue_client
        self._idempotency = idempotency_manager
        self._submission_locks: dict[str, asyncio.Lock] = {}

    def _get_submission_lock(self, key: str) -> asyncio.Lock:
        """Return a per-key lock, creating it on first access."""
        if key not in self._submission_locks:
            self._submission_locks[key] = asyncio.Lock()
        return self._submission_locks[key]

    async def submit_task(
        self,
        task_name: str,
        params: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> IdempotencyResult:
        """Submit task with idempotency protection.

        If a task with the same idempotency key was already submitted,
        returns the previous task result instead of creating a duplicate.

        Args:
            task_name: Task name
            params: Task parameters
            idempotency_key: Optional client-provided idempotency key

        Returns:
            Task result (new or duplicate)

        Example:
            >>> # First submission
            >>> result1 = await manager.submit_task(
            ...     "send_email",
            ...     {"to": "user@example.com", "subject": "Hello"}
            ... )
            >>> print(result1.status)  # "submitted"
            >>>
            >>> # Duplicate submission (same params)
            >>> result2 = await manager.submit_task(
            ...     "send_email",
            ...     {"to": "user@example.com", "subject": "Hello"}
            ... )
            >>> print(result2.status)  # "duplicate"
            >>> assert result2.task_id == result1.task_id
        """
        # Generate idempotency key
        key = self._idempotency.generate_key(task_name, params, idempotency_key)

        async with self._get_submission_lock(key):
            # Check for duplicate — inside the lock so no other coroutine can
            # slip through between check and record_submission.
            existing = await self._idempotency.check_duplicate(key)

            if existing:
                logger.info(
                    "Duplicate task '%s' detected, returning existing task %s",
                    task_name,
                    existing.task_id,
                )
                return existing

            # New task - generate ID and enqueue

            task_id = str(uuid.uuid4())

            # Create task
            task = JobProtocol(
                id=task_id,
                name=task_name,
                kwargs=params,  # Use kwargs for params
            )

            # Enqueue task
            await self._queue.enqueue(task)

            # Record submission
            await self._idempotency.record_submission(
                idempotency_key=key,
                task_id=task_id,
                task_name=task_name,
                params=params,
            )

            logger.info(
                "Submitted task '%s' with ID %s (idempotency_key=%s)",
                task_name,
                task_id,
                key,
            )

            return IdempotencyResult(
                task_id=task_id,
                idempotency_key=key,
                status=IdempotencyResultStatus.SUBMITTED,
                created_at=datetime.now(UTC),
            )

    async def complete_task(
        self,
        task_id: str,
        result: Any,
        idempotency_key: str,
    ) -> None:
        """Mark task as completed.

        Args:
            task_id: Task ID
            result: Task result
            idempotency_key: Idempotency key
        """
        await self._idempotency.record_completion(
            idempotency_key=idempotency_key,
            result=result,
        )

        logger.info("Task %s completed", task_id)


__all__ = ["IdempotencyManager", "IdempotencyResult", "IdempotentTaskManager"]
