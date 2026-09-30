# quadkit — core framework reference

The core distribution: dependency-injection container, application
lifecycle, typed configuration, and the `Result` error type. Every other
distribution resolves from it; `quadkit-contracts` carries the protocols
it binds against.

- **Install**: `pip install quadkit` · Python `>= 3.11`
- **Version** (lockstep with all thirteen distributions): `0.0.44`
  → [stability policy](./stability.md)
- **Changelog**: `core/quadkit/CHANGELOG.md` in this repository
- **Issues**: <https://github.com/dbtinoy-/quadkit/issues>

## Extras

Verified against the package's `pyproject.toml`:

| Extra | Contents |
| --- | --- |
| `quadkit[web]` | `quadkit-web[granian]` — the full web stack |
| `quadkit[test]` | `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock` |
| `quadkit[security]` | `cryptography` (token/signing helpers) |
| `quadkit[codegen]` | Code generation toolchain |
| `quadkit[docs]` / `[dev]` | Documentation and development tooling |

## Public entry points

```python
from quadkit import Application, Result, Ok, Err   # app assembly + results
from quadkit.di.provider import Provider           # register → boot lifecycle
from quadkit.di.container import Container         # resolve() is async
from quadkit.logging import get_logger             # structured logging
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,                    # register() parameter
    ContainerResolverProtocol,                     # boot() parameter
)
```

- **`Application`** — the app: `add_modules`, `add_provider`, lazy
  two-phase boot, `AppState` lifecycle
  (`CREATED → STARTING → RUNNING → STOPPED`). See
  [lifecycle](../concepts/lifecycle.md).
- **`Result` / `Ok` / `Err`** — railway error handling; the web layer
  maps `Err` values to HTTP statuses. See
  [contracts](../concepts/contracts.md) and
  [error handling](../guides/error-handling.md).
- **`Provider`** — subclass with `async def register(...)` (bind, no I/O)
  and `async def boot(...)` (resolve + initialize). See
  [dependency injection](../concepts/dependency-injection.md).
- **`Container`** — `await container.resolve(Contract)`; bindings via
  `container.singleton(Contract, instance=...)` / `factory=...`.

## Configuration

`application.yaml` at the working directory, validated against typed
sections at boot; `QK_<SECTION>__<KEY>` environment variables override.
See [configuration](../getting-started/configuration.md).

## Error handling

`quadkit-contracts.exceptions` carries the taxonomy
(`QuadkitError → DomainError → NotFoundError`, `ValidationError`,
`ConflictError`, ...); the web layer renders them as problem responses.
See [error handling](../guides/error-handling.md).

## Testing and security

Pair with [`quadkit-testing`](./quadkit-testing.md) (`AppTestBed`,
`WebTestBed`). Security posture: no secrets in YAML — environment or
secret stores; see [secure configuration](../security/secure-configuration.md)
and [vulnerability reporting](../security/vulnerability-reporting.md).
