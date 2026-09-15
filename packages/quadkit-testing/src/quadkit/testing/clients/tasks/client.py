"""TaskTestClient: high-level helper for task-system tests.

Provides :class:`TaskTestClient` which wraps a :class:`TaskTestBed` and
exposes a fluent API for starting/stopping a mock provider, enqueueing
sample tasks, and executing individual tasks — all without a real backend.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
import uuid

from quadkit.testing.clients.tasks.data import TaskTestData
from quadkit.testing.clients.tasks.mocks import MockTaskResult, MockTasksProvider

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from quadkit.testing.clients.tasks.bed import TaskTestBed


class TaskTestClient:
    """High-level task-system test helper.

    Wraps a :class:`TaskTestBed` and provides convenience methods for
    testing the task lifecycle without a running application or external
    queue backend.

    Attributes:
        test_bed: The underlying :class:`TaskTestBed` that owns the mocks.
        provider: The currently active :class:`MockTasksProvider`, or
            ``None`` when no provider is running.

    Example:
        ```python
        bed = TaskTestBed()
        await bed.setup()

        client = TaskTestClient(bed)

        async with client.task_context() as provider:
            task_ids = await client.enqueue_test_tasks()
            ...

        await bed.teardown()
        ```
    """

    def __init__(self, test_bed: TaskTestBed) -> None:
        self.test_bed = test_bed
        self.provider: MockTasksProvider | None = None

    async def start_provider(self) -> MockTasksProvider:
        """Create and start a :class:`MockTasksProvider` bound to the test bed.

        Sets ``self.provider`` and returns the new provider so callers can
        assert on its identity.

        Returns:
            The newly created :class:`MockTasksProvider`.
        """
        queue = self.test_bed.mock_queue
        executor = self.test_bed.mock_executor
        assert queue is not None
        assert executor is not None
        provider = MockTasksProvider(queue=queue, executor=executor)
        self.provider = provider
        return provider

    async def stop_provider(self) -> None:
        """Shut down the active provider and clear ``self.provider``.

        No-op if no provider is running.
        """
        if self.provider is not None:
            await self.provider.shutdown()
            self.provider = None

    async def enqueue_test_tasks(self) -> list[str]:
        """Enqueue the three standard sample tasks into the mock queue.

        Creates :class:`~quadkit.tasks.JobProtocol` instances from
        :meth:`~quadkit.testing.clients.tasks.TaskTestData.sample_tasks` and
        enqueues them.

        Returns:
            A list of three task-id strings in enqueue order.
        """
        from quadkit.tasks import JobProtocol, Priority

        task_ids: list[str] = []
        queue = self.test_bed.mock_queue
        assert queue is not None
        for task_dict in TaskTestData.sample_tasks():
            task = JobProtocol(
                id=str(uuid.uuid4()),
                name=task_dict["name"],
                args=task_dict.get("args", ()),
                kwargs=task_dict.get("kwargs", {}),
                priority=int(Priority.NORMAL),
            )
            enqueue_result = await queue.enqueue(task)
            if enqueue_result.is_err():
                raise RuntimeError(
                    f"Failed to enqueue task '{task_dict['name']}': {enqueue_result.unwrap_err()}"
                )
            task_ids.append(enqueue_result.unwrap())
        return task_ids

    async def execute_test_task(
        self,
        task: Any,
    ) -> MockTaskResult[dict[str, Any]]:
        """Execute *task* via the mock executor.

        Args:
            task: A :class:`~quadkit.tasks.JobProtocol` (or any object compatible
                with :class:`MockTaskExecutor`).

        Returns:
            A :class:`MockTaskResult` describing the outcome.
        """
        executor = self.test_bed.mock_executor
        assert executor is not None
        return await executor.execute_task(task)

    @asynccontextmanager
    async def task_context(self) -> AsyncGenerator[MockTasksProvider, None]:
        """Async context manager that starts a provider and stops it on exit.

        Yields:
            The active :class:`MockTasksProvider`.

        Example:
            ```python
            async with client.task_context() as provider:
                assert provider is not None
            assert client.provider is None
            ```
        """
        provider = await self.start_provider()
        try:
            yield provider
        finally:
            await self.stop_provider()


__all__ = ["TaskTestClient"]
