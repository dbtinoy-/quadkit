from __future__ import annotations

import pytest

from quadkit.ai.agents.exceptions import (
    ToolAccessDeniedError,
    ToolExecutionError,
    ToolNotFoundError,
)
from quadkit.ai.agents.tools import ToolRegistryImpl, tool


class _FakeModuleNode:
    def __init__(
        self, imports: list[type] | None = None, is_global: bool = False
    ) -> None:
        self.imports = imports or []
        self.is_global = is_global


class _FakeModuleGraph:
    def __init__(self, mapping: dict[type, _FakeModuleNode]) -> None:
        self._mapping = mapping

    def get_module(self, module_class: type) -> _FakeModuleNode | None:
        return self._mapping.get(module_class)


class _BrokenModuleGraph:
    def get_module(self, module_class: type) -> None:
        raise RuntimeError("graph lookup failed")


class TestToolRegistryVisibilityAndErrors:
    @pytest.mark.asyncio
    async def test_execute_returns_tool_not_found_error(self) -> None:
        registry = ToolRegistryImpl()

        result = await registry.execute("missing_tool")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ToolNotFoundError)
        assert error.message == "Tool not found"
        assert error.details == {}
        assert "missing_tool" not in str(error)
        assert "missing_tool" not in repr(error.to_dict())

    @pytest.mark.asyncio
    async def test_execute_returns_access_denied_when_tool_not_visible(self) -> None:
        class CallerModule:
            pass

        class ToolModule:
            pass

        @tool
        async def hidden_tool() -> str:
            return "hidden"

        registry = ToolRegistryImpl()
        registry.register(hidden_tool, module_class=ToolModule)
        registry.set_caller_module(CallerModule)
        registry.set_module_graph(
            _FakeModuleGraph(
                {
                    CallerModule: _FakeModuleNode(imports=[]),
                    ToolModule: _FakeModuleNode(is_global=False),
                }
            )
        )

        result = await registry.execute("hidden_tool")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ToolAccessDeniedError)
        assert error.message == "Tool access denied"
        assert error.details == {}
        assert all(
            identifier not in repr(error.to_dict())
            for identifier in ("hidden_tool", "CallerModule", "ToolModule")
        )

    @pytest.mark.asyncio
    async def test_execute_wraps_tool_exception_without_leaking_args_or_text(
        self,
    ) -> None:
        exception_secret = "TOOL_EXCEPTION_SECRET_SENTINEL"
        argument_secret = "TOOL_ARGUMENT_SECRET_SENTINEL"

        @tool
        async def failing_tool(attempt: str) -> str:
            raise ValueError(exception_secret)

        registry = ToolRegistryImpl()
        registry.register(failing_tool)

        result = await registry.execute("failing_tool", attempt=argument_secret)

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ToolExecutionError)
        assert error.cause is None
        assert error.details == {"error_type": "ValueError"}
        assert "arguments" not in error.details
        assert exception_secret not in str(error)
        assert argument_secret not in str(error)
        assert exception_secret not in repr(error.to_dict())
        assert argument_secret not in repr(error.to_dict())

    @pytest.mark.asyncio
    async def test_visibility_check_denies_access_when_graph_lookup_raises(
        self,
    ) -> None:
        class CallerModule:
            pass

        class ToolModule:
            pass

        @tool
        async def unstable_graph_tool() -> str:
            return "ok"

        registry = ToolRegistryImpl()
        registry.register(unstable_graph_tool, module_class=ToolModule)
        registry.set_caller_module(CallerModule)
        registry.set_module_graph(_BrokenModuleGraph())

        result = await registry.execute("unstable_graph_tool")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ToolAccessDeniedError)
        assert error.message == "Tool access denied"
        assert error.details == {}
        assert all(
            identifier not in repr(error.to_dict())
            for identifier in ("unstable_graph_tool", "CallerModule", "ToolModule")
        )

    @pytest.mark.asyncio
    async def test_logs_and_errors_omit_private_tool_module_and_argument_data(
        self, monkeypatch
    ) -> None:
        from unittest.mock import MagicMock

        import quadkit.ai.agents.tools.registry as registry_module

        private_tool_name = "private_tool_tenant_42"
        private_missing_name = "private_missing_tool_tenant_42"
        private_module_name = "private_module_tenant_42"
        private_caller_name = "private_caller_tenant_42"
        private_argument = "customer=tenant-42"
        private_error = "token=secret at /srv/private/tenant-42"

        private_module = type(private_module_name, (), {})
        private_caller = type(private_caller_name, (), {})

        @tool(name=private_tool_name)
        async def private_tool(token: str) -> str:
            raise ValueError(private_error)

        logger = MagicMock()
        monkeypatch.setattr(registry_module, "logger", logger)
        registry = ToolRegistryImpl()
        registry.register(private_tool, module_class=private_module)
        registry.set_caller_module(private_caller)
        registry.set_module_graph(
            _FakeModuleGraph(
                {
                    private_caller: _FakeModuleNode(imports=[]),
                    private_module: _FakeModuleNode(is_global=False),
                }
            )
        )

        denied = await registry.execute(private_tool_name, token=private_argument)
        missing = await registry.execute(private_missing_name)
        assert denied.is_err()
        assert missing.is_err()
        assert denied.unwrap_err().details == {}
        assert missing.unwrap_err().details == {}

        registry.set_caller_module(None)
        failed = await registry.execute(private_tool_name, token=private_argument)
        assert failed.is_err()
        assert failed.unwrap_err().details == {"error_type": "ValueError"}

        captured = repr(logger.mock_calls)
        assert "tool_registered" in captured
        assert "tool_access_denied" in captured
        assert "tool_execution_failed" in captured
        for private_value in (
            private_tool_name,
            private_missing_name,
            private_module_name,
            private_caller_name,
            private_argument,
            private_error,
            "/srv/private/tenant-42",
        ):
            assert private_value not in captured
        assert "ValueError" in captured
        for result in (denied, missing, failed):
            serialized_error = repr(result.unwrap_err().to_dict())
            for private_value in (
                private_tool_name,
                private_missing_name,
                private_module_name,
                private_caller_name,
                private_argument,
                private_error,
                "/srv/private/tenant-42",
            ):
                assert private_value not in serialized_error

    def test_repr_shows_visible_count_and_clear_resets_registry(self) -> None:
        class CallerModule:
            pass

        class ImportedToolModule:
            pass

        class HiddenToolModule:
            pass

        @tool
        async def visible_tool() -> str:
            return "visible"

        @tool
        async def hidden_tool() -> str:
            return "hidden"

        registry = ToolRegistryImpl()
        registry.register(visible_tool, module_class=ImportedToolModule)
        registry.register(hidden_tool, module_class=HiddenToolModule)
        registry.set_caller_module(CallerModule)
        registry.set_module_graph(
            _FakeModuleGraph(
                {
                    CallerModule: _FakeModuleNode(imports=[ImportedToolModule]),
                    ImportedToolModule: _FakeModuleNode(is_global=False),
                    HiddenToolModule: _FakeModuleNode(is_global=False),
                }
            )
        )

        assert repr(registry) == "ToolRegistry(tools=2, visible=1)"

        registry.clear()

        assert len(registry.list_tools()) == 0
        assert repr(registry) == "ToolRegistry(tools=0)"
