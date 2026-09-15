# file: tests/di/module/test_reexport.py
"""Tests for re-export expansion."""

from __future__ import annotations

import pytest

from quadkit.di.module import ModuleCompiler, module
from .conftest import (
    ProtoA,
    ProtoB,
    ProtoC,
    StubProviderA,
    StubProviderB,
    StubProviderC,
)


class TestReExportExpansion:
    """Test that module classes in exports are expanded."""

    def test_reexport_expands_types(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(
            imports=[ModA],
            providers=[StubProviderB],
            exports=[ModA, ProtoB],  # Re-export ModA
        )
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModB])

        node_b = graph.nodes[ModB]
        # ModB's exports should include ProtoA (from ModA) and ProtoB
        assert ProtoA in node_b.exports
        assert ProtoB in node_b.exports

    def test_reexport_makes_types_visible_to_importers(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(
            imports=[ModA],
            providers=[StubProviderB],
            exports=[ModA, ProtoB],  # Re-export
        )
        class ModB:
            pass

        @module(imports=[ModB], providers=[StubProviderC])
        class ModC:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModC])

        # ModC imports ModB which re-exports ModA
        # So ProtoA should be visible to ModC
        assert graph.is_visible(ModC, ProtoA)
        assert graph.is_visible(ModC, ProtoB)

    def test_reexport_chain(self):
        """A exports ProtoA, B re-exports A, C re-exports B."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(imports=[ModA], providers=[StubProviderB], exports=[ModA, ProtoB])
        class ModB:
            pass

        @module(imports=[ModB], providers=[StubProviderC], exports=[ModB, ProtoC])
        class ModC:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModC])

        # ModC re-exports ModB, which re-exports ModA
        node_c = graph.nodes[ModC]
        assert ProtoA in node_c.exports
        assert ProtoB in node_c.exports
        assert ProtoC in node_c.exports
