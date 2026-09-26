# quadkit-contracts

![Quadkit](https://raw.githubusercontent.com/dbtinoy-/quadkit/main/banner.jpg)

[![PyPI](https://img.shields.io/pypi/v/quadkit-contracts?color=%2322c55e&label=pypi)](https://pypi.org/project/quadkit-contracts/)
[![Python](https://img.shields.io/pypi/pyversions/quadkit-contracts?color=%2322c55e)](https://pypi.org/project/quadkit-contracts/)
[![License](https://img.shields.io/pypi/l/quadkit-contracts?color=%2322c55e)](https://github.com/dbtinoy-/quadkit/blob/main/LICENSE)

Protocols, shared types, and the exception hierarchy for Quadkit —
with **zero runtime dependencies** beyond `typing-extensions`. Every
published package depends on contracts; no implementation package
defines a protocol another package depends on.

For integration authors who need to bind against Quadkit interfaces
without pulling in the framework — thin adapters import only this
package.

## The quadkit family

| Package | Role |
| --- | --- |
| [`quadkit-contracts`](https://pypi.org/project/quadkit-contracts/) | zero-dependency protocols, types, exception hierarchy |
| [`quadkit`](https://pypi.org/project/quadkit/) | the framework core — DI container, modules, config, logging, `Result` |
| [`quadkit-web`](https://pypi.org/project/quadkit-web/) | ASGI layer — controllers, routing, middleware, OpenAPI docs |
| [`quadkit-cli`](https://pypi.org/project/quadkit-cli/) | project scaffolding and code generators |
| [`quadkit-testing`](https://pypi.org/project/quadkit-testing/) | in-process test beds, fakes, fixtures |

## Installation

```bash
uv add quadkit-contracts
```

Requires **Python >= 3.11**.

## Minimal working example

Protocols are structural: implement the shape, and the container binds
your implementation to the contract.

```python
from typing import Protocol

from quadkit.result import Err, Ok, Result


class UserNotFound(Exception):
    """A domain failure the caller is expected to handle."""


class UserRepository(Protocol):
    async def find_name(self, user_id: str) -> Result[str, UserNotFound]: ...


async def find_name_or_unknown(repo: UserRepository, user_id: str) -> str:
    result = await repo.find_name(user_id)
    return result.match(ok=lambda name: name, err=lambda e: "unknown")
```

The domain-model side — pydantic-based entities and events:

```python
from quadkit.contracts.domain.events import DomainEvent
from quadkit.domain import AggregateRoot


class UserCreated(DomainEvent):
    user_id: str
    email: str


class User(AggregateRoot):
    email: str
```

## The Result toolkit

`Result` is this package's flagship: expected failures become values
the type system can see. `pipeline()` chains fallible steps fluently;
`as_result` wraps exception-raising calls without swallowing the
unexpected ones:

```python
from quadkit.result import Err, Ok, as_result, pipeline


def parse_port(raw: str):
    try:
        port = int(raw)
    except ValueError as exc:
        return Err(exc)
    if not 1 <= port <= 65535:
        return Err(ValueError(f"port out of range: {port}"))
    return Ok(port)


result = (
    pipeline("8080")  # infallible start
    .then(parse_port)  # Result[int, ValueError]
    .map(lambda port: f"listening on :{port}")
    .finalize()  # Result[str, ValueError]
)


@as_result(ValueError, TypeError)  # only these become Err
async def load_setting(raw: str) -> int:
    return int(raw)
```

`collect()` gathers many results, `partition()` splits them into
successes and failures, and `try_catch()` is the sync counterpart of
`as_result`. Full walkthrough:
[contracts — errors as values](https://dbtinoy-.github.io/quadkit/concepts/contracts/).

## Optional extras

| Extra | Contents |
| --- | --- |
| `quadkit-contracts[dev]` / `[test]` | development / test tooling |

## Public API entry points

| Module | Contents |
| --- | --- |
| `quadkit.result` | `Result[T, E]`, `Ok`, `Err`, `as_result()`, `as_result_sync()`, `try_catch()`, `ResultPipeline` |
| `quadkit.contracts.core.di` | `ContainerRegistrarProtocol`, `ContainerResolverProtocol` |
| `quadkit.contracts.core.provider` | `ProviderProtocol`, `ProviderPriority` |
| `quadkit.contracts.core.registry` | `RegistryProtocol`, `StrategyRegistryProtocol`, `BackendRegistryProtocol` |
| `quadkit.contracts.domain.base` | `DomainModelProtocol`, `ID` |
| `quadkit.contracts.domain.events` | `DomainEvent` |
| `quadkit.contracts.exceptions` | `QuadkitError` and the full hierarchy |
| `quadkit.contracts.infra.cache` | `CacheBackendProtocol` |
| `quadkit.contracts.data` | `DatabaseProviderProtocol` |
| `quadkit.contracts.security.secrets` | `SecretStoreProtocol` |

Deep-dive: [contracts](https://dbtinoy-.github.io/quadkit/concepts/contracts/) in the docs
set.

## Configuration

None — this package carries types, not behavior.

## Error handling

The taxonomy lives here: `QuadkitError` is the root; `DomainError`
subclasses describe expected business failures (`NotFoundError`,
`ValidationError`, `ConflictError`, `PermissionDeniedError`, ...). The
web layer maps them to HTTP problem responses — see
[error handling](https://dbtinoy-.github.io/quadkit/guides/error-handling/).

## Testing

Protocols are tested by conformance: implement the shape, run your
implementation through the behavior callers rely on. `quadkit-testing`
ships the fakes used by the framework's own tests.

## Security

This package ships interfaces and types only — no network, no I/O, no
runtime dependencies. Report vulnerabilities privately per
[SECURITY.md](https://github.com/dbtinoy-/quadkit/blob/main/SECURITY.md).

## Stability

Version `0.0.42` in the `0.x` series, released in lockstep with the
other four distributions. **These protocols carry no compatibility
guarantee yet**: minor releases may add, rename, or remove members
while the framework is pre-1.0. Because this package is published
whole, protocols for not-yet-released areas are the most likely to
change; the settled ones are those exercised by `quadkit`,
`quadkit-web`, `quadkit-testing`, and `quadkit-cli`. Pin an exact
version (`quadkit-contracts==0.0.42`) when you depend on these types
directly. Full policy:
[stability and compatibility](https://dbtinoy-.github.io/quadkit/reference/stability/).

## Links

- **Documentation** — <https://dbtinoy-.github.io/quadkit/>
- **Getting started** — <https://dbtinoy-.github.io/quadkit/getting-started/installation/>
- **Changelog** — <https://github.com/dbtinoy-/quadkit/blob/main/CHANGELOG.md>
- **Issues** — <https://github.com/dbtinoy-/quadkit/issues>
- **Security** — report privately per [SECURITY.md](https://github.com/dbtinoy-/quadkit/blob/main/SECURITY.md)
- **Contributing** — [CONTRIBUTING.md](https://github.com/dbtinoy-/quadkit/blob/main/CONTRIBUTING.md)

Apache-2.0 — see [LICENSE](https://github.com/dbtinoy-/quadkit/blob/main/LICENSE). "Quadkit" and the
Quadkit logo are trademarks of the project — see
[TRADEMARK.md](https://github.com/dbtinoy-/quadkit/blob/main/TRADEMARK.md).
