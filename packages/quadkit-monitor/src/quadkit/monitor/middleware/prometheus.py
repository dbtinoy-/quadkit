from __future__ import annotations

from collections.abc import Callable
import importlib.util
import time
from typing import Any, cast

from quadkit.monitor import MetricsCollectorProtocol
from quadkit.monitor.metrics.collector import get_default_collector
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
            When ``None`` the process-wide collector is used (the one the
            monitor provider binds into DI), so middleware- and
            service-recorded metrics land in the same place.
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
        self.metrics_collector = metrics_collector or get_default_collector()

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
        self.request_errors = prometheus_exporter.get_or_create_counter(
            "http_request_errors_total",
            "HTTP requests that failed with a 4xx or 5xx status",
            ["method", "endpoint", "status_class"],
        )

    def _setup_metrics(self) -> None:
        """Declare this middleware's collector series, once.

        ``MetricsCollectorProtocol.create_*`` overwrites whatever is registered
        under the name, so an app that already records ``http_requests_total``
        through another middleware (``quadkit.web.middleware.metrics``, for
        example) would silently lose its label schema — and every series
        recorded so far — the moment this middleware was added. Existing
        metrics are left untouched.
        """
        collector = self.metrics_collector
        if collector.get_metric("http_requests_total") is None:
            collector.create_counter(
                "http_requests_total",
                "Total number of HTTP requests",
                labels={"method": "", "endpoint": "", "status": ""},
            )
        if collector.get_metric("http_request_duration_seconds") is None:
            collector.create_histogram(
                "http_request_duration_seconds",
                "HTTP request duration in seconds",
                labels={"method": "", "endpoint": ""},
                buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            )
        if collector.get_metric("quadkit_active_requests") is None:
            collector.create_gauge(
                "quadkit_active_requests",
                "Number of active HTTP requests",
            )
        if collector.get_metric("http_request_errors_total") is None:
            collector.create_counter(
                "http_request_errors_total",
                "HTTP requests that failed with a 4xx or 5xx status",
                labels={"method": "", "endpoint": "", "status_class": ""},
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
                if status_code[0] >= 400:
                    # Failures get their own series, bucketed by status class:
                    # an alert on "5xx rate" should not have to enumerate every
                    # code a deployment might return.
                    self.request_errors.labels(
                        method=method,
                        endpoint=path,
                        status_class=f"{status_code[0] // 100}xx",
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

                if status_code[0] >= 400:
                    error_counter = self.metrics_collector.get_metric(
                        "http_request_errors_total"
                    )
                    if error_counter:
                        cast("Any", error_counter).increment(
                            labels={
                                "method": method,
                                "endpoint": path,
                                "status_class": f"{status_code[0] // 100}xx",
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
        """Render every collected series in Prometheus text exposition format.

        ``prometheus_client`` keeps one series per label set; the collector
        instead keeps a bounded window of observations, so this renderer asks
        each metric for its per-label-set view.  Rendering only the most
        recent sample (as this once did) meant a scrape showed a single
        ``{method,endpoint,status}`` combination per metric and silently
        dropped every other — including the 4xx/5xx series an alert would be
        written against.  Histograms and summaries expand into their
        ``_bucket``/``_sum``/``_count`` (or ``_count``/``_sum``) families the
        same way ``prometheus_client`` would expose them.
        """
        lines: list[str] = []
        for name, metric in self.metrics_collector.get_all_metrics().items():
            metric_type = self._get_metric_type(metric)
            lines.append(f"# HELP {name} {metric.description}")
            lines.append(f"# TYPE {name} {metric_type}")
            if metric_type == "histogram":
                lines.extend(self._render_histogram(name, metric))
            elif metric_type == "summary":
                lines.extend(self._render_summary(name, metric))
            else:
                lines.extend(self._render_samples(name, metric))
        return "\n".join(lines) + "\n"

    def _render_samples(self, name: str, metric: Any) -> list[str]:
        """Render one line per label set for a counter or gauge."""
        return [
            f"{name}{self._format_labels(labels)} {self._format_number(value)}"
            for labels, value in self._metric_series(metric)
        ]

    def _render_histogram(self, name: str, metric: Any) -> list[str]:
        """Render cumulative buckets, sum and count per label set."""
        lines: list[str] = []
        getter = getattr(metric, "get_series_observations", None)
        buckets = list(getattr(metric, "buckets", []) or [])
        if not callable(getter):
            return self._render_samples(name, metric)
        for labels, observations in sorted(getter().items()):
            if not observations:
                continue
            for bucket in buckets:
                count = sum(1 for value in observations if value <= bucket)
                lines.append(
                    f"{name}_bucket"
                    f"{self._format_labels((*labels, ('le', self._format_number(bucket))))}"
                    f" {count}"
                )
            lines.append(
                f"{name}_bucket{self._format_labels((*labels, ('le', '+Inf')))}"
                f" {len(observations)}"
            )
            lines.append(
                f"{name}_sum{self._format_labels(labels)}"
                f" {self._format_number(sum(observations))}"
            )
            lines.append(
                f"{name}_count{self._format_labels(labels)} {len(observations)}"
            )
        return lines

    def _render_summary(self, name: str, metric: Any) -> list[str]:
        """Render the observation count and sum per label set."""
        lines: list[str] = []
        getter = getattr(metric, "get_series_observations", None)
        if not callable(getter):
            return self._render_samples(name, metric)
        for labels, observations in sorted(getter().items()):
            if not observations:
                continue
            lines.append(
                f"{name}_count{self._format_labels(labels)} {len(observations)}"
            )
            lines.append(
                f"{name}_sum{self._format_labels(labels)}"
                f" {self._format_number(sum(observations))}"
            )
        return lines

    def _metric_series(self, metric: Any) -> list[Any]:
        """Return ``[(labels, value), ...]`` for a simple metric.

        Prefers the collector's per-label-set totals; falls back to grouping
        the bounded value window by label set (last sample wins) for metric
        implementations that predate that accessor.
        """
        getter = getattr(metric, "get_series", None)
        if callable(getter):
            return sorted(
                (tuple(labels), float(value)) for labels, value in getter().items()
            )
        grouped: dict[tuple[tuple[str, str], ...], float] = {}
        for entry in getattr(metric, "_values", None) or []:
            labels = tuple(sorted((getattr(entry, "labels", None) or {}).items()))
            grouped[labels] = float(getattr(entry, "value", 0.0))
        return sorted(grouped.items())

    def _format_labels(self, labels: Any) -> str:
        """Render a label set, dropping labels without a value."""
        parts = [
            f'{key}="{self._escape_label_value(str(value))}"'
            for key, value in labels
            if value not in (None, "")
        ]
        return "{" + ",".join(parts) + "}" if parts else ""

    def _escape_label_value(self, value: str) -> str:
        """Escape a label value per the Prometheus text exposition format."""
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _format_number(self, value: float) -> str:
        """Render a float without a trailing ``.0`` for integral values."""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def _get_metric_type(self, metric: Any) -> str:
        type_name = metric.__class__.__name__.lower()
        if "counter" in type_name:
            return "counter"
        if "gauge" in type_name:
            return "gauge"
        if "histogram" in type_name:
            return "histogram"
        return "untyped"


class CollectorMetricsApp:
    """ASGI application that serves the collector's series at any path.

    Same graceful-degradation idea as :class:`PrometheusMiddleware`, but for
    the *only* job a scrape endpoint has: answer every request with the
    current metrics.  A metrics app is mounted at exactly one path by the web
    layer, so whatever path the router rewrites the request to — ``/metrics``,
    ``/metrics/``, or the value of ``WebConfig.metrics_path`` — is the scrape;
    matching on a hard-coded path would make the endpoint depend on the
    router's trailing-slash behaviour instead of on configuration.

    :class:`~quadkit.monitor.backends.exporters.prometheus.PrometheusMetricsExporter`
    is preferred when ``prometheus_client`` is installed (it renders from its
    own registry); this class is the collector-backed fallback so a deployment
    without the optional dependency still exposes real scrapeable metrics.

    Args:
        metrics_collector: Collector to render.  A probe-only collector is
            created when ``None`` — the middleware's own HTTP series are still
            recorded into it.
        auth_token: Optional bearer token.  When set, requests must carry
            ``Authorization: Bearer <auth_token>`` or receive ``401``.
            Defaults to ``None`` (endpoint open).
    """

    def __init__(
        self,
        metrics_collector: MetricsCollectorProtocol | None = None,
        auth_token: str | None = None,
    ) -> None:
        self.metrics_collector = metrics_collector or get_default_collector()
        self.auth_token = auth_token
        # Reuse the middleware's recording + rendering logic: it owns the
        # ``http_*`` series this endpoint exposes, so the scrape app and the
        # recorder must share one collector instance.
        self._renderer = PrometheusMiddleware(
            app=None,
            metrics_collector=self.metrics_collector,
            auth_token=auth_token,
        )

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """Serve the metrics exposition for any HTTP request."""
        if scope["type"] != "http":
            return
        if not is_authorized(scope, self.auth_token):
            await send_unauthorized(send)
            return
        # Always render *the collector*: when prometheus_client is installed
        # the middleware renders its module-global registry instead, which
        # holds only prometheus_client's own HTTP series — not the metrics the
        # application recorded through the injected collector. Serving that
        # registry would hand a scrape the wrong data.
        output = self._renderer._format_prometheus_metrics()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain; charset=utf-8"]],
            },
        )
        await send(
            {"type": "http.response.body", "body": output.encode("utf-8")},
        )
