# file: tests/di/module/test_registry.py
"""Tests for ModuleRegistry — ownership tracking and export validation."""

from __future__ import annotations

import pytest

from quadkit.di.module import ModuleCompiler, ModuleRegistry, module
from .conftest import ProtoA, ProtoB, ProtoC, StubProviderA, StubProviderB


class TestOwnershipTracking:
    """Test service type → module ownership mapping."""

    def test_register_ownership(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        registry = ModuleRegistry()
        registry.register_ownership(ProtoA, MyModule, "stub_a")

        assert registry.get_owner(ProtoA) is MyModule

    def test_standalone_ownership(self):
        registry = ModuleRegistry()
        registry.register_ownership(ProtoA, None, "standalone_provider")

        assert registry.get_owner(ProtoA) is None

    def test_get_module_services(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        registry = ModuleRegistry()
        registry.register_ownership(ProtoA, MyModule)
        registry.register_ownership(ProtoB, MyModule)

        services = registry.get_module_services(MyModule)
        assert ProtoA in services
        assert ProtoB in services

    def test_unknown_type_returns_none(self):
        registry = ModuleRegistry()
        assert registry.get_owner(ProtoA) is None

    def test_register_provider(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        registry = ModuleRegistry()
        registry.register_provider("stub_a", MyModule)

        assert registry.get_provider_module("stub_a") is MyModule


class TestExportValidation:
    """Test post-registration export validation."""

    def test_valid_exports_pass(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        registry = ModuleRegistry()
        registry.register_ownership(ProtoA, MyModule, "stub_a")

        issues = registry.validate_exports(graph)
        assert issues == []

    def test_missing_export_detected(self):
        @module(providers=[StubProviderA], exports=[ProtoA, ProtoB])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        registry = ModuleRegistry()
        # Only ProtoA registered, ProtoB missing
        registry.register_ownership(ProtoA, MyModule, "stub_a")

        issues = registry.validate_exports(graph)
        assert len(issues) == 1
        assert "ProtoB" in issues[0]

    def test_all_exports_missing(self):
        @module(providers=[StubProviderA], exports=[ProtoA, ProtoB])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        registry = ModuleRegistry()
        # Nothing registered

        issues = registry.validate_exports(graph)
        assert len(issues) == 2

    def test_no_exports_no_issues(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        registry = ModuleRegistry()
        issues = registry.validate_exports(graph)
        assert issues == []

    def test_container_fallback_check(self):
        """If container.has() returns True, the export is satisfied."""

        @module(providers=[StubProviderA], exports=[ProtoA])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        registry = ModuleRegistry()
        # ProtoA NOT tracked in registry, but container has it

        class FakeContainer:
            def has(self, t):
                return t is ProtoA

        issues = registry.validate_exports(graph, container=FakeContainer())
        assert issues == []

    def test_dump(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        registry = ModuleRegistry()
        registry.register_ownership(ProtoA, MyModule, "stub_a")
        registry.register_provider("stub_a", MyModule)

        dump = registry.dump()
        assert "modules" in dump
        assert "MyModule" in dump["modules"]
        assert "ProtoA" in dump["modules"]["MyModule"]
