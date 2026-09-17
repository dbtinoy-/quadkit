"""Feature tour: `@provide` — write a function, get a Provider.

The `@provide` decorator turns a factory function into a ready-made
`Provider` subclass: the return annotation is the contract the product
is registered under, the parameters are resolved from the container
during boot, and `scope=`/`name=` tune lifetime and registration
metadata. No provider class boilerplate, and no annotation drift —
forgetting the return type fails loudly at import time, not during a
boot in production.
"""

from dataclasses import dataclass

import pytest

from quadkit import Application, Provider, provide
from quadkit.contracts.core.di import ContainerRegistrarProtocol


@dataclass(frozen=True)
class Settings:
    prefix: str


class Greeter:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def greet(self, name: str) -> str:
        return f"{self._prefix}, {name}"


class Ticket:
    """Transients get a fresh object per resolution — identity is the proof."""


class SettingsProvider(Provider):
    """Plain providers and `@provide` factories mix freely in one boot."""

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(Settings, Settings(prefix="hello"))


@provide
def greeter_provider(settings: Settings) -> Greeter:
    # Singleton by default; `settings` is resolved from the container
    # when the provider boots.
    return Greeter(prefix=settings.prefix)


@provide(scope="transient")
def ticket_provider() -> Ticket:
    return Ticket()


@pytest.mark.asyncio
async def test_factories_boot_with_container_resolved_parameters() -> None:
    async with Application.boot(
        providers=[SettingsProvider(), greeter_provider(), ticket_provider()]
    ) as app:
        container = app.container

        first = await container.resolve(Greeter)
        second = await container.resolve(Greeter)
        assert first is second  # singleton is the default scope
        assert first.greet("ada") == "hello, ada"  # parameter was injected

        ticket_a = await container.resolve(Ticket)
        ticket_b = await container.resolve(Ticket)
        assert ticket_a is not ticket_b  # scope="transient" honored


def test_missing_return_annotation_fails_at_decoration_time() -> None:
    with pytest.raises(TypeError, match="return type annotation"):

        @provide
        def forgotten():  # no `-> Type`, no contract — caught immediately
            return object()
