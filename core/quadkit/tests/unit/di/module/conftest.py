"""Shared fixtures for module system tests."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.di.module import DynamicModule, Module, module
from quadkit.di.provider import Provider, ProviderPriority


# ---------------------------------------------------------------------------
# Reusable provider stubs
# ---------------------------------------------------------------------------


class StubProviderA(Provider):
    name = "stub_a"
    priority = ProviderPriority.NORMAL
    provides = [type("ProtoA", (), {})]

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class StubProviderB(Provider):
    name = "stub_b"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class StubProviderC(Provider):
    name = "stub_c"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class StubProviderD(Provider):
    name = "stub_d"
    priority = ProviderPriority.INFRASTRUCTURE

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


# ---------------------------------------------------------------------------
# Reusable protocol stubs
# ---------------------------------------------------------------------------


class ProtoA:
    """Fake protocol for testing exports."""


class ProtoB:
    """Fake protocol for testing exports."""


class ProtoC:
    """Fake protocol for testing exports."""


class ProtoD:
    """Fake protocol for testing exports."""


class ProtoInternal:
    """Fake protocol that should NOT be exported."""


# ---------------------------------------------------------------------------
# Reusable provider with provides
# ---------------------------------------------------------------------------


class ProviderWithProvides(Provider):
    name = "provider_with_provides"
    provides = [ProtoA, ProtoB]

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class ProviderExportsC(Provider):
    name = "provider_exports_c"
    provides = [ProtoC]

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class ProviderExportsD(Provider):
    name = "provider_exports_d"
    provides = [ProtoD]

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class InternalOnlyProvider(Provider):
    name = "internal_only"
    provides = [ProtoInternal]

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass
