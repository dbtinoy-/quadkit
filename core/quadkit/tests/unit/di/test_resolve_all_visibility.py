"""Regression tests for Container.resolve_all visibility filtering and deduplication."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Protocol, runtime_checkable

import pytest

from quadkit.di.container import Container
from quadkit.di.context import clear_module_context, set_module_context


@runtime_checkable
class _AuthProtocol(Protocol):
    def name(self) -> str: ...


class _PrivateAuthImpl:
    def name(self) -> str:
        return "private-impl"


class _CallerModule:
    pass


class _ProviderModule:
    pass


@pytest.mark.asyncio
async def test_resolve_all_skips_private_concrete_type_and_deduplicates_shared_instance() -> (
    None
):
    """resolve_all skips ModuleVisibilityError subtypes and deduplicates shared instances."""
    container = Container()
    shared = _PrivateAuthImpl()
    container.singleton(_PrivateAuthImpl, instance=shared)
    container.singleton(_AuthProtocol, instance=shared)

    class _FakeGraph:
        def is_visible(self, _caller: object, service_type: object) -> bool:
            return service_type is _AuthProtocol

        def get_module(self, module_cls: object) -> object:
            if module_cls is _CallerModule:
                return SimpleNamespace(name="CallerModule", imports=[_ProviderModule])
            if module_cls is _ProviderModule:
                return SimpleNamespace(name="ProviderModule", imports=[])
            return None

        def find_modules_exporting(self, _service_type: object) -> list[object]:
            return []

    tokens = set_module_context(_CallerModule, _FakeGraph())
    try:
        resolved = await container.resolve_all(_AuthProtocol)
    finally:
        clear_module_context(tokens)

    assert resolved == [shared]
