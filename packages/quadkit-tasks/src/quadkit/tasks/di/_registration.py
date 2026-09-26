"""Registration-phase methods."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from quadkit.contracts.admin.protocols import AdminContributorProtocol
from quadkit.contracts.infra.tasks import (
    TaskExecutorProtocol,
    TaskQueueProtocol,
)
from quadkit.logging import get_logger
from quadkit.tasks.admin.contributor import TasksAdminContributor
from quadkit.tasks.admin.handlers.avg_duration import AvgDurationWidgetHandler
from quadkit.tasks.admin.handlers.tasks_summary import TasksSummaryWidgetHandler
from quadkit.tasks.backends.registry import TaskBackendRegistry
from quadkit.tasks.config import TaskConfig
from quadkit.tasks.di._attrs import _TaskAttrsMixin
from quadkit.tasks.execution.metrics import TaskMetricsCollector
from quadkit.tasks.execution.pool import WorkerPool
from quadkit.tasks.execution.registry import HandlerRegistry
from quadkit.tasks.results.core import ResultStore
from quadkit.tasks.scheduling.scheduler import TaskScheduler

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
    )

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level helpers (no self; keep them small and testable)
# ---------------------------------------------------------------------------


class _TaskRegistrationMixin(_TaskAttrsMixin):
    """See TaskProvider."""

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register task services with the DI container.

        Args:
            container: DI registrar to bind task services into.
        """
        from quadkit.contracts.infra.tasks import TaskProviderProtocol
        from quadkit.tasks.di.provider import (
            TaskProvider,  # noqa: PLC0415 — breaks provider<->mixin cycle
        )

        self._container = container
        container.singleton(TaskProvider, lambda: self)
        container.singleton(TaskProviderProtocol, lambda: self)
        container.singleton(TaskScheduler, lambda: self.scheduler)
        container.singleton(WorkerPool, lambda: self.worker_pool)
        container.singleton(HandlerRegistry, lambda: self.registry)
        container.singleton(cast("type", TaskExecutorProtocol), lambda: self.registry)
        container.singleton(TaskBackendRegistry, lambda: self._backend_registry)
        container.singleton(TaskMetricsCollector, TaskMetricsCollector())
        # ResultStore: lambda reads self._result_store so it returns the upgraded
        # CacheBackendResultStore if one was injected during boot().
        container.singleton(cast("type", ResultStore), lambda: self._result_store)

        # Branch: multi-backend when config declares named backends; otherwise
        # fall back to the original single-backend behaviour.
        if self._config is not None and self._config.backends:
            await self._register_multi_backend(container)
        else:
            await self._register_single_backend(container)

        await self._discover_backends(container)
        await self._register_admin_widgets(container)

    async def _register_single_backend(
        self, container: ContainerRegistrarProtocol
    ) -> None:
        """Register the single primary queue (existing behaviour, preserved exactly)."""
        container.singleton(cast("type", TaskQueueProtocol), lambda: self.queue)

    async def _register_multi_backend(
        self, container: ContainerRegistrarProtocol
    ) -> None:
        """Register multiple named task queue backends.

        Each entry in ``self._config.backends`` is instantiated via the backend
        registry and registered as a named ``TaskQueueProtocol`` singleton.
        The primary backend (``primary=True`` or the first entry by identity)
        also receives the unnamed ``TaskQueueProtocol`` binding for backward
        compatibility.

        Args:
            container: DI registrar to bind task services into.
        """
        assert self._config is not None  # guarded by caller  # noqa: S101

        for entry in self._config.backends:
            backend_cfg = TaskConfig.from_named(entry)
            queue = self._backend_registry.create_backend(backend_cfg)
            self._queue_services.append((entry.name, queue))

            # Named binding — resolvable via Annotated[TaskQueueProtocol, Named(entry.name)]
            # ``*_`` absorbs the resolver argument the container passes into
            # factories; ``q=queue`` keeps the captured instance.
            container.singleton(
                cast("type", TaskQueueProtocol),
                factory=lambda *_, q=queue: q,
                name=entry.name,
            )

            # Primary backend also gets the unnamed binding for backward compat.
            # Use identity check (is), NOT equality (==).
            if entry.primary or self._config.backends[0] is entry:
                container.singleton(
                    cast("type", TaskQueueProtocol),
                    factory=lambda *_, q=queue: q,
                )

        logger.info(
            "tasks_multi_backend_registered",
            count=len(self._config.backends),
            names=[e.name for e in self._config.backends],
        )

    async def _discover_backends(self, container: ContainerRegistrarProtocol) -> None:
        """Scan the ``quadkit.tasks.backends`` entry-point group.

        Any entry point that resolves to a
        :class:`~quadkit.di.provider.Provider` subclass is instantiated
        and its :meth:`~quadkit.di.provider.Provider.register` method is
        called, allowing third-party backend packages to self-register.

        Args:
            container: The DI container registrar.
        """
        import importlib.metadata as _meta

        from quadkit.di.provider import Provider as _Provider

        eps = _meta.entry_points(group="quadkit.tasks.backends")
        for ep in eps:
            try:
                candidate = ep.load()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "tasks_ep_load_failed",
                    entry_point=ep.name,
                    error=str(exc),
                )
                continue
            if not (isinstance(candidate, type) and issubclass(candidate, _Provider)):
                logger.debug(
                    "tasks_ep_skipped",
                    entry_point=ep.name,
                    reason="not a Provider subclass",
                )
                continue
            logger.debug(
                "tasks_ep_found",
                entry_point=ep.name,
                provider=candidate.__name__,
            )
            try:
                await candidate().register(container)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "tasks_ep_register_failed",
                    entry_point=ep.name,
                    provider=candidate.__name__,
                    error=str(exc),
                )

    async def _register_admin_widgets(
        self, container: ContainerRegistrarProtocol
    ) -> None:
        """Register admin widget handlers and contributor.

        Args:
            container: The DI container registrar.
        """
        # Register handlers as transient
        container.transient(
            TasksSummaryWidgetHandler,
            factory=lambda: TasksSummaryWidgetHandler(
                queue_provider=self.queue, pool_provider=self.worker_pool
            ),
        )
        container.transient(
            AvgDurationWidgetHandler,
            factory=lambda: AvgDurationWidgetHandler(pool_provider=self.worker_pool),
        )

        # Register the contributor as singleton
        container.singleton(TasksAdminContributor, TasksAdminContributor)

        # Register contributor in admin registry
        container.singleton(
            AdminContributorProtocol,
            lambda: container.resolve(TasksAdminContributor),  # type: ignore[attr-defined]
            name="tasks",
        )

        logger.debug("tasks_admin_widgets_registered")
