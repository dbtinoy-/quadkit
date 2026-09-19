# file: tests/di/module/test_global.py
"""Tests for global module visibility."""

from __future__ import annotations

import pytest

from quadkit.di.module import DynamicModule, ModuleCompiler, global_module, module
from .conftest import (
    ProtoA,
    ProtoB,
    ProtoC,
    StubProviderA,
    StubProviderB,
    StubProviderC,
)


class TestGlobalModuleVisibility:
    """Test that global module exports are visible to all modules."""

    def test_global_exports_in_visibility(self):
        @global_module
        class GlobalModule:
            providers = [StubProviderA]
            exports = [ProtoA]

        @module(providers=[StubProviderB], exports=[ProtoB])
        class OtherModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[GlobalModule, OtherModule])

        # ProtoA should be visible to OtherModule even without import
        assert graph.is_visible(OtherModule, ProtoA)

    def test_global_exports_computed(self):
        @global_module
        class GlobalModule:
            providers = [StubProviderA]
            exports = [ProtoA]

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[GlobalModule])

        assert ProtoA in graph.global_exports

    def test_non_global_not_in_global_exports(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class RegularModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[RegularModule])

        assert ProtoA not in graph.global_exports

    def test_dynamic_global_module(self):
        @module()
        class InfraModule:
            pass

        dm = DynamicModule(
            module=InfraModule,
            providers=[StubProviderA],
            exports=[ProtoA],
            is_global=True,
        )

        @module(providers=[StubProviderB])
        class AppModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[dm, AppModule])

        assert ProtoA in graph.global_exports
        assert graph.is_visible(AppModule, ProtoA)

    def test_multiple_global_modules(self):
        @global_module
        class ConfigModule:
            providers = [StubProviderA]
            exports = [ProtoA]

        @global_module
        class LoggingModule:
            providers = [StubProviderB]
            exports = [ProtoB]

        @module(providers=[StubProviderC])
        class AppModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(
            root_modules=[ConfigModule, LoggingModule, AppModule],
        )

        assert graph.is_visible(AppModule, ProtoA)
        assert graph.is_visible(AppModule, ProtoB)
        assert len(graph.global_exports) == 2
