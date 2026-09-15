# quadkit-contracts

Core types and protocols for the Quadkit Framework.

> **Unstable (0.x).** These protocols are **not** covered by a compatibility
> guarantee yet. Minor releases may add, rename, or remove members while the
> framework is pre-1.0.
>
> This package is published whole, so it also carries protocols for Quadkit
> packages that are not released yet. Those are the most likely to change:
> they have not been exercised by a public implementation. Protocols used by
> `quadkit`, `quadkit-web`, `quadkit-testing` and `quadkit-cli` are the
> settled ones.
>
> Pin an exact version (`quadkit-contracts==0.1.1`) if you depend on these
> types directly. Stability guarantees begin at 1.0.

---

## Overview

`quadkit-contracts` defines all Protocols, base types, Result types, domain
models, and exception hierarchies used across the Quadkit ecosystem. It has
**zero runtime dependencies** so it can be imported into any package — including
thin integrations — without pulling in the full framework.

This package is the single source of truth for every interface in Quadkit.
All other packages depend on contracts; no implementation package defines its
own protocol that another package depends on.


> Full documentation: [docs.quadkit.dev](https://docs.quadkit.dev)
## Install

```bash
uv add quadkit-contracts
```

## Quick Start

### Result type

```python
from quadkit.result import Result, Ok, Err


async def find_user(user_id: str) -> Result[User, UserNotFound]:
    user = await db.get(user_id)
    if not user:
        return Err(UserNotFound(user_id))
    return Ok(user)


# Safe consumption
result = await find_user("u-123")
name = result.match(ok=lambda u: u.name, err=lambda e: "unknown")
```

### Domain models

```python
from quadkit.domain.models import Entity, ValueObject
from quadkit.domain import AggregateRoot
from quadkit.contracts.domain.events import DomainEvent


class UserCreated(DomainEvent):
    user_id: str
    email: str


class User(AggregateRoot):
    email: str
```

### Protocols

```python
from quadkit.contracts.infra.cache import CacheBackendProtocol
from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.contracts.security.secrets import SecretStoreProtocol
```

## Key Modules

| Module | What it contains |
|--------|-----------------|
| `quadkit.result` | `Result[T, E]`, `Ok`, `Err`, `as_result()`, `as_result_sync()`, `try_catch()`, `ResultPipeline` |
| `quadkit.domain.models` | `DomainModel`, `Entity`, `ValueObject` (concrete domain models, in core `quadkit`) |
| `quadkit.domain` | `AggregateRoot` (re-exported from `quadkit.domain.models.aggregate`) |
| `quadkit.contracts.domain.base` | `DomainModelProtocol`, `ID` |
| `quadkit.contracts.domain.events` | `DomainEvent` |
| `quadkit.contracts.infra.cache` | `CacheBackendProtocol` |
| `quadkit.contracts.data` | `DatabaseProviderProtocol` |
| `quadkit.contracts.security.secrets` | `SecretStoreProtocol` |
| `quadkit.contracts.core.di` | `ContainerRegistrarProtocol`, `ContainerResolverProtocol` |
| `quadkit.contracts.core.provider` | `ProviderProtocol`, `ProviderPriority` |
| `quadkit.contracts.core.registry` | `RegistryProtocol`, `StrategyRegistryProtocol`, `BackendRegistryProtocol` |
| `quadkit.contracts.exceptions` | `QuadkitError`, full error hierarchy |

## Key Source Files

| File | What it contains |
|------|-----------------|
| `src/quadkit/contracts/__init__.py` | Lazy-loading re-exports of all public types |
| `src/quadkit/result/` | Result type and Ok/Err helpers |
| `src/quadkit/contracts/domain/` | `DomainModelProtocol`, `DomainEvent` |
| `src/quadkit/contracts/core/` | Container, Provider, Registry protocols |
| `src/quadkit/contracts/exceptions/` | QuadkitError and domain error hierarchies |

## Design Principles

- **Minimal dependencies** — `typing-extensions` only; no framework imports
- **Protocol-only** — defines interfaces, never implementations
- **Central contract** — every other Quadkit package depends on this one, so
  changes here are the most disruptive kind the project can make
