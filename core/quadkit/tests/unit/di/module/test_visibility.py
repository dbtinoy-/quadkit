# file: tests/di/module/test_visibility.py
"""Tests for cross-module visibility rules."""

from __future__ import annotations

import pytest

from quadkit.di.module import ModuleCompiler, module, global_module
from .conftest import (
    ProtoA,
    ProtoB,
    ProtoC,
    ProtoInternal,
    StubProviderA,
    StubProviderB,
    StubProviderC,
)


class TestVisibilityRules:
    """Test the 6 visibility rules from the plan."""

    def test_own_exports_visible(self):
        """Rule 1: A provider can see services from its own module."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA])

        assert graph.is_visible(ModA, ProtoA)

    def test_imported_exports_visible(self):
        """Rule 2: A provider can see exports from an imported module."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(imports=[ModA], providers=[StubProviderB])
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModB])

        assert graph.is_visible(ModB, ProtoA)

    def test_global_exports_visible_without_import(self):
        """Rule 3: A provider can see exports from a global module."""
        @global_module
        class GlobalMod:
            providers = [StubProviderA]
            exports = [ProtoA]

        @module(providers=[StubProviderB])
        class OtherMod:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[GlobalMod, OtherMod])

        assert graph.is_visible(OtherMod, ProtoA)

    def test_non_exported_not_visible(self):
        """Rule 4: Non-exported services from another module are NOT visible."""
        @module(
            providers=[StubProviderA],
            exports=[ProtoA],  # Only ProtoA exported
        )
        class ModA:
            pass

        @module(imports=[ModA], providers=[StubProviderB])
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModB])

        # ProtoA is visible (exported)
        assert graph.is_visible(ModB, ProtoA)
        # ProtoInternal is NOT visible (not exported by ModA)
        assert not graph.is_visible(ModB, ProtoInternal)

    def test_standalone_no_restriction(self):
        """Rule 5: Standalone providers (no module) have no restrictions."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA])

        # A class not in the graph — treated as standalone
        class NotAModule:
            pass

        assert graph.is_visible(NotAModule, ProtoA)
        assert graph.is_visible(NotAModule, ProtoInternal)

    def test_not_imported_not_visible(self):
        """Module that is NOT imported — its exports are not visible."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(providers=[StubProviderB], exports=[ProtoB])
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA, ModB])

        # ModB does not import ModA
        assert not graph.is_visible(ModB, ProtoA)
        # ModA does not import ModB
        assert not graph.is_visible(ModA, ProtoB)

    def test_transitive_import_not_visible(self):
        """A → B → C.  A should NOT see C's exports (only B's)."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModC:
            pass

        @module(imports=[ModC], providers=[StubProviderB], exports=[ProtoB])
        class ModB:
            pass

        @module(imports=[ModB], providers=[StubProviderC])
        class ModA:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA])

        # A can see B's exports
        assert graph.is_visible(ModA, ProtoB)
        # A canNOT see C's exports (not directly imported, not re-exported)
        assert not graph.is_visible(ModA, ProtoA)
