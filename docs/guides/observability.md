# Observability

What a stock Quadkit service emits, where it goes, and what to do when a
deploy misbehaves. Everything below works with only the thirteen public
distributions installed — no vendor lock-in, every surface is structured
data you can route anywhere.

## Structured logging

Quadkit logs as structured events (JSON with structlog), not formatted
strings: every record carries `timestamp`, `level`, `_logger_name`, and any
context fields the framework or your code attaches. Boot logs each
provider's `register`/`boot` phase plus `application.starting` and
`application.started`; the web layer logs route discovery, security-header
setup, and per-request access lines. Web requests span ASGI lifespan →
route match → controller → response — you can follow one request by its
context fields across those events.

The application name comes from `application.yaml` (`app_name`) or the
`QK_QUADKIT__APP_NAME` environment override, and appears in every startup
banner — set it so your log stream is attributable per service.

## Health and readiness

`/health` is non-blocking on request time-outs and reports the connectivity
probes you configured (database, cache, …). Each component is reported
separately and in one of three states: `healthy`, `unhealthy` (with the
error), or `unknown` (with the reason nothing checked it, e.g.
`"No database provider is registered"`). Only `unhealthy`/`degraded`
components affect the status code, so a service with no data probes
configured answers **200 with `unknown` components** — it is not claiming
health it has not verified, it is saying what it has. Wire probes via your
providers (register pool resources at `boot`) and those components become
real checks, answering `503` when a backing service is genuinely
unreachable. Use `/health` for load-balancer targets; for Kubernetes, point
`livenessProbe` at it and use startup probes with generous `failureThreshold`
while providers boot.

Time-outs: controller work and provider boot phases are async all the way
down — a wedged downstream call stalls the event loop. Keep `httpx`
(or driver) per-request time-outs explicit in your services; the web
server's own `timeout_keep_alive` is set on `run_server(...)`.

## Tracing and metrics (optional)

OpenTelemetry is an **opt-in dependency**: without `opentelemetry-api`
installed, startup logs `opentelemetry_not_installed` and request handling
continues with zero cost. Install the API/SDK packages, configure the
standard OTEL exporter environment (`OTEL_EXPORTER_OTLP_ENDPOINT`), and
trace/span ids are injected into log events automatically — logs and traces
join without code changes.

For metrics, export through your OTLP collector the same way. Nothing is
emitted to a vendor endpoint unless you configure one.

## Incident runbook

| Symptom | Where to look first |
| --- | --- |
| `503` on `/health` | The `components` map in the health payload names the failing probe; check that backend's connectivity and credentials. |
| Requests hang without logging | A sync or un-timed-out call inside a controller; check your `httpx`/driver time-outs, then the event loop (CPU-bound work in async handlers shows up as uniform latency). |
| No logs at all | `QK_QUADKIT__LOGGING__LEVEL` (or `application.yaml` `logging.level`) set above the event you're expecting; container stdout captured by the platform. |
| `application.started` never appears | A provider raised during `boot` — the stack trace names it; validate that provider's config section first. |
| Auth returns 401 unexpectedly | Missing/expired token upstream of your authenticator; the request access log still records the attempt, keyed by the same context fields. |

## See also

- [Production deployment](production-deployment.md) — server knobs,
  container posture, config hardening.
- [Error handling](error-handling.md) — how failures become structured
  problem responses.
