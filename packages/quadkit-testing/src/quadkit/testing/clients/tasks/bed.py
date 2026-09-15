"""TaskTestBed: isolated task-system test environment.

Provides :class:`TaskTestBed` which sets up in-memory mock components
(queue + executor) and pre-populates them with sample tasks, so that
tests for the task subsystem can run without any external infrastructure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from quadkit.testing.clients.tasks.data import TaskTestData
from quadkit.testing.clients.tasks.mocks import MockTaskExecutor, MockTaskQueue
from quadkit.testing.fixtures.bed import TestEnvironment

if TYPE_CHECKING:
    # Imported lazily in create_test_client to avoid an import cycle.
    from quadkit.testing.clients.tasks.client import TaskTestClient


class TaskTestBed(TestEnvironment):
    """Test environment pre-wired with mock task queue and executor.

    Unlike the generic :class:`~quadkit.testing.fixtures.bed.TestEnvironment`,
    ``TaskTestBed`` overrides :meth:`setup` and :meth:`teardown` to manage
    the mock components directly without starting a full ``Application``.

    Attributes:
        mock_queue: In-memory ``MockTaskQueue`` instance created during setup.
        mock_executor: ``MockTaskExecutor`` instance created during setup.

    Example:
        ```python
        bed = TaskTestBed()
        await bed.setup()

        client = TaskTestClient(bed)
        task_ids = await client.enqueue_test_tasks()
        ...

        await bed.teardown()
        ```
    """

    mock_queue: MockTaskQueue | None
    mock_executor: MockTaskExecutor | None

    def __init__(self, config: Any = None) -> None:
        super().__init__()
        # Attributes are set during setup(); declare type hints here only.
        self.mock_queue = None
        self.mock_executor = None

    async def setup(self) -> None:  # type: ignore[override]
        """Initialise mock components and pre-populate the queue.

        Creates a fresh :class:`~quadkit.testing.clients.tasks.MockTaskQueue`
        and :class:`~quadkit.testing.clients.tasks.MockTaskExecutor`, then
        enqueues the three sample tasks returned by
        :meth:`~quadkit.testing.clients.tasks.TaskTestData.sample_tasks`.
        Does **not** start an ``Application`` or DI container.
        """
        from quadkit.tasks import JobProtocol, Priority

        self.mock_queue = MockTaskQueue()
        self.mock_executor = MockTaskExecutor()

        # Pre-populate queue with 3 sample tasks
        for task_dict in TaskTestData.sample_tasks():
            task = JobProtocol(
                id=str(uuid.uuid4()),
                name=task_dict["name"],
                args=task_dict.get("args", ()),
                kwargs=task_dict.get("kwargs", {}),
                priority=int(Priority.NORMAL),
            )
            await self.mock_queue.enqueue(task)

    async def teardown(self) -> None:
        """Clear the mock queue and reset state.

        Safe to call even if :meth:`setup` was never called.
        """
        if self.mock_queue is not None:
            await self.mock_queue.clear_queue()
        self.mock_queue = None
        self.mock_executor = None

    def get_enqueued_tasks(self) -> list[Any]:
        """Return all tasks currently waiting in the mock queue.

        Returns:
            A list of :class:`~quadkit.tasks.JobProtocol` objects, in enqueue order.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if self.mock_queue is None:
            msg = "TaskTestBed is not set up yet. Call await bed.setup() first."
            raise RuntimeError(msg)
        return self.mock_queue.get_all()

    def create_test_client(self) -> TaskTestClient:
        """Create a :class:`TaskTestClient` bound to this bed.

        Returns:
            A new :class:`~quadkit.testing.clients.tasks.TaskTestClient`
            wired to this bed's mock queue and executor.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if self.mock_queue is None:
            msg = "TaskTestBed is not set up yet. Call await bed.setup() first."
            raise RuntimeError(msg)
        from quadkit.testing.clients.tasks.client import TaskTestClient

        return TaskTestClient(self)


__all__ = ["TaskTestBed"]
