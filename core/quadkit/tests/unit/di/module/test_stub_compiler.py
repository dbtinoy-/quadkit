"""Tests for ModuleCompiler stub requirement warning mechanism."""

from __future__ import annotations

from quadkit.di.module.base import Module
from quadkit.di.module.compiler import ModuleCompiler
from quadkit.di.module.decorator import module
from quadkit.di.module.dynamic import DynamicModule


class TestStubCompilerWarning:
    """Test ModuleCompiler warnings for require_stub modules."""

    def test_compiler_warns_when_stub_not_implemented(self) -> None:
        """Module with require_stub=True but no stub() override should warn."""

        @module(require_stub=True)
        class MyModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[], exports=[])

        compiler = ModuleCompiler()
        graph = compiler.compile([MyModule])
        assert any("stub" in w.lower() for w in graph.warnings)

    def test_no_warning_when_stub_implemented(self) -> None:
        """Module with require_stub=True and stub() override should not warn."""

        @module(require_stub=True)
        class MyModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[], exports=[])

            @classmethod
            def stub(cls, config: object = None) -> DynamicModule:
                return DynamicModule(module=cls, providers=[], exports=[])

        compiler = ModuleCompiler()
        graph = compiler.compile([MyModule])
        stub_warnings = [w for w in graph.warnings if "stub" in w.lower()]
        assert len(stub_warnings) == 0

    def test_no_warning_when_require_stub_false(self) -> None:
        """Modules without require_stub=True should never warn about stub."""

        @module()
        class MyModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[], exports=[])

        compiler = ModuleCompiler()
        graph = compiler.compile([MyModule])
        stub_warnings = [w for w in graph.warnings if "stub" in w.lower()]
        assert len(stub_warnings) == 0
