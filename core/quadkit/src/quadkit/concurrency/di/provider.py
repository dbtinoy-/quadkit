from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.concurrency.config import ConcurrencyConfig
from quadkit.concurrency.executors.dispatcher import DispatcherImpl
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.di.provider import Provider, ProviderPriority

if TYPE_CHECKING:
    from quadkit.contracts.core import TaskManagerProtocol


class ConcurrencyProvider(Provider):
    """Registers concurrency utilities: Dispatcher and TaskManager."""

    name = "concurrency"
    priority = ProviderPriority.INFRASTRUCTURE

    def __init__(self, config: ConcurrencyConfig | None = None) -> None:
        super().__init__()
        self._concurrency_config = config
        self._dispatcher: DispatcherImpl | None = None
        self._task_manager: TaskManagerProtocol | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register concurrency services."""
        from quadkit.concurrency.config import DispatcherConfig, ThreadPoolConfig
        from quadkit.concurrency.executors.task_manager import TaskManager
        from quadkit.contracts.core import (
            DispatcherProtocol,
            TaskManagerProtocol,
        )

        cfg: ConcurrencyConfig = self._concurrency_config or ConcurrencyConfig()
        dispatcher_config = DispatcherConfig(
            io_pool=ThreadPoolConfig(max_workers=cfg.worker_threads),
        )
        self._dispatcher = DispatcherImpl(dispatcher_config)
        container.singleton(DispatcherImpl, self._dispatcher)
        container.singleton(DispatcherProtocol, self._dispatcher)

        self._task_manager = TaskManager()
        container.singleton(TaskManager, self._task_manager)
        container.singleton(TaskManagerProtocol, self._task_manager)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Apply ConcurrencyConfig settings at boot.

        Wires ``default_channel_capacity`` into :class:`BoundedChannel`'s
        default (channels created without an explicit capacity).
        """
        from quadkit.concurrency.channels import BoundedChannel

        cfg: ConcurrencyConfig = self._concurrency_config or ConcurrencyConfig()
        BoundedChannel.configure(cfg.default_channel_capacity)

    async def shutdown(self) -> None:
        """Gracefully shutdown managed concurrency services."""
        if self._task_manager is not None:
            await self._task_manager.shutdown_gracefully()
        if self._dispatcher is not None:
            cfg = self._concurrency_config or ConcurrencyConfig()
            await self._dispatcher.shutdown(
                wait=True,
                drain=True,
                drain_timeout=cfg.dispatcher_shutdown_timeout,
            )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Health check — always healthy (in-process only, no external backend).

        Args:
            timeout: Ignored for in-process providers.

        Returns:
            Always HEALTHY — no external backend to check.
        """
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"status": "operational"},
        )


__all__ = ["ConcurrencyProvider"]
