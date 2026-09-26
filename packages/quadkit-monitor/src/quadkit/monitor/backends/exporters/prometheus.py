"""Prometheus-based MetricsExporter implementation.

This module contains the implementation that was previously exposed directly
from the ``exporters`` package root.  It is split out to honour the
rule that ``__init__.py`` only exports symbols.
"""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)

# Optional import of prometheus_client
PromCounter: Any = None
PromGauge: Any = None
PromHistogram: Any = None
CollectorRegistry: Any = None
HAS_PROMETHEUS = False
try:
    from prometheus_client import CollectorRegistry as _CR  # noqa: N814
    from prometheus_client import Counter as _PC  # noqa: N814
    from prometheus_client import Gauge as _PG  # noqa: N814
    from prometheus_client import Histogram as _PH  # noqa: N814

    CollectorRegistry = _CR
    PromCounter = _PC
    PromGauge = _PG
    PromHistogram = _PH
    HAS_PROMETHEUS = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_PROMETHEUS = False


class PrometheusMetricsExporter:
    """Async-compatible adapter for prometheus_client.

    Wraps ``prometheus_client.Counter``, ``Gauge``, and ``Histogram`` objects
    with a thread-safe, async-friendly API.  Blocking calls are offloaded to a
    thread pool via ``asyncio.to_thread`` so the event loop is never stalled.

    Label schemas for each metric name are locked-in on first use; subsequent
    calls must supply the same label keys.  If a call omits a previously-seen
    label key the value defaults to an empty string so the series is still
    valid.

    A Prometheus-client ASGI application (``/metrics`` endpoint) is
    available via :attr:`metrics_app`.  Mount it in your web application::

        # Inside a WebProvider or application startup
        metrics_route = await container.resolve("prometheus_metrics_app")
        app.mount("/metrics", metrics_route)

    Args:
        registry: Optional custom ``CollectorRegistry``.  Defaults to a fresh
            isolated registry so multiple exporters in the same process do not
            collide.
    """

    def __init__(self, registry: Any = None) -> None:
        if not HAS_PROMETHEUS:
            raise RuntimeError("prometheus-client is required for Prometheus exporter")
        import threading

        self._registry: Any = registry if registry is not None else CollectorRegistry()
        self._metrics: dict[str, Any] = {}
        # Maps metric name → frozenset of known label keys so we can detect
        # schema drift and back-fill missing labels with empty strings.
        self._label_schemas: dict[str, frozenset[str]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # ASGI /metrics endpoint
    # ------------------------------------------------------------------

    @property
    def metrics_app(self) -> Any:
        """ASGI application that exposes the Prometheus /metrics endpoint.

        Returns:
            An ASGI-compatible callable (from ``prometheus_client.make_asgi_app``).

        Raises:
            RuntimeError: If ``prometheus-client`` is not installed.
        """
        from prometheus_client import make_asgi_app

        return make_asgi_app(registry=self._registry)

    # ------------------------------------------------------------------
    # Public MetricsExporter interface
    # ------------------------------------------------------------------

    async def counter(
        self, name: str, value: int, tags: dict[str, str] | None = None
    ) -> None:
        """Increment a counter by *value*.

        Args:
            name: MetricProtocol name.
            value: Amount to increment.
            tags: Label key/value pairs.
        """
        await asyncio.to_thread(self._inc, name, value, tags)

    async def gauge(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Set a gauge to *value*.

        Args:
            name: MetricProtocol name.
            value: New gauge value.
            tags: Label key/value pairs.
        """
        await asyncio.to_thread(self._set_gauge, name, value, tags)

    async def histogram(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Observe *value* on a histogram.

        Args:
            name: MetricProtocol name.
            value: Observation value.
            tags: Label key/value pairs.
        """
        await asyncio.to_thread(self._observe, name, value, tags)

    async def flush(self) -> None:
        """No-op — prometheus_client pushes are pull-based."""
        return

    # ------------------------------------------------------------------
    # Thread-safe metric registration helpers
    # ------------------------------------------------------------------

    def _normalise_labels(
        self, name: str, tags: dict[str, str] | None
    ) -> dict[str, str]:
        """Return a labels dict that is compatible with the registered schema.

        If *name* has not been seen before the current *tags* define the label
        schema.  On subsequent calls any missing keys are backfilled with ``""``
        so the series is always valid.

        Args:
            name: MetricProtocol name.
            tags: Raw label key/value dict (may be ``None``).

        Returns:
            A dict that matches the registered schema for *name*.
        """
        tags = dict(tags) if tags else {}
        with self._lock:
            if name not in self._label_schemas:
                self._label_schemas[name] = frozenset(tags.keys())
            else:
                # Back-fill any label keys present in the schema but absent in
                # this call so prometheus_client does not raise.
                for key in self._label_schemas[name]:
                    tags.setdefault(key, "")
        return tags

    def _get_or_create(
        self,
        name: str,
        metric_type: str,
        labels: dict[str, str],
    ) -> Any:
        """Return (or create) the prometheus_client metric object for *name*.

        Thread-safe via ``self._lock``.  The metric is created once with the
        label names derived from *labels*.

        Args:
            name: MetricProtocol name (used as both the Prometheus metric name and dict key).
            metric_type: One of ``"counter"``, ``"gauge"``, ``"histogram"``.
            labels: Label key/value pairs for this observation.

        Returns:
            The underlying prometheus_client metric object.
        """
        with self._lock:
            if name not in self._metrics:
                label_names = sorted(labels.keys())
                description = f"{metric_type.capitalize()}: {name}"
                creator = {
                    "counter": PromCounter,
                    "gauge": PromGauge,
                    "histogram": PromHistogram,
                }.get(metric_type, PromCounter)
                self._metrics[name] = creator(
                    name,
                    description,
                    labelnames=label_names,
                    registry=self._registry,
                )
            return self._metrics[name]

    def _inc(self, name: str, value: int, tags: dict[str, str] | None) -> None:
        labels = self._normalise_labels(name, tags)
        try:
            metric = self._get_or_create(name, "counter", labels)
            metric.labels(**labels).inc(value)
        except Exception as e:  # noqa: BLE001 — metric recording must never raise into the app
            logger.debug("prometheus_counter_inc_failed name=%s error=%s", name, e)

    def _set_gauge(self, name: str, value: float, tags: dict[str, str] | None) -> None:
        labels = self._normalise_labels(name, tags)
        try:
            metric = self._get_or_create(name, "gauge", labels)
            metric.labels(**labels).set(value)
        except Exception as e:  # noqa: BLE001 — metric recording must never raise into the app
            logger.debug("prometheus_gauge_set_failed name=%s error=%s", name, e)

    def _observe(self, name: str, value: float, tags: dict[str, str] | None) -> None:
        labels = self._normalise_labels(name, tags)
        try:
            metric = self._get_or_create(name, "histogram", labels)
            metric.labels(**labels).observe(value)
        except Exception as e:  # noqa: BLE001 — metric recording must never raise into the app
            logger.debug(
                "prometheus_histogram_observe_failed name=%s error=%s", name, e
            )
