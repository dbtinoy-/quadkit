"""Feature tour: ContainerBuilder — a container without an application.

`Application.boot()` wires config, modules, and providers into one
container with managed lifecycles. When the goal is a script, a test, or
a small tool, that machinery is overhead: `ContainerBuilder` assembles
just the container. It speaks the same registration vocabulary —
singleton, transient, factory — and it can bridge application-world
providers in, so a `Provider` subclass that would otherwise wait for a
booted application stands up in one await. `build()` is an async
construction: provider factories may be coroutines, and the returned
object is a resolver with no web host, no modules, and no lifecycle
beyond close/stop.
"""

import pytest

from quadkit import Application, ContainerBuilder, Provider
from quadkit.contracts.core.di import ContainerRegistrarProtocol


class Engine:
    def __init__(self, cylinders: int = 4) -> None:
        self.cylinders = cylinders


class Gearbox:
    pass


@pytest.mark.asyncio
async def test_singletons_and_factories() -> None:
    container = await (
        ContainerBuilder()
        .add_singleton(Engine, lambda: Engine(cylinders=6))
        .build()
    )
    first = await container.resolve(Engine)
    assert first.cylinders == 6
    # Singletons are shared across resolutions.
    assert await container.resolve(Engine) is first


@pytest.mark.asyncio
async def test_transients_stay_fresh() -> None:
    container = await (
        ContainerBuilder().add_transient(Engine, lambda: Engine()).build()
    )
    first = await container.resolve(Engine)
    second = await container.resolve(Engine)
    assert first is not second


@pytest.mark.asyncio
async def test_providers_bridge_into_standalone_containers() -> None:
    class GearboxProvider(Provider):
        async def register(self, container: ContainerRegistrarProtocol) -> None:
            container.singleton(Gearbox, Gearbox())

    container = await ContainerBuilder().add_provider(GearboxProvider()).build()
    assert isinstance(await container.resolve(Gearbox), Gearbox)

    # The provider vocabulary is identical everywhere: the same provider
    # class also runs through a booted application lifecycle.
    async with Application.boot(providers=[GearboxProvider()]) as app:
        assert isinstance(await app.container.resolve(Gearbox), Gearbox)
