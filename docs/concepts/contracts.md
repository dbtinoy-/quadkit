# Contracts

`quadkit-contracts` is the foundation package: **protocols, shared
types, and exceptions — with zero runtime dependencies.** Everything
else in the framework talks through these contracts rather than through
concrete implementations.

## Why contracts

Packages depend on interfaces, not on each other. A provider is swapped
by configuration — not by rewriting call sites — as long as both
implementations satisfy the same protocol. That is what makes the
framework's "same contract, one config line" promise hold.

```text
quadkit-contracts     protocols, types, exceptions (zero deps)
        ↑
quadkit               container, application, lifecycle
        ↑
quadkit-web           controllers, routing, middleware
```

Dependency direction is fixed: packages may depend *inward* on
contracts, never outward on siblings by name.

## What a contract looks like

Protocols are plain `typing.Protocol` classes with typed method
signatures — structural, so your own classes conform without
inheriting anything:

```python
from quadkit.contracts.core.di import ContainerResolverProtocol


def build_settings(resolver: ContainerResolverProtocol):
    # typed against the protocol, not a concrete container
    ...
```

## Errors as values: `Result[T, E]`

Fallible operations return a `Result` instead of raising for expected
failures, so error paths stay visible in type signatures:

```python
from quadkit import Err, Ok, Result


def parse_port(raw: str) -> Result[int, str]:
    if raw.isdigit():
        return Ok(int(raw))
    return Err(f"not a number: {raw!r}")


match parse_port("8000"):
    case Ok(port):
        print(f"serving on {port}")
    case Err(reason):
        print(f"bad config: {reason}")
```

Unexpected, exceptional defects still raise through the framework's
exception hierarchy (`quadkit-contracts` exceptions); `Result` is for
the failures your design expects.

Next: [dependency injection](./dependency-injection.md) puts contracts
to work in the container.
