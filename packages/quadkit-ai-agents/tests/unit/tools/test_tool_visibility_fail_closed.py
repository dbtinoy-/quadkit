"""Fail-closed regression tests for tool visibility (audit Round 9, SS48).

Covers: graph-less registries with a caller module, broken/malformed module
graphs, caller-less standalone mode, and the preserved happy paths.
"""

from __future__ import annotations

import pytest

from quadkit.ai.agents.exceptions import ToolAccessDeniedError
from quadkit.ai.agents.tools import ToolRegistryImpl, tool


class _FakeModuleNode:
    def __init__(self, imports: list[type] | None = None, is_global: bool = False) -> None:
        self.imports = imports or []
        self.is_global = is_global


class _FakeModuleGraph:
    def __init__(self, mapping: dict[type, _FakeModuleNode]) -> None:
        self._mapping = mapping

    def get_module(self, module_class: type) -> _FakeModuleNode | None:
        return self._mapping.get(module_class)


class _MalformedModuleGraph:
    def get_module(self, module_class: type) -> _MalformedModuleNode:
        return _MalformedModuleNode(module_class)


class _MalformedModuleNode:
    def __init__(self, module_class: type) -> None:
        self._module_class = module_class

    @property
    def is_global(self) -> bool:
        raise RuntimeError("malformed graph node")

    @property
    def imports(self) -> list[type]:
        raise RuntimeError("malformed graph node")


class TestToolVisibilityFailClosed:
    @pytest.mark.asyncio
    async def test_graph_less_registry_exposes_only_same_module_tools(self) -> None:
        class CallerModule:
            pass

        class OtherModule:
            pass

        @tool
        async def local_tool() -> str:
            return "local"

        @tool
        async def foreign_tool() -> str:
            return "foreign"

        registry = ToolRegistryImpl()
        registry.register(local_tool, module_class=CallerModule)
        registry.register(foreign_tool, module_class=OtherModule)
        registry.set_caller_module(CallerModule)

        assert [t.name for t in registry.list_visible_tools()] == ["local_tool"]
        assert registry.list_visible_tool_names() == ["local_tool"]
        schemas = registry.list_tool_schemas()
        assert [s["function"]["name"] for s in schemas] == ["local_tool"]

    @pytest.mark.asyncio
    async def test_graph_less_registry_denies_cross_module_execute(self) -> None:
        class CallerModule:
            pass

        class OtherModule:
            pass

        @tool
        async def foreign_tool() -> str:
            return "foreign"

        registry = ToolRegistryImpl()
        registry.register(foreign_tool, module_class=OtherModule)
        registry.set_caller_module(CallerModule)

        result = await registry.execute("foreign_tool")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ToolAccessDeniedError)
        assert error.details == {}
        assert "CallerModule" not in repr(error.to_dict())
        assert "OtherModule" not in repr(error.to_dict())
        assert "foreign_tool" not in repr(error.to_dict())

    @pytest.mark.asyncio
    async def test_graph_less_registry_allows_same_module_execute(self) -> None:
        class CallerModule:
            pass

        @tool
        async def local_tool() -> str:
            return "local"

        registry = ToolRegistryImpl()
        registry.register(local_tool, module_class=CallerModule)
        registry.set_caller_module(CallerModule)

        result = await registry.execute("local_tool")

        assert result.is_ok()
        assert result.unwrap() == "local"

    @pytest.mark.asyncio
    async def test_graph_less_registry_allows_unowned_tool_execute(self) -> None:
        class CallerModule:
            pass

        @tool
        async def unowned_tool() -> str:
            return "unowned"

        registry = ToolRegistryImpl()
        registry.register(unowned_tool)
        registry.set_caller_module(CallerModule)

        result = await registry.execute("unowned_tool")

        assert result.is_ok()
        assert result.unwrap() == "unowned"

    @pytest.mark.asyncio
    async def test_broken_graph_denies_execute(self) -> None:
        class CallerModule:
            pass

        class ToolModule:
            pass

        class _BrokenModuleGraph:
            def get_module(self, module_class: type) -> None:
                raise RuntimeError("graph lookup failed")

        @tool
        async def unstable_graph_tool() -> str:
            return "ok"

        registry = ToolRegistryImpl()
        registry.register(unstable_graph_tool, module_class=ToolModule)
        registry.set_caller_module(CallerModule)
        registry.set_module_graph(_BrokenModuleGraph())

        result = await registry.execute("unstable_graph_tool")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), ToolAccessDeniedError)

    @pytest.mark.asyncio
    async def test_malformed_graph_node_hides_tool(self) -> None:
        class CallerModule:
            pass

        class ToolModule:
            pass

        @tool
        async def broken_node_tool() -> str:
            return "ok"

        registry = ToolRegistryImpl()
        registry.register(broken_node_tool, module_class=ToolModule)
        registry.set_caller_module(CallerModule)
        registry.set_module_graph(_MalformedModuleGraph())  # type: ignore[arg-type]

        assert registry.list_visible_tool_names() == []
        result = await registry.execute("broken_node_tool")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ToolAccessDeniedError)

    def test_caller_less_registry_without_graph_lists_all_tools(self) -> None:
        @tool
        async def any_tool() -> str:
            return "any"

        registry = ToolRegistryImpl()
        registry.register(any_tool)

        assert [t.name for t in registry.list_visible_tools()] == ["any_tool"]

    @pytest.mark.asyncio
    async def test_caller_less_registry_with_graph_lists_all_tools(self) -> None:
        class ToolModule:
            pass

        @tool
        async def any_tool() -> str:
            return "any"

        registry = ToolRegistryImpl()
        registry.register(any_tool, module_class=ToolModule)
        registry.set_module_graph(_FakeModuleGraph({}))

        assert [t.name for t in registry.list_visible_tools()] == ["any_tool"]
        assert (await registry.execute("any_tool")).is_ok()

    @pytest.mark.asyncio
    async def test_happy_paths_stay_visible(self) -> None:
        class CallerModule:
            pass

        class SameModuleToolModule:
            pass

        class GlobalToolModule:
            pass

        class ImportedToolModule:
            pass

        @tool
        async def same_module_tool() -> str:
            return "same"

        @tool
        async def global_tool() -> str:
            return "global"

        @tool
        async def imported_tool() -> str:
            return "imported"

        @tool
        async def hidden_tool() -> str:
            return "hidden"

        registry = ToolRegistryImpl()
        registry.register(same_module_tool, module_class=CallerModule)
        registry.register(global_tool, module_class=GlobalToolModule)
        registry.register(imported_tool, module_class=ImportedToolModule)
        registry.register(hidden_tool, module_class=SameModuleToolModule)
        registry.set_caller_module(CallerModule)
        registry.set_module_graph(
            _FakeModuleGraph(
                {
                    CallerModule: _FakeModuleNode(imports=[ImportedToolModule]),
                    GlobalToolModule: _FakeModuleNode(is_global=True),
                    ImportedToolModule: _FakeModuleNode(is_global=False),
                    SameModuleToolModule: _FakeModuleNode(is_global=False),
                }
            )
        )

        assert sorted(registry.list_visible_tool_names()) == [
            "global_tool",
            "imported_tool",
            "same_module_tool",
        ]
        assert (await registry.execute("same_module_tool")).is_ok()
        assert (await registry.execute("global_tool")).is_ok()
        assert (await registry.execute("imported_tool")).is_ok()
