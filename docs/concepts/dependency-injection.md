# Dependency injection

The DI container wires your application at boot from declarations, not
from call-site `import` soup. Components ask for contracts in their
constructors; the container supplies implementations.

## The container

Three registration shapes cover most needs:

```python
from quadkit import Container

container = Container()

# already built — hand it over
container.singleton(Settings, instance=Settings())

# built lazily on first resolve
container.singleton(Cache, factory=lambda: Cache())

# complex wiring — a factory can also be an async callable
container.singleton(Client, factory=lambda: build_client())
```

Resolving is by type — registering against a contract type is what
keeps implementations swappable.

## Providers

A **provider** packages related registrations and their lifecycle in
one class. Subclass `Provider` and implement two phases:

```python
from quadkit.di.provider import Provider

from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)


class BillingProvider(Provider):
    async def register(self, container: ContainerRegistrarProtocol) -> None:
        # bind what exists and how to build it — runs first
        container.singleton(BillingGateway, factory=self._build_gateway)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        # resolve and initialize — runs after all registrations complete
        # and the container is frozen; I/O is allowed here
        self._gateway = await container.resolve(BillingGateway)
```

Providers attach to the application with `app.add_providers([...])` (or
through [modules](./modules.md), which bundle providers with their
controllers). `register()` runs for every provider before any `boot()`,
so boot order only depends on declared intent, not import order.

Do not re-register framework-owned keys (like the web module's config)
from your own providers — the owning module already binds them.

## Constructor injection by contract

Controllers and services declare what they need as typed constructor
parameters; the container resolves them from the registrations above.
Because dependencies are typed against protocols, an implementation
change is a registration change — nothing else.

## Testing

In tests, replace registrations instead of monkey-patching modules.
The web test bed overrides fluently before the app boots:

```python
# inside an async test using WebTestBed(create_app()) as bed:
bed.override(BillingGateway, FakeBillingGateway())
```

See [testing](../getting-started/testing.md) for the full harness and
[example-hub](https://github.com/dbtinoy-/quadkit/blob/main/examples/example-hub/src/example_hub/di/provider.py)
for a complete, commented provider in a real application.
