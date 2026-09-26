from __future__ import annotations

from collections.abc import Callable
import importlib.util
import time
from typing import Any, cast

from quadkit.monitor import MetricsCollectorProtocol
from quadkit.monitor.metrics.prometheus import exporter as prometheus_exporter
from quadkit.monitor.middleware.auth import is_authorized, send_unauthorized

PROMETHEUS_AVAILABLE = importlib.util.find_spec("prometheus_client") is not None


class PrometheusMiddleware:
    """ASGI middleware that automatically collects HTTP request metrics.

    Wraps any ASGI application and records per-request counters, duration
    histograms, and an active-request gauge.  When ``prometheus_client`` is
    installed the metrics are exposed in the standard Prometheus text format at
    *path* (default ``/metrics``);
    otherwise the framework's :class:`~quadkit.monitor.metrics.collector.MetricsCollectorProtocol`
    is used so the application degrades gracefully without the optional
    dependency.

    Args:
        app: The inner ASGI application to forward non-scrape requests
            to. When ``None``, non-metrics scopes are dropped (see
            :meth:`set_next_app` for post-construction wiring).
        path: URL path at which to serve the Prometheus scrape endpoint.
            Defaults to ``"/metrics"``.
        metrics_collector: Optional pre-configured
            :class:`~quadkit.monitor.metrics.collector.MetricsCollectorProtocol`.
            A new default collector is created when ``None`` is passed.
        auth_token: Optional bearer token.  When set, requests must carry
            ``Authorization: Bearer <auth_token>`` or receive ``401``.
            Defaults to ``None`` (endpoint open).

    Example::

        from quadkit.monitor.middleware import PrometheusMiddleware

        app = PrometheusMiddleware(my_asgi_app, path="/metrics")
        # Mount *app* in your ASGI server of choice.
    """

    _next_app: Callable[..., Any] | None = None

    def __init__(
        self,
        app: Callable[..., Any] | None = None,
        path: str = "/metrics",
        metrics_collector: MetricsCollectorProtocol | None = None,
        auth_token: str | None = None,
    ):
        self._next_app = app
        self.path = path
        self.auth_token = auth_token
        self.metrics_collector = metrics_collector or MetricsCollectorProtocol()

        if PROMETHEUS_AVAILABLE:
            self._setup_prometheus_metrics()
        else:
            self._setup_metrics()

    def _setup_prometheus_metrics(self) -> None:
        self.requests_total = prometheus_exporter.get_or_create_counter(
            "http_requests_total",
            "Total number of HTTP requests",
            ["method", "endpoint", "status"],
        )
        self.request_duration = prometheus_exporter.get_or_create_histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
        )
        self.active_requests = prometheus_exporter.get_or_create_gauge(
            "quadkit_active_requests",
            "Number of active HTTP requests",
        )

    def _setup_metrics(self) -> None:
        self.metrics_collector.create_counter(
            "http_requests_total",
            "Total number of HTTP requests",
            labels={"method": "", "endpoint": "", "status": ""},
        )
        self.metrics_collector.create_histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            labels={"method": "", "endpoint": ""},
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        )
        self.metrics_collector.create_gauge(
            "quadkit_active_requests",
            "Number of active HTTP requests",
        )

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            # Observability-only middleware: forward to the inner app when
            # wired, otherwise drop the scope (never hang the connection).
            if callable(self._next_app):
                await self._next_app(scope, receive, send)
            return

        if scope["path"] == self.path and scope["method"] == "GET":
            if not is_authorized(scope, self.auth_token):
                await send_unauthorized(send)
                return
            await self._serve_metrics(send)
            return

        start_time = time.time()
        method = scope["method"]
        path = scope["path"]

        if PROMETHEUS_AVAILABLE:
            self.active_requests.inc()
        else:
            active_gauge = self.metrics_collector.get_metric("quadkit_active_requests")
            if active_gauge:
                cast("Any", active_gauge).increment()

        status_code = [200]

        async def wrapped_send(message: Any) -> Any:
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            await send(message)

        try:
            # Observability-only middleware: forward to the inner app when
            # wired, otherwise drop the scope (matches __call__ above).
            # This previously fell back to ``self.next_app``, which does not
            # exist — the attribute is ``_next_app`` — so an unwired pipeline
            # raised AttributeError instead of passing through.
            if callable(self._next_app):
                await self._next_app(scope, receive, wrapped_send)
        finally:
            if PROMETHEUS_AVAILABLE:
                self.active_requests.dec()
                self.requests_total.labels(
                    method=method,
                    endpoint=path,
                    status=str(status_code[0]),
                ).inc()
                self.request_duration.labels(method=method, endpoint=path).observe(
                    time.time() - start_time,
                )
            else:
                active_gauge = self.metrics_collector.get_metric(
                    "quadkit_active_requests"
                )
                if active_gauge:
                    cast("Any", active_gauge).decrement()

                counter = self.metrics_collector.get_metric("http_requests_total")
                if counter:
                    cast("Any", counter).increment(
                        labels={
                            "method": method,
                            "endpoint": path,
                            "status": str(status_code[0]),
                        },
                    )

                histogram = self.metrics_collector.get_metric(
                    "http_request_duration_seconds"
                )
                if histogram:
                    cast("Any", histogram).observe(
                        time.time() - start_time,
                        labels={"method": method, "endpoint": path},
                    )

    def set_next_app(self, app: Callable) -> None:
        """Wire the inner ASGI application after construction."""
        self._next_app = app

    async def _serve_metrics(self, send: Callable) -> None:
        if PROMETHEUS_AVAILABLE:
            metrics_output = prometheus_exporter.export().decode("utf-8")
            content_type = prometheus_exporter.content_type
        else:
            metrics_output = self._format_prometheus_metrics()
            content_type = "text/plain; charset=utf-8"

        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", content_type.encode()]],
            },
        )
        await send(
            {"type": "http.response.body", "body": metrics_output.encode("utf-8")},
        )

    def _format_prometheus_metrics(self) -> str:
        lines = []
        for name, metric in self.metrics_collector.get_all_metrics().items():
            lines.append(f"# HELP {name} {metric.description}")
            lines.append(f"# TYPE {name} {self._get_metric_type(metric)}")
            if hasattr(metric, "_values") and metric._values:
                # deque does not support slicing, so we get the last element manually
                last_value = metric._values[-1]
                for value in [last_value]:
                    labels_str = ""
                    if value.labels:
                        parts = [
                            f'{kv[0]}="{kv[1]}"'
                            for kv in filter(lambda kv: kv[1], value.labels.items())
                        ]
                        if parts:
                            labels_str = "{" + ",".join(parts) + "}"
                    lines.append(f"{name}{labels_str} {value.value}")
        return "\n".join(lines) + "\n"

    def _get_metric_type(self, metric: Any) -> str:
        type_name = metric.__class__.__name__.lower()
        if "counter" in type_name:
            return "counter"
        if "gauge" in type_name:
            return "gauge"
        if "histogram" in type_name:
            return "histogram"
        return "untyped"
