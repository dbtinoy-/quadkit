"""Full-featured monitoring and observability provider for ``quadkit-monitor``.

This module defines :class:`MonitorProvider`, which replaces the core
framework's no-op :class:`~quadkit.monitor.di.sub_providers.observability.ObservabilityProvider`
with real metric collection, distributed tracing, and health-check
infrastructure when ``quadkit-monitor`` is installed.

Relationship with ``ObservabilityProvider``
--------------------------------------------
The Quadkit core always registers
:class:`~quadkit.monitor.di.sub_providers.observability.ObservabilityProvider`
at ``ProviderPriority.INFRASTRUCTURE``.  That provider binds no-op stubs
for every observability contract so that application code compiles and runs
even without this package.

``MonitorProvider`` is constructed with an explicit priority that places it
*before* the default ``INFRASTRUCTURE`` value, meaning its ``register()``
call is executed first and its singleton bindings take precedence in the DI
container.  The net result:

* **``ObservabilityProvider``** registers no-op defaults (fallback, always
  present).
* **``MonitorProvider``** overrides those defaults with real implementations
  (active when ``quadkit-monitor`` is installed and added to the app).

Because DI container singletons are resolved in registration order and later
registrations of the same key win, ``MonitorProvider``'s higher priority
(lower numeric value) ensures its bindings are visible to all dependent
services resolved after boot.
"""

from __future__ import annotations

import contextlib
from dataclasses import asdict, is_dataclass
from typing import Any, cast

from quadkit.contracts.core import (
    HookRegistryProtocol,
    ProviderPriority,
)
from quadkit.contracts.observability.metrics import (
    MetricsBackendProtocol as MonitoringBackend,
)
from quadkit.contracts.observability.metrics import (
    MetricsCollectorProtocol as MetricsCollectorProtocol,
)
from quadkit.contracts.observability.tracing import (
    TracerProtocol as TracerProtocol,
)
from quadkit.di.provider import Provider
from quadkit.logging import get_logger
from quadkit.monitor.backends.exporters.otel_registry import (
    MetricsExporterRegistry,
    TracingExporterRegistry,
)
from quadkit.monitor.config import MonitorConfig
from quadkit.monitor.constants import DEFAULT_MAX_SPANS
from quadkit.monitor.error_tracking import ErrorTrackerProtocol
from quadkit.monitor.health import HealthCheckerRegistry
from quadkit.monitor.metrics.collector import (
    MetricsCollectorProtocol as _ConcreteMetricsCollector,
)
from quadkit.monitor.tracing import InMemoryTraceProvider

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


def _is_simple_hook_value(value: Any) -> bool:
    return value is None or isinstance(value, str | bool | int | float)


def _extract_payload_attributes(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}

    raw_payload: dict[str, Any] | None = None
    if is_dataclass(payload) and not isinstance(payload, type):
        raw_payload = asdict(payload)
    elif isinstance(payload, dict):
        raw_payload = payload
    else:
        with contextlib.suppress(TypeError):
            raw_payload = vars(payload)

    if raw_payload is None:
        return {}

    return {
        f"payload.{key}": value
        for key, value in raw_payload.items()
        if isinstance(key, str) and _is_simple_hook_value(value)
    }


from quadkit.monitor.di._lifecycle import _MonitorLifecycleMixin
from quadkit.monitor.di._metrics import _MonitorMetricsMixin
from quadkit.monitor.di._registration import _MonitorRegistrationMixin


