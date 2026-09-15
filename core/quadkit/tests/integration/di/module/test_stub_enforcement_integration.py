"""Integration tests for stub enforcement (compiler warnings + assert_stub_modules).

Tests the interaction between:
- ModuleCompiler._check_stub_requirements() adding warnings to graph.warnings
- assert_stub_modules() from quadkit-testing raising ConfigurationError

Uses a realistic 2-module scenario with and without stub() overrides.
"""

from __future__ import annotations

import pytest

from quadkit.di.provider import Provider
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.module import Module
from quadkit.di.module.compiler import ModuleCompiler
from quadkit.di.module.decorator import module
from quadkit.di.module.dynamic import DynamicModule
from quadkit.testing.lib.stubs import ConfigurationError, assert_stub_modules

# ---------------------------------------------------------------------------
# Minimal service markers and providers
# ---------------------------------------------------------------------------


class DatabaseService:
    """Marker type for database service."""


class _DbProvider(Provider):
    """Real database provider."""

    name = "db"
    priority = ProviderPriority.INFRASTRUCTURE

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(DatabaseService, DatabaseService)


class _FakeDbProvider(Provider):
    """Fake database provider for tests."""

    name = "fake_db"
    priority = ProviderPriority.INFRASTRUCTURE

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(DatabaseService, DatabaseService)


# ---------------------------------------------------------------------------
# Test module classes (module-level to avoid closure issues)
# ---------------------------------------------------------------------------


@module(require_stub=True)
class DatabaseModule(Module):
    """Module with require_stub=True but NO stub() override."""

    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(module=cls, providers=[_DbProvider])


@module(require_stub=True)
class DatabaseModuleWithStub(Module):
    """Module with require_stub=True AND a stub() override."""

    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(module=cls, providers=[_DbProvider])

    @classmethod
    def stub(cls) -> DynamicModule:
        return DynamicModule(module=cls, providers=[_FakeDbProvider])


@module()
class NormalModule(Module):
    """Module without require_stub flag (normal module)."""

    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(module=cls, providers=[_DbProvider])


# ---------------------------------------------------------------------------
# Test class 1: Compiler warnings
# ---------------------------------------------------------------------------


class TestStubCompilerWarnings:
    """Test ModuleCompiler._check_stub_requirements() warnings."""

    def test_compiler_warns_for_missing_stub(self) -> None:
        """Compiler adds warning when require_stub=True module has no stub() override."""
        compiler = ModuleCompiler()
        graph = compiler.compile([DatabaseModule])

        # Should have at least one warning
        assert len(graph.warnings) > 0

        # Warning should mention the module name
        warning_text = "\n".join(graph.warnings)
        assert "DatabaseModule" in warning_text
        assert "require_stub" in warning_text or "stub" in warning_text.lower()

    def test_compiler_no_warning_when_stub_overridden(self) -> None:
        """No warning when require_stub=True module has stub() override."""
        compiler = ModuleCompiler()
        graph = compiler.compile([DatabaseModuleWithStub])

        # Filter for stub-related warnings (there might be other warnings)
        stub_warnings = [
            w
            for w in graph.warnings
            if "require_stub" in w or "stub()" in w or "DatabaseModuleWithStub" in w
        ]
        assert len(stub_warnings) == 0

    def test_warnings_are_strings(self) -> None:
        """All warnings in graph.warnings are strings."""
        compiler = ModuleCompiler()
        graph = compiler.compile([DatabaseModule, DatabaseModuleWithStub])

        for warning in graph.warnings:
            assert isinstance(warning, str)


# ---------------------------------------------------------------------------
# Test class 2: assert_stub_modules
# ---------------------------------------------------------------------------


class TestAssertStubModules:
    """Test assert_stub_modules() helper function."""

    def test_raises_in_testing_mode_for_missing_stub(self) -> None:
        """assert_stub_modules raises ConfigurationError in testing mode."""
        compiler = ModuleCompiler()
        graph = compiler.compile([DatabaseModule])

        with pytest.raises(ConfigurationError) as exc_info:
            assert_stub_modules(graph, testing_mode=True)

        # Error message should reference the module
        assert "DatabaseModule" in str(exc_info.value)
        assert "require_stub" in str(exc_info.value)

    def test_no_raise_in_production_mode(self) -> None:
        """assert_stub_modules does not raise in production mode (testing_mode=False)."""
        compiler = ModuleCompiler()
        graph = compiler.compile([DatabaseModule])

        # Should not raise even though stub is missing
        assert_stub_modules(graph, testing_mode=False)

    def test_no_raise_when_stub_overridden(self) -> None:
        """assert_stub_modules does not raise when stub() is overridden."""
        compiler = ModuleCompiler()
        graph = compiler.compile([DatabaseModuleWithStub])

        # Should not raise in testing mode because stub() is overridden
        assert_stub_modules(graph, testing_mode=True)

    def test_no_raise_for_normal_modules(self) -> None:
        """assert_stub_modules does not raise for modules without require_stub flag."""
        compiler = ModuleCompiler()
        graph = compiler.compile([NormalModule])

        # Should not raise — normal module doesn't need stub
        assert_stub_modules(graph, testing_mode=True)


# ---------------------------------------------------------------------------
# Test class 3: End-to-end integration
# ---------------------------------------------------------------------------


class TestStubEnforcementEndToEnd:
    """Test compiler warnings and assert_stub_modules together."""

    def test_compiler_warns_and_assert_stub_raises(self) -> None:
        """Module without stub() produces warning AND raises in assert_stub_modules."""
        compiler = ModuleCompiler()
        graph = compiler.compile([DatabaseModule])

        # 1. Compiler should have warned
        assert len(graph.warnings) > 0
        warning_text = "\n".join(graph.warnings)
        assert "DatabaseModule" in warning_text

        # 2. assert_stub_modules should raise
        with pytest.raises(ConfigurationError):
            assert_stub_modules(graph, testing_mode=True)

    def test_stub_module_passes_all_checks(self) -> None:
        """Module with stub() has no warnings AND passes assert_stub_modules."""
        compiler = ModuleCompiler()
        graph = compiler.compile([DatabaseModuleWithStub])

        # 1. No stub-related warnings
        stub_warnings = [
            w
            for w in graph.warnings
            if "require_stub" in w or "stub()" in w or "DatabaseModuleWithStub" in w
        ]
        assert len(stub_warnings) == 0

        # 2. assert_stub_modules should not raise
        assert_stub_modules(graph, testing_mode=True)

    def test_mixed_modules_partial_stub_coverage(self) -> None:
        """Graph with both stubbed and non-stubbed modules."""
        compiler = ModuleCompiler()
        graph = compiler.compile([DatabaseModule, DatabaseModuleWithStub, NormalModule])

        # Compiler warns about DatabaseModule only
        assert len(graph.warnings) > 0
        warning_text = "\n".join(graph.warnings)
        assert "DatabaseModule" in warning_text

        # assert_stub_modules raises because DatabaseModule is not stubbed
        with pytest.raises(ConfigurationError) as exc_info:
            assert_stub_modules(graph, testing_mode=True)

        # Error should reference only DatabaseModule, not DatabaseModuleWithStub
        assert "DatabaseModule" in str(exc_info.value)
