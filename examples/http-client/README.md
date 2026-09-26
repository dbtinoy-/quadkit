# HTTP Client Demo

A focused example of **outbound HTTP** with `quadkit-http`. The demo's real
framework client makes a genuine loopback round-trip to an in-process mock
upstream — no third party, no resilience layer, just the client and a
reachable peer.

## What you'll learn

1. `HTTPModule.configure()` — register the framework HTTP client and expose
   `HTTPClientProtocol` for injection
2. The client's verb methods return a `Result` — unwrap `Ok(response)` for
   `response.status` / `response.json`, or `Err(HTTPClientError)`
3. An in-process `aiohttp` mock upstream on an ephemeral loopback port, so the
   demo runs with no external egress
4. Provider lifecycle — start the upstream and client at `boot()`, release them
   at `shutdown()`
5. Relaxing `enforce_url_safety` for a known-trusted loopback peer

## Read in order

| # | File | What you learn |
|---|------|----------------|
| 1 | `src/http_side/app.py` | `HTTPModule` + `WebModule` composition |
| 2 | `src/http_side/mock/upstream.py` | The in-process aiohttp upstream + its lifecycle |
| 3 | `src/http_side/di/provider.py` | Boot the upstream, build the client, bind the controller |
| 4 | `src/http_side/services/upstream.py` | Drive the client, unwrap the `Result` |
| 5 | `src/http_side/controllers/api.py` | Thin HTTP adapter: proxy the echo + status routes |
| 6 | `tests/` | Real loopback round-trips asserting status + body |

## Run it

```bash
PYTHONPATH=examples/http-client/src uv run python -m http_side   # :8132
```

- `GET /upstream/echo` — the client calls the upstream's `/echo`; you see the
  method/path the client actually sent
- `GET /upstream/status/{code}` — the upstream answers with that status; the
  demo reports the real status it received

## Tests

```bash
uv run pytest examples/http-client/tests
```

The tests boot the real composition root (which starts the mock upstream) and
drive it over ASGI — no mocks at the client level. They assert the outbound
contract: a real round-trip returns the upstream's status and echoed body.
