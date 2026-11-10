"""Regression tests: SLOMonitor/SLOEvaluationWorker are resolvable via DI.

MonitorModule.with_slo() declares SLOMonitor and SLOEvaluationWorker in
its exports=[...] list, but historically the provider only ever kept
them as private instance attributes (self._slo_monitor / self._slo_worker)
without registering a container key for either — so any consumer
declaring a dependency on the exported protocol hit
UnresolvableDependencyError despite the module's own documented contract.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.infra.tasks import TaskManagerProtocol
from quadkit.di.container import Container
from quadkit.monitor.config import MonitorConfig
from quadkit.monitor.di.provider import MonitorProvider
from quadkit.monitor.slo.monitor import SLOMonitor
from quadkit.monitor.slo.worker import SLOEvaluationWorker
from quadkit.tasks.background_task_manager import BackgroundTaskManager


def _make_backend() -> MagicMock:
    backend = MagicMock()
    backend.initialize = AsyncMock()
    backend.shutdown = AsyncMock()
    return backend


@pytest.mark.asyncio
async def test_slo_monitor_and_worker_resolve_after_boot_with_task_manager():
    """Both SLOMonitor and SLOEvaluationWorker resolve when SLO is enabled."""
    config = MonitorConfig(slo={"enabled": True})
    provider = MonitorProvider(backend=_make_backend(), config=config)

    container = Container()
    task_manager = BackgroundTaskManager()
    container.singleton(TaskManagerProtocol, task_manager)

    await provider.register(container)
    await provider.boot(container)

    monitor = await container.resolve(SLOMonitor)
    assert isinstance(monitor, SLOMonitor)

    worker = await container.resolve(SLOEvaluationWorker)
    assert isinstance(worker, SLOEvaluationWorker)
    assert worker._monitor is monitor

    await provider.shutdown()
    await task_manager.shutdown()


@pytest.mark.asyncio
async def test_slo_monitor_resolves_without_task_manager():
    """SLOMonitor still resolves when no TaskManagerProtocol is registered.

    (SLOEvaluationWorker cannot start without a task manager, so it stays
    unresolvable in that case — but the monitor itself has no such
    dependency and should not be gated on it.)
    """
    config = MonitorConfig(slo={"enabled": True})
    provider = MonitorProvider(backend=_make_backend(), config=config)

    container = Container()

    await provider.register(container)
    await provider.boot(container)

    monitor = await container.resolve(SLOMonitor)
    assert isinstance(monitor, SLOMonitor)

    await provider.shutdown()


@pytest.mark.asyncio
async def test_slo_types_not_registered_when_slo_disabled():
    """No SLOMonitor/SLOEvaluationWorker container keys when SLO is disabled."""
    config = MonitorConfig(slo={"enabled": False})
    provider = MonitorProvider(backend=_make_backend(), config=config)

    container = Container()

    await provider.register(container)
    await provider.boot(container)

    assert not container.has(SLOMonitor)
    assert not container.has(SLOEvaluationWorker)

    await provider.shutdown()


@pytest.mark.asyncio
async def test_default_logging_alert_dispatcher_registered_and_overridable() -> None:
    """MonitorProvider registers LoggingAlertDispatcher by default without overriding custom bindings."""
    from quadkit.contracts.observability.metrics import AlertDispatcherProtocol
    from quadkit.monitor.alerts.alerting import LoggingAlertDispatcher

    provider = MonitorProvider(backend=_make_backend(), config=MonitorConfig())
    container = Container()
    await provider.register(container)

    resolved = await container.resolve(AlertDispatcherProtocol)
    assert isinstance(resolved, LoggingAlertDispatcher)

    # Custom binding registered beforehand wins over the default
    custom_container = Container()
    custom_dispatcher = AsyncMock(spec=AlertDispatcherProtocol)
    custom_container.singleton(AlertDispatcherProtocol, custom_dispatcher)
    custom_provider = MonitorProvider(backend=_make_backend(), config=MonitorConfig())
    await custom_provider.register(custom_container)

    assert await custom_container.resolve(AlertDispatcherProtocol) is custom_dispatcher
    await provider.shutdown()
    await custom_provider.shutdown()
