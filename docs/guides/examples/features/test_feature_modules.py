"""Feature tour: modules — explicit surfaces, boot-time enforcement.

Applications compose from modules, and each module declares its public
surface: `providers` it owns, `exports` it publishes, `imports` it
needs. Three guarantees make the declarations load-bearing rather than
decorative. Modules not in the import graph stay inert — nothing
registers by accident. At boot, cross-module wiring is audited: a
consumer can inject another module's service only when that module
exports it, and an unexported reach fails loudly with the fix in the
message. And the audit is deliberately boot-scoped: at runtime the
container resolves flat for speed, with no module context to consult.
"""

import pytest

from quadkit import Application, Module, Provider, create_module, provide
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.contracts.exceptions.container import UnresolvableDependencyError
from quadkit.contracts.exceptions.provider import ModuleVisibilityError


class Secret:
    """Vault-internal: provided by VaultModule, never exported."""


class Shared:
    """The one type VaultModule publishes."""


class VaultProvider(Provider):
    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(Secret, Secret())
        container.singleton(Shared, Shared())


@create_module(providers=[VaultProvider], exports=[Shared])
class VaultModule(Module):
    pass


class Greeter:
    def __init__(self, ok: bool) -> None:
        self.ok = ok


@provide
def shared_greeter(shared: Shared) -> Greeter:
    return Greeter(ok=True)


@provide
def greedy_greeter(secret: Secret) -> Greeter:
    return Greeter(ok=True)


@pytest.mark.asyncio
async def test_unimported_modules_stay_inert() -> None:
    # VaultModule was never passed to the application: its providers do
    # not exist as far as the container is concerned.
    async with Application.boot(modules=[]) as app:
        with pytest.raises(UnresolvableDependencyError):
            await app.container.resolve(Shared)

    async with Application.boot(modules=[VaultModule]) as app:
        assert isinstance(await app.container.resolve(Shared), Shared)


@pytest.mark.asyncio
async def test_exports_are_the_public_surface() -> None:
    @create_module(providers=[shared_greeter], imports=[VaultModule])
    class OrdersModule(Module):
        pass

    # Shared is exported: the factory injects it across the boundary.
    async with Application.boot(modules=[OrdersModule]) as app:
        assert (await app.container.resolve(Greeter)).ok is True

    @create_module(providers=[greedy_greeter], imports=[VaultModule])
    class LeakyOrdersModule(Module):
        pass

    # Secret is not exported: the reach fails at boot, naming the fix.
    with pytest.raises(ModuleVisibilityError, match="not exported") as caught:
        async with Application.boot(modules=[LeakyOrdersModule]):
            pass
    error = str(caught.value)
    assert "VaultModule" in error
    assert "Export Secret" in error


@pytest.mark.asyncio
async def test_visibility_is_a_boot_time_audit() -> None:
    @create_module(providers=[shared_greeter], imports=[VaultModule])
    class OrdersModule(Module):
        pass

    async with Application.boot(modules=[OrdersModule]) as app:
        # Runtime resolution carries no module context — controllers,
        # scripts, and this test stand outside the audit. The root
        # container resolves flat, unexported services included.
        assert isinstance(await app.container.resolve(Secret), Secret)
