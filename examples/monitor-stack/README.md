# Monitor Stack Demo

A focused, browser-first example of **Quadkit MonitorModule**. The console
uses the package's real metric instruments, bounded in-memory tracing, and
categorised health registry. No external telemetry service is required.

## What you'll learn

1. `MonitorModule.configure()` — real observability bindings through DI
2. Metrics — counters, gauges, histograms, and instrument introspection
3. Tracing — start/end spans, attributes, trace IDs, and duration metrics
4. Health probes — register a readiness check and run the package registry
5. Provider lifecycle — add only the demo-specific self-check and HTTP console

## Read in order

| # | File | What you learn |
|---|------|----------------|
| 1 | `application.yaml` | Quadkit Monitor tracing and demo settings |
| 2 | `src/monitorstack/app.py` | `MonitorModule` + `WebModule` composition |
| 3 | `src/monitorstack/di/provider.py` | Resolve monitor protocols and register one self-check |
| 4 | `src/monitorstack/controllers/api.py` | JSON adapters for metrics, probes, and spans |
| 5 | `src/monitorstack/ui/` | Live browser console |
| 6 | `tests/` | Real composition-root coverage |

## Architecture

```
application.yaml
      │
      ▼
MonitorModule.configure()
      ├── MetricsCollectorProtocol
      ├── TracerProtocol
      └── HealthCheckRegistry
                │
                ▼
      MonitorStackProvider + WebModule
                │
                ▼
       browser observability console
```

The demo deliberately does not duplicate metric, tracing, or health classes.
Quadkit Monitor owns those capabilities; the app provider only registers the
one check and presents them.

## Quick start

```bash
cd examples/monitor-stack
uv run python -m monitorstack
```

Open the URL printed by the server. Record a span, adjust a metric, and watch
the health and metric panels refresh.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/monitor/health` | Run liveness/readiness probes |
| `GET` | `/api/monitor/health/self` | Run the named self-check |
| `GET` | `/api/monitor/metrics` | Inspect package metric instruments |
| `POST` | `/api/monitor/metrics/increment` | Increment a counter |
| `POST` | `/api/monitor/metrics/gauge` | Set a gauge |
| `GET` | `/api/monitor/traces` | Inspect bounded spans |
| `POST` | `/api/monitor/trace` | Create a timed span |
