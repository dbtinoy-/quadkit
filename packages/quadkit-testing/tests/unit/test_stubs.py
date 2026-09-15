"""Tests for assert_stub_modules() helper in quadkit.testing.stubs.

Verifies that the assert_stub_modules() function correctly identifies modules
with require_stub=True that are loaded via configure() instead of stub().
"""

from __future__ import annotations

import pytest

from quadkit.di.module.base import Module
from quadkit.di.module.compiler import ModuleCompiler
from quadkit.di.module.decorator import module
from quadkit.di.module.dynamic import DynamicModule
from quadkit.testing.lib.stubs import ConfigurationError, assert_stub_modules


class TestAssertStubModules:
    """Test suite for assert_stub_modules() helper."""

    def _make_graph_with_require_stub(self) -> object:
        """Graph with a require_stub module that has NOT overridden stub()."""

        @module(require_stub=True)
        class MyModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[], exports=[])

        return ModuleCompiler().compile([MyModule])

    def _make_graph_stubbed(self) -> object:
        """Graph with a require_stub module that HAS overridden stub()."""

        @module(require_stub=True)
        class MyModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[], exports=[])

            @classmethod
            def stub(cls, config: object = None) -> DynamicModule:
                return DynamicModule(module=cls, providers=[], exports=[])

        return ModuleCompiler().compile([MyModule])

    def _make_graph_no_require_stub(self) -> object:
        """Graph with a module that does NOT have require_stub=True."""

        @module()
        class MyModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[], exports=[])

        return ModuleCompiler().compile([MyModule])

    def test_no_error_when_not_testing_mode(self) -> None:
        """Should not raise when testing_mode=False, regardless of stub override."""
        graph = self._make_graph_with_require_stub()
        assert_stub_modules(graph, testing_mode=False)

    def test_raises_in_testing_mode_without_stub(self) -> None:
        """Should raise ConfigurationError when testing_mode=True and stub not overridden."""
        graph = self._make_graph_with_require_stub()
        with pytest.raises(ConfigurationError, match="stub"):
            assert_stub_modules(graph, testing_mode=True)

    def test_no_error_when_stub_overridden(self) -> None:
        """Should not raise when stub() method is overridden."""
        graph = self._make_graph_stubbed()
        assert_stub_modules(graph, testing_mode=True)

    def test_no_error_when_require_stub_false(self) -> None:
        """Should not raise when require_stub=False."""
        graph = self._make_graph_no_require_stub()
        assert_stub_modules(graph, testing_mode=True)
