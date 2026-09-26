"""Idempotency protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.infra.tasks.idempotency import IdempotencyResult


@runtime_checkable
class IdempotencyManagerProtocol(Protocol):
    """Manages idempotency keys for task submissions.

    Implementations (e.g. ``quadkit-tasks``
    :class:`~quadkit.tasks.execution.manager.IdempotencyManager`) generate
    deterministic keys from task parameters and detect duplicate
    submissions against an :class:`IdempotencyStoreProtocol` backend.
    """

    def generate_key(
        self,
        task_name: str,
        params: dict[str, Any],
        client_key: str | None = None,
    ) -> str:
        """Generate an idempotency key from task name and parameters.

        Args:
            task_name: Name of the task.
            params: Task parameters.
            client_key: Optional client-provided key; returned verbatim.

        Returns:
            A deterministic idempotency key.
        """
        ...

    async def check_duplicate(
        self,
        idempotency_key: str,
    ) -> IdempotencyResult | None:
        """Check whether a key was already submitted.

        Args:
            idempotency_key: The idempotency key to look up.

        Returns:
            The previous :class:`IdempotencyResult` when a duplicate exists,
            ``None`` otherwise.
        """
        ...

    async def record_submission(
        self,
        idempotency_key: str,
        task_id: str,
        task_name: str,
        params: dict[str, Any],
    ) -> None:
        """Record a task submission under *idempotency_key*."""
        ...

    async def record_completion(
        self,
        idempotency_key: str,
        result: Any,
    ) -> None:
        """Record the completion result for *idempotency_key*."""
        ...


@runtime_checkable
class IdempotentTaskManagerProtocol(Protocol):
    """Task manager with idempotency protection.

    Implementations (e.g. ``quadkit-tasks``
    :class:`~quadkit.tasks.execution.manager.IdempotentTaskManager`)
    enqueue tasks while preventing duplicate submissions under the same
    idempotency key.
    """

    async def submit_task(
        self,
        task_name: str,
        params: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> IdempotencyResult:
        """Submit a task with idempotency protection.

        Args:
            task_name: Name of the task to submit.
            params: Task parameters.
            idempotency_key: Optional client-provided idempotency key.

        Returns:
            The submission :class:`IdempotencyResult` — a duplicate
            submission returns the previously stored result.

        Example:
            ```python
            result = await manager.submit_task(
                "tts_generation",
                {"text": "hello"},
                idempotency_key="user-42:tts-1",
            )
            if result.status == "duplicate":
                print("already submitted:", result.task_id)
            ```
        """
        ...
