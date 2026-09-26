from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.core import HookRegistryProtocol
from quadkit.hooks.registry import HookRegistry
from quadkit.monitor.di.provider import MonitorProvider
from quadkit.monitor.tracing import InMemoryTraceProvider

_EXPECTED_HOOKS = {
    "auth.login",
    "auth.logout",
    "cache.evicted",
    "cache.hit",
    "cache.miss",
    "connection.acquired",
    "event.handled",
    "event.published",
    "message.consumed",
    "message.published",
    "request.received",
    "response.prepared",
    "server.started",
    "server.stopped",
    "task.completed",
    "task.failed",
    "task.queued",
    "token.refreshed",
    "transaction.begin",
    "transaction.end",
}


class _RecordingHooks:
    def __init__(self) -> None:
        self.registered: list[tuple[str, Any]] = []
        self.unregistered: list[tuple[str, Any]] = []

    def register_action(
        self,
        hook_name: str,
        handler: Any,
        priority: int = 100,
        *,
        once: bool = False,
    ) -> None:
        _ = (priority, once)
        self.registered.append((hook_name, handler))

    def register_filter(
        self,
        hook_name: str,
        handler: Any,
        priority: int = 100,
        *,
        once: bool = False,
    ) -> None:
        raise NotImplementedError

    def unregister_action(self, hook_name: str, handler: Any) -> bool:
        self.unregistered.append((hook_name, handler))
        return True

    def unregister_filter(self, hook_name: str, handler: Any) -> bool:
        raise NotImplementedError

    async def call_action(self, hook_name: str, **kwargs: Any) -> None:
        raise NotImplementedError

    async def apply_filter(self, hook_name: str, value: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def has_action(self, hook_name: str) -> bool:
        return any(registered == hook_name for registered, _ in self.registered)

    def has_filter(self, hook_name: str) -> bool:
        raise NotImplementedError

    def clear(self, hook_name: str | None = None) -> None:
        _ = hook_name
        self.registered.clear()
        self.unregistered.clear()


class _HookingContainer:
    def __init__(self, hooks: HookRegistryProtocol | None) -> None:
        self._hooks = hooks

    async def resolve_optional(self, contract: type[object]) -> object | None:
        if contract is HookRegistryProtocol:
            return self._hooks
        return None

    async def resolve(self, contract: type[object]) -> object | None:
        _ = contract
        return None


class _Backend:
    def __init__(self, *, tracer: object | None = None) -> None:
        self.initialize = AsyncMock()
        self.shutdown = AsyncMock()
        self.tracer = tracer


@dataclass(frozen=True)
class _RequestReceivedPayload:
    method: str
    path: str


@pytest.mark.asyncio
async def test_boot_registers_all_monitor_hook_subscriptions_and_shutdown_unregisters_them() -> (
    None
):
    hooks = _RecordingHooks()
    provider = MonitorProvider(_Backend())

    await provider.boot(_HookingContainer(hooks))

    assert {hook_name for hook_name, _ in hooks.registered} == _EXPECTED_HOOKS

    await provider.shutdown()

    assert {hook_name for hook_name, _ in hooks.unregistered} == _EXPECTED_HOOKS


@pytest.mark.asyncio
async def test_request_hook_records_metrics_and_traces() -> None:
    hooks = HookRegistry("monitor-tests")
    backend_tracer = InMemoryTraceProvider(service_name="monitor-hooks").tracer
    provider = MonitorProvider(_Backend(tracer=backend_tracer))

    await provider.boot(_HookingContainer(hooks))
    await hooks.call_action(
        "request.received",
        payload=_RequestReceivedPayload(method="GET", path="/pets"),
    )

    metric = provider.metrics_collector.get_metric("quadkit_hook_events_total")

    assert metric is not None
    assert metric.get_count() == 1
    assert metric._values[-1].labels == {
        "hook": "request.received",
        "package": "web",
    }

    assert provider.tracer is backend_tracer
    span = provider.tracer.get_all_spans()[-1]
    assert span.name == "hook.request.received"
    assert span.attributes["quadkit.hook.name"] == "request.received"
    assert span.attributes["quadkit.hook.package"] == "web"
    assert span.attributes["payload.method"] == "GET"
    assert span.attributes["payload.path"] == "/pets"


@pytest.mark.asyncio
async def test_boot_without_hook_registry_remains_optional() -> None:
    backend = _Backend()
    provider = MonitorProvider(backend)

    await provider.boot(_HookingContainer(None))

    backend.initialize.assert_awaited_once()
