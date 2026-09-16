"""Concurrency protocol class definitions."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.core.concurrency_enums import ExecutionStrategy


@runtime_checkable
class TaskManagerProtocol(Protocol):
    """Protocol for task management with priority and tagging support."""

    def create_critical_task(
        self,
        coro: Any,
        *,
        name: str | None = None,
    ) -> Any:  # asyncio.Task[Any] in real implementation
        """Create a critical task that should complete before shutdown."""
        ...

    def create_background_task(
        self,
        coro: Any,  # Awaitable[Any] in real implementation
        *,
        name: str | None = None,
    ) -> Any:  # asyncio.Task[Any] in real implementation
        """Create a background task that can be cancelled on shutdown."""
        ...

    async def shutdown_gracefully(
        self,
        critical_timeout: float = 10.0,
        background_timeout: float = 2.0,
    ) -> None:
        """Shutdown tasks gracefully with different timeouts."""
        ...

    def get_task_counts(self) -> dict[str, int]:
        """Get current task counts for monitoring."""
        ...


@runtime_checkable
class DispatcherProtocol(Protocol):
    """Protocol for dispatching sync and async functions with automatic detection.

    Sync functions are offloaded to a thread pool with context propagation.
    Async functions run directly on the event loop.
    """

    async def run(
        self,
        func: Any,
        *args: Any,
        executor: Any | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a function, automatically choosing sync or async path.

        Args:
            func: Sync or async callable to execute.
            args: Positional arguments forwarded to func.
            executor: Optional executor override for sync functions.
            timeout: Optional per-call timeout in seconds.
            kwargs: Keyword arguments forwarded to func.

        Returns:
            The return value of func.

        Raises:
            RuntimeError: If the dispatcher is draining.
        """
        ...

    async def run_many(
        self,
        tasks: list[tuple[Any, tuple[Any, ...], dict[str, Any]]],
        concurrency: int | None = None,
        timeout: float | None = None,
    ) -> list[Any]:
        """Execute multiple functions concurrently.

        Args:
            tasks: List of (func, args, kwargs) tuples.
            concurrency: Max concurrent executions. None means unlimited.
            timeout: Per-task timeout in seconds.

        Returns:
            Results in the same order as tasks.
        """
        ...

    async def shutdown(
        self,
        wait: bool = True,
        drain: bool = False,
        drain_timeout: float | None = None,
    ) -> None:
        """Shutdown the dispatcher and release thread pools.

        Args:
            wait: Wait for running tasks to complete.
            drain: Stop accepting new tasks before shutdown.
            drain_timeout: Max seconds to wait for active tasks to drain.
        """
        ...

    @property
    def is_draining(self) -> bool:
        """True if the dispatcher is rejecting new tasks."""
        ...

    @property
    def active_task_count(self) -> int:
        """Number of currently executing tasks."""
        ...


@runtime_checkable
class ParallelProtocol(Protocol):
    """Protocol for structured parallelism with safe error handling."""

    @classmethod
    async def execute(
        cls,
        *tasks: Any,
        strategy: ExecutionStrategy = ExecutionStrategy.GATHER,
    ) -> list[Any]:
        """Execute tasks in parallel with the specified strategy."""
        ...


@runtime_checkable
class ChannelProtocol(Protocol):
    """Protocol for typed async channels providing backpressure-aware communication.

    A channel decouples producers and consumers with an optional bounded
    buffer. Closing a channel signals that no more items will be sent.
    """

    async def send(self, item: Any) -> None:
        """Send an item into the channel.

        Blocks if the channel's buffer is full until space is available.

        Args:
            item: Item to enqueue.

        Raises:
            ChannelClosedError: If the channel has already been closed.
            ChannelFullError: If the channel is bounded and at capacity
                and the caller does not wish to wait.
        """
        ...

    async def receive(self) -> Any:
        """Receive the next item from the channel.

        Blocks until an item is available or the channel is closed.

        Returns:
            The next item from the channel.

        Raises:
            ChannelClosedError: If the channel is closed and empty.
        """
        ...

    async def close(self) -> None:
        """Close the channel.

        After closing, no further items may be sent. Pending items can
        still be received until the buffer is drained.
        """
        ...

    @property
    def closed(self) -> bool:
        """True if the channel has been closed."""
        ...

    @property
    def is_empty(self) -> bool:
        """True if the channel currently has no queued items."""
        ...


__all__ = [
    "ChannelProtocol",
    "DispatcherProtocol",
    "ParallelProtocol",
    "TaskManagerProtocol",
]
