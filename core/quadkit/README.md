# quadkit

![Quadkit](https://raw.githubusercontent.com/dbtinoy-/quadkit/main/banner.jpg)

[![PyPI](https://img.shields.io/pypi/v/quadkit?color=%2322c55e&label=pypi)](https://pypi.org/project/quadkit/)
[![Python](https://img.shields.io/pypi/pyversions/quadkit?color=%2322c55e)](https://pypi.org/project/quadkit/)
[![License](https://img.shields.io/pypi/l/quadkit?color=%2322c55e)](https://github.com/dbtinoy-/quadkit/blob/main/LICENSE)

Async-first application framework for Python: dependency-injection
container, application lifecycle, typed configuration, and the `Result`
error model. This is the core package; everything else published from
this repository builds on it.

For application developers — write providers and modules, bind
contracts, and let one container boot them in order.

What's in the box:

- **DI container** — singleton, scoped, and transient bindings, async
  factories, override support for tests; the graph resolves once, at
  boot.
- **Provider & module system** — providers register bindings, boot
  resources, and shut them down in reverse order; modules compose
  providers into reusable units.
- **Typed configuration** — `application.yaml` validated against
  dataclass models at boot (unknown keys fail fast), every key
  overridable via `QK_*` environment variables, profiles via `QK_PROFILE`.
- **The `Result` model** — expected failures are values
  (`Ok`/`Err`), not exceptions; `ResultPipeline` chains them fluently
  while keeping the error type visible to mypy.
- **Structured logging** — `get_logger()` gives every service a
  keyed, structlog-style logger out of the box.
- **Domain primitives** — `AggregateRoot`, `Entity`, `DomainEvent`,
  `AbstractUnitOfWork` for DDD-style modelling without a framework
  tax.

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
uv add quadkit
# batteries-included web stack:
uv add "quadkit[web]"
```

Requires **Python >= 3.11**.

## Minimal working example

```python
import asyncio

from quadkit import Application
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.di.provider import Provider


class Settings:
    greeting = "hello, quadkit"


class SettingsProvider(Provider):
    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(Settings, instance=Settings())


async def main() -> None:
    app = Application()
    app.add_provider(SettingsProvider())
    await app.start()
    try:
        settings = await app.container.resolve(Settings)
        print(settings.greeting)
    finally:
        await app.stop()


asyncio.run(main())
```

For the web quickstart (a real endpoint in minutes), see
[the docs](https://dbtinoy-.github.io/quadkit/getting-started/first-app/).

## Expected failures are values

`Result[T, E]` keeps the happy path and the failure path in the type
system — `pipeline()` chains fallible steps without `try/except`
pyramids, and `mypy` sees the error type at every step:

```python
from quadkit.result import Err, Ok, pipeline


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
```

In controllers, returning an `Err` renders as an RFC 7807 problem
response automatically — see the
[error-handling guide](https://dbtinoy-.github.io/quadkit/guides/error-handling/).

## Optional extras

| Extra | Contents |
| --- | --- |
| `quadkit[web]` | `quadkit-web[granian]` — the full web stack |
| `quadkit[test]` | `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock` |
| `quadkit[security]` | `cryptography` (signing/token helpers) |
| `quadkit[codegen]` | code generation toolchain |
| `quadkit[docs]` / `[dev]` | documentation / development tooling |

## Public API entry points

```python
from quadkit import Application, Result, Ok, Err
from quadkit.di.provider import Provider
from quadkit.di.container import Container
from quadkit.config import BaseConfig, ConfigLoader
from quadkit.logging import get_logger
from quadkit.domain import AggregateRoot, Entity, DomainEvent, AbstractUnitOfWork
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
```

Providers can also define an async `boot()` (acquire resources) and
`shutdown()` (release them, in reverse registration order) — the
container drives the whole lifecycle.

Concepts: [contracts](https://dbtinoy-.github.io/quadkit/concepts/contracts/) ·
[dependency injection](https://dbtinoy-.github.io/quadkit/concepts/dependency-injection/) ·
[modules](https://dbtinoy-.github.io/quadkit/concepts/modules/) ·
[lifecycle](https://dbtinoy-.github.io/quadkit/concepts/lifecycle/) ·
[async model](https://dbtinoy-.github.io/quadkit/concepts/async-model/).

## Configuration

`application.yaml` at the working directory, validated against typed
config models at boot (unknown keys fail fast); application metadata
lives at the root (`name`, `version`, `description`); every typed key
overrides from the environment with `QK_<SECTION>__<KEY>`. Use
`QK_PROFILE` to select a profile.

```bash
QK_QUADKIT__LOGGING__LEVEL=DEBUG   # fold into the root `logging` section
QK_PROFILE=production              # select a profile block
```

See
[configuration](https://dbtinoy-.github.io/quadkit/getting-started/configuration/).

## Error handling

`Result[T, E]` for expected domain failures; the
`quadkit-contracts` exception hierarchy (`QuadkitError → DomainError →
NotFoundError`, `ValidationError`, `ConflictError`, ...) for everything
else. The web layer renders both as problem responses — see
[error handling](https://dbtinoy-.github.io/quadkit/guides/error-handling/).

## Testing

Pair with `quadkit-testing`: `AppTestBed.from_factory(create_app)` boots
your application in-process (with `overrides={Contract: fake}` for test
doubles), no server required. See
[testing](https://dbtinoy-.github.io/quadkit/getting-started/testing/).

## Security

Never put secrets in `application.yaml` — pass them through `QK_*`
environment variables or a secret store. Unexpected exceptions never
leak internals to clients. See
[secure configuration](https://dbtinoy-.github.io/quadkit/security/secure-configuration/) and
report vulnerabilities privately per
[SECURITY.md](https://github.com/dbtinoy-/quadkit/blob/main/SECURITY.md).

## Stability

Version `0.0.42` in the `0.x` series, released in lockstep with the
other four distributions; APIs may change between minor versions until
1.0 — pin an exact version
(`quadkit==0.0.42`) or a tight range (`>=0.0.42,<0.1.0`). Full policy:
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
