# Docker deployment

Reference container setup for a Quadkit service, using the minimal-api style
template shape (`src/` layout, `application.yaml`, `python -m` entry point).

## Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first: this layer caches until the pin changes.
RUN pip install "quadkit[web]==0.0.44" granian

# Application code and config.
COPY src/ src/
COPY application.yaml .

# Run as an unprivileged user.
RUN useradd --uid 1000 --create-home app && chown -R app:app /app
USER app

EXPOSE 8100

# Granian in production; the service binds 0.0.0.0 inside the container.
ENV QK_WEB__SERVER__BACKEND=granian \
    QK_WEB__SERVER__HOST=0.0.0.0 \
    QK_WEB__SERVER__PORT=8100
CMD ["python", "-m", "minimal_api.app"]
```

Notes on the choices:

- **Pin the distribution** (`quadkit[web]==…`) — reproducible images; bump
  deliberately after reading release notes.
- **`python -m` entry point** — mirrors local development; no duplicated
  wiring in a separate ASGI module. Quadkit loads `application.yaml` from
  the working directory (`/app` here).
- **Env overrides for the container delta** — bind host, port, and backend
  come from `QK_*` env vars, so the same image runs anywhere without config
  edits. Secrets arrive the same way (`QK_*` env from your secret store).

## Compose sketch for local parity

```yaml
services:
  api:
    build: .
    ports: ["8100:8100"]
    environment:
      QK_WEB__SERVER__BACKEND: uvicorn
      QK_WEB__SERVER__RELOAD: "true"
    volumes:
      - ./application.yaml:/app/application.yaml:ro
```

## Health and shutdown

- `/health` reports 200 only when every configured connectivity probe
  passes (see [observability](guides/observability.md)); point your
  orchestrator's readiness check at it. A service with no probes configured
  fails closed (503) — that is intentional, not a bug.
- Providers shut down in reverse boot order on SIGTERM, so in-flight work
  drains. Give the container a graceful stop timeout (`stop_grace_period`)
  that covers your slowest worker drain.
- Log to stdout — Quadkit writes structured logs there by default, which
  is what container runtimes collect.

## Verifying the image outside CI

```bash
docker build -t qk-minimal .
docker run --rm -p 8100:8100 qk-minimal
curl localhost:8100/hello
```
