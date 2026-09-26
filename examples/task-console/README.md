# Task Console

A focused, browser-first example of **Quadkit's background-processing
stack** from `quadkit-tasks`. `TasksModule.configure()` wires a real
`MemoryTaskQueue`, `WorkerPool`, `TaskScheduler`, `InMemoryResultStore`,
and `DeadLetterQueue` — the console enqueues real jobs, watches the real
worker pool and scheduler process them, and retries permanently-failed
jobs out of the real dead letter queue. No Redis, RabbitMQ, or Postgres
broker is required.

## What to try

1. Look at the seeded activity: on boot the demo enqueues one
   `send_welcome_email`, one `resize_image`, one `flaky_report`, and one
   `always_fails` job through the real
   `TaskProviderProtocol.enqueue_job()`.
2. Check **Recent results** — `send_welcome_email` and `resize_image`
   complete immediately; `always_fails` and `flaky_report` land in the
   real `DeadLetterQueue` because this demo wires no
   `RetryPolicyProtocol` (a failed job routes straight to the DLQ, never
   back onto the queue).
3. Open **Dead letter queue** and click **Retry** on `flaky_report` — it
   re-enqueues the *same* job through `DeadLetterQueue.retry()`. Its
   handler tracks attempts in-process and only succeeds on the third try,
   so you may need to retry it twice to watch it finally complete.
4. Enqueue your own job from the form — pick a task, fill in its kwargs
   as JSON, and submit; the job appears in **Submitted jobs** immediately
   and in **Recent results** once the worker pool picks it up.
5. Watch **Worker pool** and **Scheduled jobs** — both are read straight
   from `TaskProviderProtocol.get_worker_stats()` /
   `get_scheduled_jobs()`. A real `@scheduled("*/1 * * * *")` heartbeat
   job is registered on boot and fires every minute.
6. Click **Purge all** on the DLQ panel to clear it via
   `DeadLetterQueue.clear()`.

## Quadkit surface

- `TasksModule.configure(queue=MemoryTaskQueue(), worker_count=1,
  enable_scheduler=True)` — a global module; every singleton it registers
  (`TaskProviderProtocol`, `ResultStore`, `WorkerPool`, ...) is resolvable
  from any container scope
- `TaskProviderProtocol.enqueue_job()` / `register_handler()` /
  `register_scheduled_task()` / `get_worker_stats()` /
  `get_scheduled_jobs()` / `health_check()` — the real task-processing API
  this console is built on
- `@scheduled(cron_expression, name=...)` — registers a real cron job with
  `TaskScheduler`
- `ResultStore.get()` / `wait()` / `get_completed()` / `get_failed()` —
  real result persistence with TTL-based expiry
- `DeadLetterQueue.list_failed()` / `retry()` / `clear()` — real DLQ
  inspection and recovery (reached via `WorkerPool._dead_letter_queue`,
  since `quadkit-tasks` has no public DI binding for it yet — the same
  "reach past the exported surface" exception `audit-trail` documents for
  `AuditLogger._store`)
- `WebModule` controllers with a standalone server entry point

## Run

```bash
cd examples/task-console
PYTHONPATH=src uv run python -m task_console
```

The hub embeds this console at `/examples/task-console/`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/tasks/health` | Report readiness of the underlying task provider |
| POST | `/api/tasks` | Enqueue a job from `{task, kwargs, priority, max_retries}` |
| GET | `/api/tasks/submitted` | List every job the demo has submitted this run |
| GET | `/api/tasks/jobs/{job_id}` | Return the stored result for a job, or 404 if not yet available |
| GET | `/api/tasks/jobs/{job_id}/wait` | Wait (bounded by config) for a job to complete, then return its result |
| GET | `/api/tasks/results` | List recently completed and failed jobs from the real result store |
| GET | `/api/tasks/workers` | Return live worker-pool statistics |
| GET | `/api/tasks/scheduled` | Return the scheduler's registered cron jobs |
| GET | `/api/tasks/dlq` | List permanently failed jobs sitting in the dead letter queue |
| POST | `/api/tasks/dlq/{job_id}/retry` | Re-enqueue a dead-lettered job for another attempt |
| POST | `/api/tasks/dlq/purge` | Purge every entry from the DLQ |

## Bugs found and fixed while building this demo

Building a real console against `quadkit-tasks` surfaced three latent
framework/service bugs, fixed alongside this demo:

1. **Double-wrapped `JobResult.data`** (`quadkit-tasks`,
   `execution/worker.py::_execute_job`) — the success path re-wrapped the
   already-complete `JobResult` returned by
   `execute_handler_through_middleware()` in a second
   `JobResult.ok(...)`, so every consumer's `result.data` held a full
   `{success, data, error, duration, ...}` dict instead of the handler's
   raw return value. Fixed by unwrapping `inner_result.data` before
   building the final result.
2. **DLQ retry silently reused an empty job id** (this demo's
   `TaskConsoleService.retry_dlq_job`) — `JobProtocol` only generates a
   fresh UUID in `__post_init__` (construction time); assigning
   `job.id = ""` afterwards does not regenerate one, so every retried job
   was re-enqueued under an empty id and silently clobbered result-store
   lookups. Fixed by assigning a real `uuid.uuid4()`.
3. **`purge_dlq()` purged nothing** (this demo) — `DeadLetterQueue.purge()`
   only removes entries older than `older_than_hours`, and `0` is falsy,
   so `purge(older_than_hours=0)` silently fell back to the default 7-day
   retention window instead of purging everything. Fixed by calling the
   real `DeadLetterQueue.clear()` instead, which is the framework's actual
   "remove everything unconditionally" operation.

## Quadkit Concepts

| Concept | How it's used |
|---------|---------------|
| Provider Pattern | `TaskConsoleProvider` resolves the `TaskProviderProtocol`, `ResultStore`, and `WorkerPool` that `TasksModule` registered, registers the demo's own handlers, then wires the browser-facing service |
| Dependency Injection | `TaskConsoleApiController` receives `TaskConsoleService` via constructor; the service receives the real provider, result store, and DLQ |
| Global Module Visibility | `TasksModule.configure(is_global=True)` makes `TaskProviderProtocol`/`ResultStore`/`WorkerPool` resolvable from `TaskConsoleProvider` even though they aren't in the module's `exports` list |
| Zero External Broker | `MemoryTaskQueue()` is constructed explicitly and passed to `TasksModule.configure(queue=...)`, so the whole demo runs with no Redis/RabbitMQ/Postgres dependency |
| Real Scheduled Jobs | `@scheduled("*/1 * * * *", name="scheduled_heartbeat")` registers a cron job with the real `TaskScheduler`, backed by `croniter` |
| No Retry Policy — DLQ-First | `quadkit-tasks` has no `RetryPolicyProtocol` wired via DI anywhere in the package, so this demo relies on the DLQ plus manual re-enqueue for retry stories, not automatic retries |
| Health Checks | `TaskConsoleProvider.health_check()` delegates to the service, which reports the real `TaskProviderProtocol.health_check()` result plus submitted/DLQ counts |
| Result Pattern | `enqueue()`/`retry_dlq_job()` return `Result[dict, ValidationError \| NotFoundError]`; validation failures raise `ValueError`, mapped to a 422 |
| RFC-9457 Problem Details | An unknown task name or non-object `kwargs` maps to a 422 `application/problem+json` body via `ValidationError` |
| Web Controllers | `TaskConsoleApiController` extends `Controller` with `@get`/`@post` route decorators under the `/api/tasks` prefix |
| Task Allowlist | The browser can only enqueue the demo's own curated handler set (`_ALLOWED_TASKS`), never an arbitrary caller-supplied task name |
| Client-Tracked Submission Log | `TaskQueueProtocol` has no "list all jobs ever submitted" method, so the demo tracks what it has submitted client-side — the same pattern `notification-center` and `search-console` use for their own unlistable collections |
