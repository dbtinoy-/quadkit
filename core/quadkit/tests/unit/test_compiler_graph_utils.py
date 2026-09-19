"""Tests for the module compiler's topological-sort utilities."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.exceptions.provider import ModuleCycleError
from quadkit.di.module.compiler._graph_utils import (
    compute_module_boot_levels,
    topological_sort_modules,
)
from quadkit.di.module.graph import ModuleNode
from quadkit.di.module.metadata import ModuleMetadata


def _node(cls: type, name: str, imports: list[type] | None = None) -> ModuleNode:
    return ModuleNode(
        module_class=cls,
        name=name,
        metadata=ModuleMetadata(name=name),
        providers=[],
        imports=imports or [],
        exports=frozenset(),
        is_global=False,
        is_dynamic=False,
        controllers=[],
        health_providers=None,  # type: ignore[arg-type]
    )


def _cls(prefix: str, n: int) -> type:
    return type(f"{prefix}{n}", (), {})


class TestTopologicalSort:
    def test_linear_chain(self) -> None:
        a, b, c = _cls("M", 1), _cls("M", 2), _cls("M", 3)
        nodes = {
            a: _node(a, "a"),
            b: _node(b, "b", imports=[a]),
            c: _node(c, "c", imports=[b]),
        }
        assert topological_sort_modules(nodes) == [a, b, c]

    def test_diamond(self) -> None:
        a, b, c, d = (_cls("M", i) for i in range(1, 5))
        nodes = {
            a: _node(a, "a"),
            b: _node(b, "b", imports=[a]),
            c: _node(c, "c", imports=[a]),
            d: _node(d, "d", imports=[b, c]),
        }
        result = topological_sort_modules(nodes)
        assert result[0] is a
        assert result[-1] is d
        assert set(result) == {a, b, c, d}

    def test_deterministic_name_order_for_independent_modules(self) -> None:
        z, m, a = _cls("Z", 1), _cls("M", 2), _cls("A", 3)
        nodes = {
            z: _node(z, "z-mod"),
            m: _node(m, "m-mod"),
            a: _node(a, "a-mod"),
        }
        result = topological_sort_modules(nodes)
        # No imports → sorted by module name.
        assert result == [a, m, z]

    def test_external_imports_ignored(self) -> None:
        # Imports pointing outside the node map are not part of the graph.
        a = _cls("A", 1)
        external = _cls("Ext", 9)
        nodes = {a: _node(a, "a", imports=[external])}
        assert topological_sort_modules(nodes) == [a]

    def test_cycle_raises_module_cycle_error(self) -> None:
        a, b = _cls("A", 1), _cls("B", 2)
        # Cross references are passed as classes; node.imports must be set
        # after both classes exist (frozen dataclass → build with correct
        # imports directly).
        nodes: dict[type, ModuleNode] = {
            a: _node(a, "alpha", imports=[b]),
            b: _node(b, "beta", imports=[a]),
        }
        with pytest.raises(ModuleCycleError, match="Unplaced modules"):
            topological_sort_modules(nodes)


class TestBootLevels:
    def test_levels_follow_dependency_depth(self) -> None:
        a, b, c = _cls("M", 1), _cls("M", 2), _cls("M", 3)
        nodes = {
            a: _node(a, "a"),
            b: _node(b, "b", imports=[a]),
            c: _node(c, "c", imports=[b]),
        }
        order = topological_sort_modules(nodes)
        levels = compute_module_boot_levels(nodes, order)
        assert levels == {a: 0, b: 1, c: 2}

    def test_independent_modules_share_level_zero(self) -> None:
        x, y = _cls("X", 1), _cls("Y", 2)
        nodes = {
            x: _node(x, "x"),
            y: _node(y, "y"),
        }
        order = topological_sort_modules(nodes)
        levels = compute_module_boot_levels(nodes, order)
        assert levels[x] == 0
        assert levels[y] == 0

    def test_diamond_levels(self) -> None:
        a, b, c, d = (_cls("M", i) for i in range(1, 5))
        nodes = {
            a: _node(a, "a"),
            b: _node(b, "b", imports=[a]),
            c: _node(c, "c", imports=[a]),
            d: _node(d, "d", imports=[b, c]),
        }
        order = topological_sort_modules(nodes)
        levels = compute_module_boot_levels(nodes, order)
        assert levels == {a: 0, b: 1, c: 1, d: 2}

    def test_unknown_import_defaults_to_zero_base(self) -> None:
        a = _cls("A", 1)
        external = _cls("E", 9)
        nodes: dict[type, Any] = {a: _node(a, "a", imports=[external])}
        levels = compute_module_boot_levels(nodes, [a])
        # External import not in levels → max() default 0 → level 1.
        assert levels[a] == 1
