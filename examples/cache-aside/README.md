# Cache-Aside Demo

A focused, browser-first example of the **cache-aside pattern** on
`quadkit-cache`. A report is computed once and then served from the cache
until it expires (`cache_side.report_ttl`) or is explicitly invalidated.

## What you'll learn

1. `CacheModule.configure()` — register a cache backend (in-memory by default)
   and expose `CacheBackendProtocol` for injection
2. `StampedeProtectedCache.get_or_compute` — the cache-aside read: return the
   stored value on a hit, run `compute` once on a miss and store the result
3. Service separation — the read-through lives in `ReportService`, not the
   controller
4. Provider lifecycle — resolve the backend at `boot()`, wrap it, bind the
   wired controller
5. Invalidation — `POST /report/invalidate` clears the entry so the next read
   recomputes

## Read in order

| # | File | What you learn |
|---|------|----------------|
| 1 | `src/cache_side/app.py` | `CacheModule` + `WebModule` composition |
| 2 | `src/cache_side/di/provider.py` | Resolve `CacheBackendProtocol`, wrap in stampede protection |
| 3 | `src/cache_side/services/report.py` | The cache-aside read via `get_or_compute` |
| 4 | `src/cache_side/controllers/api.py` | Thin HTTP adapter: read + invalidate |
| 5 | `tests/` | Real round trips proving compute → cached → invalidated |

## Run it

```bash
PYTHONPATH=examples/cache-aside/src uv run python -m cache_side   # :8131
```

- `GET /report` — `{"cached": false}` on the first call, `{"cached": true}` after
- `POST /report/invalidate` — drop the entry; the next read recomputes

## Tests

```bash
uv run pytest examples/cache-aside/tests
```

The tests boot the real composition root and drive it over ASGI — no mocks.
They assert the cache-aside contract: the first read computes, the second is
served from the cache (same payload, no second compute), and an invalidate
forces a recompute.
