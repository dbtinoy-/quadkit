"""Boot-path coverage for @provide factories.

The decorator-shape tests prove `@provide` builds a Provider subclass;
these tests prove the production path: a real `Application.start()`
freezes the container and then boots providers, and FunctionProvider
binds its products inside the framework-managed registration window.
"""

from dataclasses import dataclass

import pytest

from quadkit import Application, Provider, provide
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.contracts.exceptions import ContainerError


@dataclass(frozen=True)
class Settings:
    prefix: str


class Greeter:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def greet(self, name: str) -> str:
        return f"{self._prefix}, {name}"


class Ticket:
    """Identity-only transient product."""


class SettingsProvider(Provider):
    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(Settings, Settings(prefix="hello"))


@provide
def greeter_provider(settings: Settings) -> Greeter:
    return Greeter(prefix=settings.prefix)


@provide(scope="transient")
def ticket_provider() -> Ticket:
    return Ticket()


async def test_provide_factories_boot_and_bind_after_freeze() -> None:
    async with Application.boot(
        providers=[SettingsProvider(), greeter_provider(), ticket_provider()]
    ) as app:
        first = await app.container.resolve(Greeter)
        second = await app.container.resolve(Greeter)
        assert first is second
        assert first.greet("ada") == "hello, ada"

        assert await app.container.resolve(Ticket) is not await app.container.resolve(
            Ticket
        )


async def test_container_stays_frozen_to_userland_after_boot() -> None:
    async with Application.boot(providers=[SettingsProvider()]) as app:
        assert app.container.is_frozen
        with pytest.raises(ContainerError, match="frozen"):
            app.container.singleton(Greeter, Greeter(prefix="late"))
