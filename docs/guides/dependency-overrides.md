# Dependency overrides

The [dependency injection](../concepts/dependency-injection.md) model
pays its biggest dividend in tests: because controllers ask for
*protocols*, a test can hand the application a fake implementation with
one line — no mocking frameworks, no patching import sites.

Both files below are `docs/guides/examples/` in this repository, kept
byte-identical with this page, and the test file is executed in CI.

## The application: protocol in, binding out

<!-- snippet: examples/dependency_overrides_app.py -->
```python
"""Runnable companion to docs/guides/dependency-overrides.md.

A controller that asks for a *protocol* in its constructor, production
bindings from a provider, and a test that substitutes a fake before the
application boots:

    pytest test_dependency_overrides_app.py
"""

from typing import Protocol

from quadkit import Application
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.di.provider import Provider
from quadkit.web import Controller, WebModule, get


class Greeter(Protocol):
    """The service contract the controller depends on — not a class."""

    def greet(self) -> str: ...


class FriendlyGreeter:
    """The production implementation bound by the provider."""

    def greet(self) -> str:
        return "hello from friendly"


class GreeterProvider(Provider):
    """Binds the protocol to the production implementation."""

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(Greeter, instance=FriendlyGreeter())


class GreetingController(Controller):
    """Constructor injection: annotate with the protocol, get the binding."""

    def __init__(self, greeter: Greeter) -> None:
        self._greeter = greeter

    @get("/greet")
    async def greet(self) -> dict:
        return {"greeting": self._greeter.greet()}


def create_app() -> Application:
    app = Application()
    app.add_modules([WebModule.configure(controllers=[GreetingController])])
    app.add_provider(GreeterProvider())
    return app


app = create_app()
```

Note the pattern: the controller's `__init__` parameter is annotated
with the `Greeter` *protocol*, not `FriendlyGreeter`. The container
injects whatever is registered for the protocol at boot.

## The test: substitute before boot

<!-- snippet: examples/test_dependency_overrides_app.py -->
```python
"""Tests for dependency_overrides_app.py — runs from docs/guides/examples in CI."""

import pytest

from quadkit.testing import AppTestBed, WebTestBed

from dependency_overrides_app import Greeter, create_app


class ShoutyGreeter:
    """A test double: same contract, different behavior, zero config."""

    def greet(self) -> str:
        return "HELLO FROM SHOUTY"


@pytest.mark.asyncio
async def test_production_binding_is_used_by_default():
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/greet")
        assert response.json == {"greeting": "hello from friendly"}


@pytest.mark.asyncio
async def test_web_test_bed_override_before_boot():
    # Overrides must be registered *before* the application boots, because
    # providers run at boot: construct the bed, override, then enter.
    bed = WebTestBed(create_app())
    bed.override(Greeter, ShoutyGreeter())
    async with bed:
        response = bed.get("/greet")
        assert response.json == {"greeting": "HELLO FROM SHOUTY"}


@pytest.mark.asyncio
async def test_app_test_bed_overrides_mapping():
    # The same substitution, for application-level (non-HTTP) tests.
    async with AppTestBed.from_factory(
        create_app, overrides={Greeter: ShoutyGreeter()}
    ) as bed:
        greeter = await bed.app.container.resolve(Greeter)
        assert greeter.greet() == "HELLO FROM SHOUTY"
```

## The one rule that matters

**Register the override before the application boots.** Providers run at
boot — they bind `Greeter → FriendlyGreeter` and the container
constructs dependent objects from those bindings. An substitute that
arrives after boot is too late.

Two equivalent forms, both verified by the executed test above:

- **`WebTestBed`** — construct the bed, call
  `bed.override(Contract, fake)` (chainable), *then* enter the
  `async with`. This suits HTTP-level tests that assert on responses.
- **`AppTestBed.from_factory`** — pass
  `overrides={Contract: fake}` next to the factory (a callable or a
  `"my_app.app:create_app"` dotted string). This suits application-level
  tests that resolve services from the container directly
  (`await bed.app.container.resolve(...)`).

Because overrides replace *bindings*, the fake swims in the same stream
as production wiring: constructor injection, singleton lifetimes, and
provider boot logic all still apply — only the one contract is swapped.

## Next steps

- [Testing quickstart](../getting-started/testing.md) — the test-bed
  API end to end.
- [quadkit-testing reference](../reference/quadkit-testing.md) — the
  full test-bed surface.
