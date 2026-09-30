# Quadkit Structured Logging

Structured, JSON-capable logging for the Quadkit Framework, built on
structlog. This document is the **contract** for log consumers (SIEM
pipelines, error trackers, CLI operators) and must stay in sync with
`quadkit/logging/configurator.py`.

## Enabling structured logging

```python
from quadkit.logging import configure_logging

configure_logging(level="INFO", json_format=True, service_name="my-app")
```

Or through configuration (loaded from `QK_*` env vars):

Core configuration is the `quadkit.logging` section (env prefix
`QK_QUADKIT__LOGGING__*`). Observability packages may expose their own
config, but they do **not** own structured logging: format, level, redaction,
and sampling are all driven by the core `QK_QUADKIT__LOGGING__*` namespace
so there is a single source of truth for the pipeline.

| Config key                      | Meaning                                  | Default  |
|---------------------------------|------------------------------------------|----------|
| `QK_QUADKIT__LOGGING__LEVEL`  | Global log level                         | `INFO`   |
| `QK_QUADKIT__LOGGING__JSON_FORMAT` | Render JSON instead of console text  | `false`  |
| `QK_QUADKIT__LOGGING__LEVELS` | Per-logger overrides (`{"quadkit.di": "DEBUG"}`) | —   |
| `QK_QUADKIT__LOGGING__SAMPLING__ENABLED` | Enable event sampling           | `false`  |
| `QK_QUADKIT__LOGGING__REDACTION__ENABLED` | Mask denylisted fields       | true     |
| `QK_QUADKIT__LOGGING__REDACTION__FIELD_DENYLIST` | Denylist tuple        | default  |

`service_name` passed to `configure_logging()` — or the `Application.name` /
`QuadkitConfig.app_name` when using `apply_config()` — is injected into every
log event as the top-level `service` field.

## JSON event schema (`json_format=True`)

Each log line is a single JSON object emitted by
`structlog.processors.JSONRenderer()`:

```json
{
  "timestamp": "2026-08-19 10:15:30",
  "level": "INFO",
  "event": "user_created",
  "service": "my-app",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "_logger_name": "quadkit.web.controller",
  "_filename": "controller.py",
  "_lineno": 42,
  "_module": "controller",
  "_func_name": "create_user",
  "user_id": "usr_123"
}
```

| Field       | Source                                                        |
|-------------|---------------------------------------------------------------|
| `timestamp` | `TimeStamper(fmt="%Y-%m-%d %H:%M:%S")`                       |
| `level`     | `structlog.stdlib.add_log_level`                             |
| `event`     | Message passed to `logger.info("...")`                       |
| `service`   | Injected by `configure_logging(service_name=...)` / `Application.name`; overridable via `bind(service=...)` |
| `trace_id` / `span_id` | `_otel_processor` — only when an OTEL trace context is active |
| `_logger_name` | `get_logger()` / `_add_logger_name` — auto-prefixed with `quadkit.` |
| `_filename` / `_lineno` / `_module` / `_func_name` | `CallsiteParameterAdder`, wrapped by `_NamespacedCallsiteAdder` |
| `exception` | Formatted traceback, present on `logger.exception(...)` / `exc_info=True` |

Key-value arguments passed to a log call are appended verbatim as top-level
fields (`logger.info("user_created", user_id=usr.id)` → `"user_id"`).

## Field names: what the envelope owns, and what you own

Two namespaces, so a caller's field and the pipeline's metadata can never
be the same key:

- **`_`-prefixed keys belong to the framework** — `_logger_name`,
  `_filename`, `_lineno`, `_module`, `_func_name`. Do not pass them.
- **Every other plain name belongs to the caller.** `module=`, `filename=`,
  `name=`, `msg=` are ordinary fields; `logger.info("module_booted",
  module=self.name)` renders the value you passed.
- **Five envelope names are reserved**: `event`, `level`, `timestamp`,
  `service` and `exception`. `service` is deliberately overridable via
  `bind(service=...)`; the other four are not yours to set.
  `dev/checks/reserved_log_fields.py` fails the build on a call site that
  passes one.

`event` is the sharp one: it is structlog's parameter for the *message*, so
`logger.warning("emit_failed", event=type(evt).__name__)` raises
`TypeError` — inside the `except` block that was reporting the failure.
Because a diagnostic must never raise, `_NamedLogger` moves such a field to
`event_field` rather than letting the call blow up; the gate is what makes
you rename it properly (`event_type`, `webhook_event`).

Callsite metadata reports *your* frame, not the framework's: the adder is
configured with `additional_ignores=["quadkit.logging"]`, without which
`_NamedLogger.info` in `logging/factory.py` is the nearest non-structlog
frame and every line in the process is stamped with it.

## Behavior guarantees

- **Levels**: `DEBUG < INFO < WARNING < ERROR < CRITICAL`. A global
  filtering wrapper drops events below `level` before processors run.
- **Per-logger overrides** only *raise* the effective level (never lower it
  below the global minimum).
- **Redaction**: fields matching the denylist (e.g. `token`, `password`,
  `api_key`) are masked before rendering. Enabled by default. To log raw
  values, pass `redaction_enabled=False` or a custom denylist.
- **Sampling** (optional): deterministic per-event sampling, rate keyed by
  event name (`sampling_rules={"request_received": 0.01}`) with
  `sampling_default_rate` as fallback.
- **Stdlib bridge**: third-party libraries (SQLAlchemy, asyncpg, httpx,
  Granian) are routed through `ProcessorFormatter` with level + timestamp
  enrichment. Foreign records do **not** pass the structlog processor chain
  (no redaction/sampling/OTEL enrichment for them).

## Consumption guidance

- Use `get_logger(__name__)` — the `quadkit.` prefix is added
  automatically, so `logger.name` is always fully qualified.
- Never `print()`; never log secret material (redaction is a safety net,
  not a substitute for not logging secrets).
- For error tracking, forward `level >= ERROR` events with `event`,
  `exception`, `_logger_name`, and `trace_id` fields — correlation IDs make
  distributed debugging possible.
