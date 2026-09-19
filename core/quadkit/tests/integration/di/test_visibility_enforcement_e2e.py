from __future__ import annotations

import pytest

from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.context import (
    _current_module,
    _module_graph,
    check_visibility,
    clear_module_context,
    get_current_module,
    set_module_context,
)
from quadkit.di.module.base import Module
from quadkit.di.module.compiler import ModuleCompiler
from quadkit.di.module.decorator import module
from quadkit.di.module.dynamic import DynamicModule
from quadkit.di.provider import Provider


# Service protocols
class CoreService:
    pass


class CacheService:
    pass


class _CoreProvider(Provider):
    name = "core_provider"
    priority = ProviderPriority.NORMAL

    async def register(self, container):
        pass


class _CacheProvider(Provider):
    name = "cache_provider"
    priority = ProviderPriority.NORMAL

    async def register(self, container):
        pass


@module(providers=[_CoreProvider], exports=[CoreService])
class CoreModule(Module):
    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(
            module=cls, providers=[_CoreProvider], exports=[CoreService]
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


@pytest.fixture(autouse=True)
def _reset_context():
    """Ensure ContextVars are clean before/after each test."""
    tok_m = _current_module.set(None)
    tok_g = _module_graph.set(None)
    yield
    _current_module.reset(tok_m)
    _module_graph.reset(tok_g)


@pytest.fixture
def compiled_graph():
    """Compile a real module graph: CacheModule → CoreModule."""
    return ModuleCompiler().compile([CacheModule])


class TestCheckVisibilityWithRealGraph:
    """Test check_visibility() with a real compiled module graph."""

    def test_module_can_access_own_exports(self, compiled_graph) -> None:
        """CacheModule exports CacheService → CacheModule can access it."""
        tokens = set_module_context(CacheModule, compiled_graph)
        try:
            assert check_visibility(CacheService) is True
        finally:
            clear_module_context(tokens)

    def test_module_can_access_imported_exports(self, compiled_graph) -> None:
        """CacheModule imports CoreModule → can access CoreService."""
        tokens = set_module_context(CacheModule, compiled_graph)
        try:
            assert check_visibility(CoreService) is True
        finally:
            clear_module_context(tokens)

    def test_module_cannot_access_unexported_service(self, compiled_graph) -> None:
        """CoreModule does not export CacheService."""
        tokens = set_module_context(CoreModule, compiled_graph)
        try:
            assert check_visibility(CacheService) is False
        finally:
            clear_module_context(tokens)

    def test_no_context_returns_true(self, compiled_graph) -> None:
        """No module context set → unrestricted (standalone usage)."""
        # No context set, so check_visibility should return True
        assert check_visibility(CoreService) is True


class TestModuleContextLifecycle:
    """Test the full lifecycle of module context set/get/clear."""

    def test_set_and_get_current_module(self, compiled_graph) -> None:
        """Setting module context makes it retrievable via get_current_module."""
        tokens = set_module_context(CoreModule, compiled_graph)
        try:
            assert get_current_module() is CoreModule
        finally:
            clear_module_context(tokens)

    def test_clear_resets_context(self, compiled_graph) -> None:
        """Clearing context resets get_current_module to None."""
        tokens = set_module_context(CoreModule, compiled_graph)
        clear_module_context(tokens)
        assert get_current_module() is None

    def test_nested_context_restored_after_clear(self, compiled_graph) -> None:
        """Nested contexts restore properly when cleared in reverse order."""
        # Outer context
        outer_tokens = set_module_context(CoreModule, compiled_graph)
        # Inner context
        inner_tokens = set_module_context(CacheModule, compiled_graph)
        assert get_current_module() is CacheModule
        # Restore inner → outer
        clear_module_context(inner_tokens)
        assert get_current_module() is CoreModule
        # Restore outer → None
        clear_module_context(outer_tokens)
        assert get_current_module() is None
