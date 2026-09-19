"""Boot-time module-visibility enforcement (cross-module surface audit).

Registration attribution links every service to the module whose provider
registered it, so the resolve gate can distinguish three cases the old
"nobody exports it" fallback conflated: framework/standalone services
(unrestricted), a module's own private services (visible to that module),
and another module's unexported services (a visibility violation).
"""

import pytest

from quadkit import Application, Module, Provider, create_module, provide
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.contracts.exceptions.provider import ModuleVisibilityError


class Secret:
    """Provided by VaultModule, never exported."""


class Shared:
    """Provided and exported by VaultModule."""


class VaultSecrets:
    """Private store consumed only inside VaultModule."""


class VaultReader:
    def __init__(self) -> None:
        self.read = False


class VaultProvider(Provider):
    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(Secret, Secret())
        container.singleton(Shared, Shared())
        container.singleton(VaultSecrets, VaultSecrets())


@create_module(providers=[VaultProvider], exports=[Shared])
class VaultModule(Module):
    pass


class Greeter:
    pass


@provide
def greedy_factory(secret: Secret) -> Greeter:
    return Greeter()


@provide
def fine_factory(shared: Shared) -> Greeter:
    return Greeter()


@provide
def internal_factory(secrets: VaultSecrets) -> VaultReader:
    return VaultReader()


async def test_unexported_import_raises_visibility_error_with_fix_hint() -> None:
    @create_module(providers=[greedy_factory], imports=[VaultModule])
    class AppModule(Module):
        pass

    with pytest.raises(ModuleVisibilityError, match="not exported"):
        async with Application.boot(modules=[AppModule]):
            pass


async def test_exported_service_crosses_the_module_boundary() -> None:
    @create_module(providers=[fine_factory], imports=[VaultModule])
    class AppModule(Module):
        pass

    async with Application.boot(modules=[AppModule]) as app:
        assert isinstance(await app.container.resolve(Greeter), Greeter)


async def test_module_consumes_its_own_private_services() -> None:
    @create_module(providers=[internal_factory], imports=[])
    class ReaderModule(Module):
        pass

    @create_module(providers=[VaultProvider], exports=[Shared])
    class IsolatedVault(Module):
        pass

    # The reader module owns VaultReader... but VaultSecrets lives in the
    # vault — so give the vault its own internal consumer instead.
    @provide
    def vault_internal(secrets: VaultSecrets) -> Shared:
        return Shared()

    @create_module(providers=[VaultProvider, vault_internal], exports=[Shared])
    class SelfContainedVault(Module):
        pass

    async with Application.boot(modules=[SelfContainedVault]):
        pass  # own private provider consumed at own boot: allowed


async def test_runtime_resolution_outside_boot_is_flat() -> None:
    @create_module(providers=[fine_factory], imports=[VaultModule])
    class AppModule(Module):
        pass

    async with Application.boot(modules=[AppModule]) as app:
        # Visibility is a boot-time wiring audit. Resolution outside a
        # module context (runtime controllers, scripts, tests) stands
        # outside it: the root container sees the full registry.
        assert isinstance(await app.container.resolve(Secret), Secret)
