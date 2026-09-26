# Installation

## Requirements

- **Python >= 3.11** — every published distribution shares this floor,
  taken from each package's `requires-python` metadata.
- [uv](https://docs.astral.sh/uv/) (recommended) or `pip`.

No database, cache, message broker, or any other external service is
needed to install the packages, follow the quickstart, or run the test
harness — the defaults are self-contained and work offline.

## Install

```bash
# uv (recommended)
uv add "quadkit[web]"

# pip
pip install "quadkit[web]"
```

`quadkit[web]` is the batteries-included web stack: the core framework
plus `quadkit-web` with the [Granian](https://github.com/emmett-framework/granian)
server backend. That single dependency line is all the
[first app](./first-app.md) needs.

## The thirteen packages

Everything published from this repository is one of these thirteen
distributions. They version in lockstep — see
[stability and compatibility](../reference/stability.md).

| Distribution | Install command | Provides |
| --- | --- | --- |
| `quadkit` | `pip install quadkit` | DI container, application lifecycle, configuration, `Result` |
| `quadkit-contracts` | `pip install quadkit-contracts` | Protocols, shared types, exceptions — zero runtime dependencies |
| `quadkit-web` | `pip install quadkit-web` | Async web layer: controllers, routing, middleware, OpenAPI |
| `quadkit-testing` | `pip install quadkit-testing` | Test harnesses, fakes, and web test clients |
| `quadkit-cli` | `pip install quadkit-cli` | Project scaffolding, generators, and dev commands |
| `quadkit-sql` | `pip install quadkit-sql` | Async SQL databases: engines, repositories, migrations |
| `quadkit-auth` | `pip install quadkit-auth` | Authentication and authorization: sessions, tokens, RBAC |
| `quadkit-cache` | `pip install quadkit-cache` | Multi-backend caching: in-memory, Redis, memcached |
| `quadkit-storage` | `pip install quadkit-storage` | Blob and object storage backends (local, S3, GCS, Azure, R2) |
| `quadkit-events` | `pip install quadkit-events` | Event bus and event store: publish, subscribe, replay |
| `quadkit-tasks` | `pip install quadkit-tasks` | Background tasks and scheduling |
| `quadkit-http` | `pip install quadkit-http` | Outbound HTTP client: pooling, retries, streaming |
| `quadkit-monitor` | `pip install quadkit-monitor` | Metrics and runtime monitoring |

Internal dependencies point inward only: `quadkit`,
`quadkit-web`, `quadkit-testing`, and `quadkit-cli` all resolve
`quadkit-contracts` from the package index — never from a workspace
checkout.

## Notable extras

Install extras with the familiar bracket syntax — for example
`pip install "quadkit-web[uvicorn]"`. Each extra is declared in that
package's `pyproject.toml`.

| Extra | Adds |
| --- | --- |
| `quadkit[web]` | `quadkit-web[granian]` — the full web stack with the default server |
| `quadkit[test]` | Core test dependencies |
| `quadkit-web[uvicorn]` / `[hypercorn]` | Alternative ASGI server backends |
| `quadkit-web[templates]` | Server-side template rendering |
| `quadkit-web[websocket]` | WebSocket support |
| `quadkit-testing[web]` | The web test client extras |

The server backend is selected automatically (Granian, then Uvicorn) and
can be pinned in [configuration](./configuration.md).

## Verify the install

```bash
python -c "from quadkit import Application; print(Application)"
```

Then continue to [your first app](./first-app.md).
