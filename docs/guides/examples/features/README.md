# The feature tour

Forty-two runnable showcases of the public framework — one file per feature,
each executable as a test and readable as a guide, including the signature
Result pattern. Everything here runs
against the published wheels: no private packages, no services to start, no
sleeps.

## Run it

```bash
pip install quadkit quadkit-web quadkit-testing pytest pytest-asyncio
pytest docs/guides/examples/features/ -q          # all of it (~2s)
pytest docs/guides/examples/features/test_feature_throttle.py -q   # one feature
```

## The tour

| File | Feature | The line that sells it |
|---|---|---|
| `test_feature_sse.py` | Server-Sent Events | An async generator becomes a live feed: `@get` + `EventSourceResponse`. The advanced `SSEResponse` adds retry directives, durable event ids, and connect/disconnect lifecycle hooks. |
| `test_feature_throttle.py` | Rate limiting | `RateLimitModule.configure(backend="memory")` + `@throttle("2/minute", by="ip")` → a 429 with `Retry-After` and RFC-7807 problem details. No Redis needed to develop; Redis when you deploy. |
| `test_feature_api_version.py` | API evolution | `@api_version(1, deprecated=True, sunset="2030-01-01")` mounts `/v1/...` with honest `Deprecation`/`Sunset` headers; v2 answers side-by-side at `/v2/...`. |
| `test_feature_background.py` | Background work | Return `(payload, BackgroundTasks)` — the response streams out first, the work finishes behind it, with the request context restored inside every task. |
| `test_feature_roles.py` | Role guards | `@roles("admin", authorizer=auth)` hangs a guard on a handler; denied requests never reach business code. Two protocols (`Authenticator`, `Authorizer`) are the entire seam. |
| `test_feature_retry_stream.py` | Reactive retry | `stream.pipe(retry(RetryOptions(max_attempts=3)))` re-subscribes a flaky source until it succeeds — or hands you the last error with dignity. `should_retry` short-circuits fatal errors instantly. |
| `test_feature_request_context.py` | Request context | `request_context(registry, request_id=...)` scopes typed contextvars and restores them on exit; on the web, the default middleware propagates `X-Request-ID`/`X-Tenant-ID` and echoes the id back. |
| `test_feature_pagination.py` | Pagination | Declare `page`/`size`; return `Page(items, total, page, size)` and the derived `pages` count rides along. Cursor-style returns the standard `items + meta` envelope. |
| `test_feature_responses.py` | Response shaping | `file_response` (with correct disposition), `streaming_response` (chunked), `html_response`, `redirect_response` — and a bare `str` renders `text/html` for HTMX pages. |
| `test_feature_uploads.py` | Validated uploads | `FileUploadPipeline` with size/type/extension validators returning typed `Result`s; `save_to(base_dir=)` refuses path-traversal escapes outright. |
| `test_feature_templates.py` | Templates | `Jinja2Templates` is constructor-injected (register once, inject everywhere) with context processors — and autoescape is on: `<script>` arrives as text. |
| `test_feature_subject.py` | Subjects | `Subject(replay=2)` — late subscribers start with the newest two items before continuing live; `complete()` unwinds everyone cleanly. |
| `test_feature_hooks.py` | Lifecycle hooks | Register actions on canonical hook names (`request.received`, `response.prepared`) — priority-ordered, failure-tolerant, typed payloads, zero middleware wiring. |
| `test_feature_result.py` | The Result pattern | Errors are values: `Ok`/`Err` with `map_sync`/`and_then_sync`/`or_else_sync`/`match`, `@as_result` and `try_catch` to lift raisers, `collect`/`partition` to fold whole collections. Async chains use the same verbs. |
| `test_feature_result_web.py` | Result → HTTP | `Err(NotFoundError(...))` from a handler lands as 404, `PaymentDeclined` as 402 via one `@error_status` decorator, the `DomainError` default as 400. No `try/except` anywhere near a controller. |
| `test_feature_di.py` | Dependency injection | `singleton` / `transient` / `scoped` — one registration call each; `@inject` classes auto-wire from constructor annotations; scoped instances cache within a scope and isolate across it (concurrency-proof single creation). |
| `test_feature_builder.py` | `@buildable` | `Invoice.builder().with_number(...).with_total(...).build()` — fluent construction lands on plain classes; defaults apply, missing required fields surface at `build()`, `copy()` branches builders safely. |
| `test_feature_params.py` | Typed params & pipes | `query`/`header`/`DomainModel`-typed body — declared in the signature, delivered typed; `ParseIntPipe` parses, a 6-line custom pipe clamps page size at 50. |
| `test_feature_interceptors.py` | Interceptors | `@use_interceptors(...)` per route; `InterceptorPipeline` singleton for app-wide coverage. Before/after around `next.handle()` — a custom interceptor tags every response. |
| `test_feature_invoker.py` | Invoker | Call a plain async function with dependencies resolved from the container by type and arguments supplied positionally — one line, no wiring ceremony; flows through the app middleware pipeline. |
| `test_feature_websockets.py` | WebSockets | `@websocket_handler("/ws/ticks/{channel}")` + `on_connect`/`on_message`/`on_disconnect` lifecycle; path params bind per connection; channel state stays isolated by instance. |
| `test_feature_crud.py` | CRUD scaffolding | Implement `CRUDServiceProtocol` (five async methods returning `Result`s); `GenericController` yields list/get/create/update/delete — 201/204/404 and pagination keys included, zero handler code. |
| `test_feature_sanitization.py` | Input sanitization | One middleware line scrubs query values: null bytes stripped, `<script>`/`javascript:` payloads dropped to empty strings — the route still serves. |
| `test_feature_plugins.py` | Plugin planning | `validate_plan`: dependencies satisfied and conflicts excluded deterministically; issues recorded, boot never blocked; the disabled set persists across restarts. |
| `test_feature_logging.py` | Logging discipline | Secret fields mask to `<redacted>` — nested containers included; deterministic sampling at 0.0 drops noise while a named rule keeps every `order.placed`. |
| `test_feature_htmx.py` | HTMX partials | `HTMXResponse` stamps `HX-Trigger` (dicts JSON-encoded) and `HX-Refresh`; bare `str` returns serve as `text/html` — HTMX swaps get exactly what they need. |
| `test_feature_cqrs_dispatch.py` | CQRS dispatch | `CQRSController` hands commands/queries to protocol buses injected by constructor — endpoints stay transport-thin, handlers stay web-free; a missing bus fails with the registration hint. |
| `test_feature_middleware_composition.py` | Middleware composition | Chain → frozen onion pipeline (immutable: `add` returns a new pipeline); priority-ordered registry lifts straight into a chain; the default stack is an explicit list where user middleware follows the outermost DI-scope layer. |
| `test_feature_auth_extraction.py` | Auth extraction | Identity is a seam: middleware writes `request.state.user`, `get_current_user_required` answers 401 with a `Bearer` challenge for guests, `get_current_user_optional` returns `None` — and `get_request_id` rides the same state trough. |
| `test_feature_verbs.py` | HEAD/OPTIONS/PATCH | Every GET route answers HEAD for free (headers, no body); explicit `@head` serves HEAD-only endpoints (GET there is 405); `@options` advertises `Allow`; `@patch` merges partial updates. |
| `test_feature_result_pipeline.py` | Result pipelines | `pipeline(v)`/`ResultPipeline(r)` → `then` short-circuits on first `Err`, `map` for infallible steps, `recover` swaps in a fallback plan, `finalize` returns the typed `Result[T, E]`. |
| `test_feature_provide.py` | `@provide` factories | Write a function, get a Provider: return annotation is the contract, parameters inject from the container during boot, `scope=` sets lifetime; missing annotation fails at import time. |
| `test_feature_version_extraction.py` | Version extraction | Four strategies (header/query/URI/media-type) stamp `request.state.api_version` through `VersioningMiddleware` — extraction only, `default_version` fallback, handlers read with `get_version`. |
| `test_feature_controller_discovery.py` | Controller discovery | `discover_controllers(("pkg",))` walks the package tree, returns concrete Controller subclasses only, deduped; hand the list to `WebModule.configure` and convention replaces registration. |
| `test_feature_modules.py` | Modules & exports | Unimported modules stay inert; at boot the container audits cross-module wiring — an exported service crosses the boundary, an unexported reach fails at boot with the fix named; runtime resolution is deliberately flat. |
| `test_feature_config_layers.py` | Config layering | Deterministic precedence: env vars override YAML, YAML overrides declared defaults; plain constructors read defaults while `from_yaml`/providers layer the sources; boot wires `QuadkitConfig` with `QK_*` applied. |
| `test_feature_container_builder.py` | ContainerBuilder | A container without an application: fluent `add_singleton`/`add_transient` with `await build()`, singletons shared and transients fresh, and `Provider` classes bridge straight in from the application world. |
| `test_feature_health.py` | Health & probes | Probe trio (`/health/live`/`ready`/`startup`) tells the truth out of the box — a running app always reports its baseline; deep `/health` is strict: missing db/cache are named unhealthy components (503), a degraded one maps to 207. |
| `test_feature_static_files.py` | Static assets | `WebConfig(static=StaticFileConfig(enabled=True, ...))` mounts a directory at boot — content types by extension, nested paths, traversal refused as plain 404, `html=True` flips to SPA mode. |
| `test_feature_config_sources.py` | Config sources | `ConfigProvider(sources=[...])` deep-merges layered files per key (later wins, fall-through), env always lands on top, and custom typed sections stay under the strict unknown-key guard. |
| `test_feature_web_security.py` | Web perimeter | CORS allow-lists negotiate preflights for guests (204 + echoed headers) and stay silent for strangers; host lists refuse impostors with 400; nosniff / frame DENY / referrer-policy ride along by default. |
| `test_feature_exception_handlers.py` | Exception handling | Thrown `DomainError`s become RFC 7807 problem details with zero wiring — plain `{Type: handler}` mappings translate your own exceptions, dispatch by inheritance, and outrank the built-in translation. |

## What "tour-grade" means

- **Executable** — a pytest file first and a guide second; CI runs them.
- **Honest** — they assert the failure paths too (429s, 403s, 422s,
  error short-circuits).
- **Wheel-proven** — each file was verified against the five public wheels
  (`quadkit`, `quadkit-web`, `quadkit-contracts`, `quadkit-testing`,
  `quadkit-cli`) in a clean environment.
- **Found bugs so you don't have to** — authoring these examples drove out
  five framework fixes (ambient `@throttle` resolution, memory-backend
  wiring, 429 mapping, deprecation headers, background-task wiring), all
  shipped with regression tests.