class MonitorProvider(
    _MonitorLifecycleMixin,
    _MonitorMetricsMixin,
    _MonitorRegistrationMixin,
    Provider,
):
    """Monitoring and observability provider for Quadkit Framework"""

    name = "monitor"
    priority = ProviderPriority.INFRASTRUCTURE
    config_key: str | None = "monitor"
    config_model: type | None = MonitorConfig

    def __init__(
        self,
        backend: MonitoringBackend,
        exporter: Any | None = None,
        config: Any | None = None,
    ):
        super().__init__()
        self.backend = backend
        self.metrics_collector = _ConcreteMetricsCollector()
        # Tracing sub-objects are always composed eagerly: from the explicit
        # config when supplied, otherwise from in-memory defaults. ``register()``
        # re-composes when the orchestrator injects the yaml section (via
        # ``config_key``) so the real values win.
        self.trace_provider: Any = None
        self.tracer: Any = None
        self.metrics_exporter = exporter
        # Explicit config passed at construction; the orchestrator may inject
        # the yaml section later via ``config_key``/``config_model``, but an
        # explicit config always wins (same convention as queue/graphql/
        # secrets providers).
        self._requested_config = config
        # Exporter registries — owned by this provider, registered via DI
        self._tracing_exporter_registry = TracingExporterRegistry.with_defaults()
        self._metrics_exporter_registry = MetricsExporterRegistry.with_defaults()
        # Store config for runtime registration decisions. When explicit
        # config was supplied at construction time (``configure()`` or
        # ``create_provider_from_config``), skip the orchestrator's yaml
        # section injection in ``_inject_provider_config`` so the explicit
        # values are not overwritten by the default ``monitor`` section.
        self._config = config
        self._config_from_factory = config is not None
        self._compose_tracing()
        self._health_checker_registry: HealthCheckerRegistry | None = None
        self._hook_registry: HookRegistryProtocol | None = None
        self._hook_handlers: list[tuple[str, Any]] = []
        self._slo_monitor: Any | None = None
        self._slo_worker: Any | None = None
        self._digest_worker: Any | None = None
        self._error_tracker: ErrorTrackerProtocol | None = None
        self._error_hook: Any | None = None

    @classmethod
    def from_config(cls, config: MonitorConfig, **context: Any) -> MonitorProvider:
        """Create a MonitorProvider from config.

        Delegates to the create_provider_from_config factory.
        """
        from quadkit.monitor.di.factories import create_provider_from_config

        return create_provider_from_config(config)

    def _compose_tracing(self) -> None:
        """(Re)build the trace provider and tracer from ``self._config``.

        Called eagerly from ``__init__`` when explicit config was supplied and
        again from ``register()`` when injection arrived late (i.e.
        ``configure()`` ran with no explicit config and the orchestrator
        injected the yaml section after construction).
        """
        tracing_cfg = None
        if self._config is not None:
            tracing_cfg = getattr(self._config, "tracing", None) or {}

        # Resolve service_name and max_spans from tracing config (if present)
        service_name = None
        max_spans = None
        if tracing_cfg is not None:
            service_name = getattr(tracing_cfg, "service_name", None)
            max_spans = getattr(tracing_cfg, "max_spans", None)

        if not service_name:
            service_name = "quadkit-service"

        self.trace_provider = InMemoryTraceProvider(
            service_name=service_name,
            max_spans=max_spans or DEFAULT_MAX_SPANS,
        )
        self.tracer = self.trace_provider.tracer

    def _register_hook_subscriptions(self, hook_registry: HookRegistryProtocol) -> None:
        self._hook_registry = hook_registry
        self._ensure_hook_event_metric()

        for hook_name in _HOOK_PACKAGE_BY_NAME:
            handler = self._build_hook_handler(hook_name)
            hook_registry.register_action(hook_name, handler)
            self._hook_handlers.append((hook_name, handler))

    def _build_hook_handler(self, hook_name: str) -> Any:
        async def _handler(**kwargs: Any) -> None:
            await self._record_hook_event(hook_name, **kwargs)

        return _handler

    def _ensure_hook_event_metric(self) -> None:
        if self.metrics_collector.get_metric(_HOOK_EVENT_COUNTER_NAME) is None:
            self.metrics_collector.create_counter(
                _HOOK_EVENT_COUNTER_NAME,
                "Total number of monitor hook events",
                labels={"hook": "", "package": ""},
            )

    async def _record_hook_event(self, hook_name: str, **kwargs: Any) -> None:
        package = _HOOK_PACKAGE_BY_NAME[hook_name]
        self._ensure_hook_event_metric()

        metric = self.metrics_collector.get_metric(_HOOK_EVENT_COUNTER_NAME)
        if metric is not None:
            cast("Any", metric).increment(
                labels={
                    "hook": hook_name,
                    "package": package,
                },
            )

        span = self.tracer.start_span(
            f"hook.{hook_name}",
            attributes={
                "quadkit.hook.name": hook_name,
                "quadkit.hook.package": package,
            },
        )
        try:
            for key, value in _extract_payload_attributes(
                kwargs.get("payload")
            ).items():
                span.set_attribute(key, value)
        finally:
            if hasattr(span, "end"):
                cast("Any", span).end()
