"""Shared fixtures and module definitions for graph reflection integration tests."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.di.module import DynamicModule, Module, ModuleCompiler, module
from quadkit.di.provider import Provider, ProviderPriority


class CoreService:
    pass


class CacheService:
    pass


class WebHandler:
    pass


class _CoreProvider(Provider):
    name = "core_provider"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class _CacheProvider(Provider):
    name = "cache_provider"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class _WebProvider(Provider):
    name = "web_provider"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


@module(providers=[_CoreProvider], exports=[CoreService])
class CoreModule(Module):
    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(
            module=cls,
            providers=[_CoreProvider],
            exports=[CoreService],
        )


@module(providers=[_CacheProvider], imports=[CoreModule], exports=[CacheService])
class CacheModule(Module):
    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(
            module=cls,
            providers=[_CacheProvider],
            imports=[CoreModule],
            exports=[CacheService],
        )


@module(
    providers=[_WebProvider],
    imports=[CoreModule, CacheModule],
    exports=[WebHandler],
)
class WebModule(Module):
    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(
            module=cls,
            providers=[_WebProvider],
            imports=[CoreModule, CacheModule],
            exports=[WebHandler],
        )


@pytest.fixture
def graph():
    return ModuleCompiler().compile([WebModule])
