# Background Worker

Long-running work off the request path — the canonical starter for
provider-owned background loops: an asyncio queue, a bounded worker
pool, graceful shutdown, and an HTTP facet for submitting and observing
work.

**Demonstrates:** the provider lifecycle (`register` → `boot` starts the
pool, `shutdown` drains it), dependency injection across providers and
controllers, 202-accepted submissions, and testing asynchronous
processing with real round trips.

## Layout

```
src/background_worker/
├── app.py              # composition root
├── main.py             # serve() with try/finally app.stop()
├── config.py           # BackgroundWorkerConfig (concurrency, poll_timeout)
├── controllers/api.py  # WorkController — POST /tasks (202), GET /stats
├── services/worker.py  # TaskQueue + WorkerEngine (bounded pool)
└── di/provider.py      # starts engine in boot(), drains in shutdown()
```

## Run

```bash
pip install quadkit[web]
PYTHONPATH=src python -m background_worker
curl -X POST localhost:8124/tasks -H 'content-type: application/json' \
  -d '{"duration": 2.0}'
curl localhost:8124/stats
```

The pool size is `background_worker.concurrency` (override with
`QK_BACKGROUND_WORKER__CONCURRENCY=4`).

## Test

```bash
PYTHONPATH=src pytest tests/
```

The suite also exercises reliability: failure injection (a raising task
is counted, the pool survives).
