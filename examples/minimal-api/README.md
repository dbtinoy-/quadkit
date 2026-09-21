# Minimal API

The smallest useful Quadkit web service — and the canonical starter
template: one controller, two routes, one typed-config knob, laid out in
the standard `src/` shape every other starter builds on.

**Demonstrates:** `Application`, `WebModule.configure(controllers=[...])`,
`@get`/`@post` routes, `body()` payloads, status codes, typed
`BaseConfig` sections, and `application.yaml` discovery.

## Layout

```
src/minimal_api/
├── app.py             # composition root: build_modules/build_providers
├── main.py            # serve() with try/finally app.stop()
├── config.py          # MinimalApiConfig (minimal_api: yaml section)
├── controllers/api.py # HelloController — GET /hello, POST /echo
└── di/provider.py     # register/boot/health_check lifecycle
```

## Run

```bash
pip install quadkit[web]
PYTHONPATH=src python -m minimal_api
curl localhost:8120/hello
```

The greeting comes from `minimal_api.greeting` in `application.yaml`
(override with `QK_MINIMAL_API__GREETING=hi`).

## Test

```bash
pip install quadkit[web] quadkit-testing pytest pytest-asyncio
PYTHONPATH=src pytest tests/
```

The suite also exercises reliability: a 50-request concurrency exercise
(mixed in-flight requests must not bleed state).
