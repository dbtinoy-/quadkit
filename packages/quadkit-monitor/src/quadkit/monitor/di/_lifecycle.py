"""Boot, shutdown, and health-check methods."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.core import (
    HookRegistryProtocol,
)
from quadkit.contracts.exceptions.container import ContainerError
from quadkit.contracts.observability.metrics import (
    MetricsCollectorProtocol as MetricsCollectorProtocol,
)
from quadkit.contracts.observability.tracing import (
    TracerProtocol as TracerProtocol,
)
from quadkit.logging import get_logger
from quadkit.monitor.di._attrs import _MonitorAttrsMixin
from quadkit.monitor.health import HealthCheckerRegistry

if TYPE_CHECKING:
    from quadkit.contracts import BootContainerProtocol

logger = get_logger(__name__)

_HOOK_PACKAGE_BY_NAME = {
    "cache.hit": "cache",
    "cache.miss": "cache",
    "cache.evicted": "cache",
    "event.published": "events",
    "event.handled": "events",
    "connection.acquired": "sql",
    "transaction.begin": "sql",
    "transaction.end": "sql",
    "request.received": "web",
    "response.prepared": "web",
    "server.started": "web",
    "server.stopped": "web",
    "auth.login": "auth",
    "auth.logout": "auth",
    "token.refreshed": "auth",
    "message.published": "queue",
    "message.consumed": "queue",
    "task.queued": "tasks",
    "task.completed": "tasks",
    "task.failed": "tasks",
}
_HOOK_EVENT_COUNTER_NAME = "quadkit_hook_events_total"


class _MonitorLifecycleMixin(_MonitorAttrsMixin):
    """See :class:`MonitorProvider`."""

    async def boot(self, container: BootContainerProtocol) -> None:
        """Start the monitoring provider and wire the observability facade.

        After all providers are registered the container graph is complete,
        so this is the correct place to resolve optional cross-provider
        dependencies such as the database exporter.
        """
        await self.backend.initialize()

        # Optional external error tracking (Sentry). No-op unless a DSN is
        # configured (QK_MONITOR__ERROR_TRACKING__DSN).
        error_tracking_cfg = getattr(self._config, "error_tracking", None)
        if error_tracking_cfg is not None:
            from quadkit.monitor.error_tracking import (
                NullErrorTracker,
                setup_error_tracking,
            )

            self._error_tracker = setup_error_tracking(error_tracking_cfg)
            if not isinstance(self._error_tracker, NullErrorTracker):
                from quadkit.monitor.error_tracking import (
                    install_unhandled_exception_hook,
                )

                self._error_hook = install_unhandled_exception_hook(self._error_tracker)
                logger.info(
                    "error_tracking_enabled",
                    provider=type(self._error_tracker).__name__,
                )

        # M-05: If the backend exposes a real tracer (e.g. OpenTelemetryBackend after
        # initialize()), use it so @traced decorators go through the real OTel pipeline.
        backend_tracer = getattr(self.backend, "tracer", None)
        if backend_tracer is not None:
            self.tracer = backend_tracer
            logger.info(
                "tracer_wired_from_backend", backend=type(self.backend).__name__
            )

        hook_registry = await container.resolve_optional(HookRegistryProtocol)
        if hook_registry is not None:
            self._register_hook_subscriptions(hook_registry)

        # Wire DB-backed metrics exporter when Prometheus + store_in_db is configured
        # and no exporter was supplied at construction time.
        if (
            self._config
            and getattr(self._config, "prometheus", None)
            and getattr(self._config.prometheus, "store_in_db", False)
            and self.metrics_exporter is None
        ):
            # contracts must always be importable
            from quadkit.contracts.data import DatabaseProviderProtocol
            from quadkit.monitor.backends.db_exporter import DBMetricsExporter

            try:
                db = await container.resolve(DatabaseProviderProtocol)
            except Exception:  # noqa: BLE001 — optional DB metrics exporter wiring degrades on any resolution failure (not registered containers raise UnresolvableDependencyError, not KeyError)
                logger.warning(
                    "db_metrics_exporter_skipped",
                    reason="DatabaseService not registered; DB metrics storage unavailable",
                )
            else:
                db_exporter = DBMetricsExporter(
                    db,
                    table=self._config.prometheus.metrics_table,
                )
                cast("Any", container).singleton("MetricsExporter", lambda: db_exporter)
                self.metrics_exporter = db_exporter
                logger.info(
                    "db_metrics_exporter_registered",
                    table=self._config.prometheus.metrics_table,
                )

        # Create default request metrics.
        self.metrics_collector.create_counter(
            "quadkit_requests_total",
            "Total number of requests",
        )
        self.metrics_collector.create_gauge(
            "quadkit_active_connections",
            "Number of active connections",
        )
        self.metrics_collector.create_histogram(
            "quadkit_request_duration_seconds",
            "Request duration in seconds",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        )

        # Resolve and store the HealthCheckerRegistry for use in shutdown()
        with contextlib.suppress(RuntimeError, KeyError, AttributeError, TypeError):
            self._health_checker_registry = await container.resolve(
                HealthCheckerRegistry
            )

        # Start SLO evaluation worker if enabled.
        if (
            self._config
            and getattr(self._config, "slo", None)
            and self._config.slo.enabled
        ):
            from quadkit.contracts.infra.tasks import TaskManagerProtocol
            from quadkit.contracts.observability.metrics import (
                AlertDispatcherProtocol,
            )
            from quadkit.monitor.slo.monitor import SLOMonitor
            from quadkit.monitor.slo.worker import SLOEvaluationWorker

            slo_cfg = self._config.slo
            dispatcher: AlertDispatcherProtocol | None = None
            try:
                dispatcher = await container.resolve(AlertDispatcherProtocol)
            except ContainerError:
                logger.warning(
                    "alert_dispatcher_not_registered",
                    detail="AlertDispatcherProtocol not in container; SLO worker runs without alert dispatch",
                )

            monitor = SLOMonitor(
                alert_dispatcher=dispatcher,
                suppression_window_seconds=slo_cfg.suppression_window_seconds,
            )
            # MonitorModule.with_slo() declares SLOMonitor and
            # SLOEvaluationWorker in its exports=[...] list. register()
            # pre-binds lazy factories (self._resolve_slo_monitor /
            # self._resolve_slo_worker) for both so the container has a
            # key for them; store the real instances here as soon as
            # they exist so those factories have something to return.
            self._slo_monitor = monitor
            task_mgr = await container.resolve_optional(TaskManagerProtocol)
            if task_mgr is None:
                logger.warning(
                    "slo_worker_skipped",
                    detail="TaskManagerProtocol not registered; SLO worker not started",
                )
            else:
                worker = SLOEvaluationWorker(
                    task_manager=task_mgr,
                    monitor=monitor,
                    evaluation_interval=slo_cfg.evaluation_interval,
                    initial_delay_seconds=5.0,
                )
                await worker.start()
                self._slo_worker = worker

        # Start the weekly-digest flush worker if a WeeklyDigestDispatcher
        # is registered in the container.  Without this worker the digest
        # buffer accumulates forever.
        from quadkit.monitor.alerts.channels.weekly_digest import (
            WeeklyDigestDispatcher,
        )

        try:
            digest_dispatcher = await container.resolve(WeeklyDigestDispatcher)
        except ContainerError:
            digest_dispatcher = None

        if digest_dispatcher is not None:
            from quadkit.contracts.infra.tasks import TaskManagerProtocol
            from quadkit.monitor.alerts.digest_worker import (
                WeeklyDigestFlushWorker,
            )

            digest_task_mgr = await container.resolve(TaskManagerProtocol)
            digest_worker = WeeklyDigestFlushWorker(
                task_manager=digest_task_mgr,
                dispatcher=digest_dispatcher,
            )
            await digest_worker.start()
            self._digest_worker = digest_worker
            logger.info(
                "weekly_digest_flush_worker_started",
                interval_seconds=digest_worker.interval_seconds,
            )

    def _resolve_slo_monitor(self) -> Any:
        """Return the SLOMonitor assembled during boot().

        Raises:
            RuntimeError: If called before boot() has created it (e.g. SLO
                is disabled or boot() has not yet run).
        """
        if self._slo_monitor is None:
            raise RuntimeError(
                "SLOMonitor resolved before MonitorProvider.boot() completed, "
                "or MonitorConfig.slo.enabled is False."
            )
        return self._slo_monitor

    def _resolve_slo_worker(self) -> Any:
        """Return the SLOEvaluationWorker assembled during boot().

        Raises:
            RuntimeError: If called before boot() has started it (e.g. no
                TaskManagerProtocol was registered, SLO is disabled, or
                boot() has not yet run).
        """
        if self._slo_worker is None:
            raise RuntimeError(
                "SLOEvaluationWorker resolved before MonitorProvider.boot() "
                "started it — this requires MonitorConfig.slo.enabled=True "
                "and a registered TaskManagerProtocol."
            )
        return self._slo_worker

    async def shutdown(self) -> None:
        """Shutdown the monitoring provider"""
        if self._hook_registry is not None:
            for hook_name, handler in self._hook_handlers:
                self._hook_registry.unregister_action(hook_name, handler)
            self._hook_handlers.clear()
            self._hook_registry = None

        await self.backend.shutdown()

        # Stop SLO evaluation worker if running.
        if self._slo_worker is not None:
            with contextlib.suppress(RuntimeError, Exception):
                await self._slo_worker.stop()

        # Stop weekly-digest flush worker if running.  The worker emits one
        # final flush on stop so accumulated entries aren't lost on shutdown.
        if self._digest_worker is not None:
            with contextlib.suppress(RuntimeError, Exception):
                await self._digest_worker.stop()

        # Cleanup health checker registry
        if self._health_checker_registry is not None:
            try:
                await self._health_checker_registry.cleanup()
            except (RuntimeError, KeyError, AttributeError, ImportError):
                # If cleanup fails, skip
                pass

        # Flush pending error-tracking events on shutdown.
        if self._error_tracker is not None:
            with contextlib.suppress(RuntimeError, Exception):
                self._error_tracker.flush()

        # Uninstall the unhandled-exception hook if one was installed.
        if self._error_hook is not None:
            with contextlib.suppress(RuntimeError, Exception):
                self._error_hook.uninstall()
