"""Tests for the ToolNode workflow node."""

from __future__ import annotations

from typing import Any

from quadkit.workflow.nodes.tool_node import ToolNode


class _Result:
    def __init__(self, result: str) -> None:
        self.result = result


class _Tool:
    def __init__(self, output: Any = None, error: Exception | None = None):
        self.output = output
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def execute(self, args: dict[str, Any]) -> Any:
        self.calls.append(args)
        if self.error is not None:
            raise self.error
        return self.output


class TestToolNode:
    async def test_basic_execution(self) -> None:
        tool = _Tool(output="hello")
        node = ToolNode("n", tool=tool)
        result = await node.execute({"input": "x"})
        assert result == {"output": "hello"}
        assert tool.calls == [{"input": "x"}]

    async def test_result_object_unwrapped(self) -> None:
        tool = _Tool(output=_Result("payload"))
        node = ToolNode("n", tool=tool)
        assert (await node.execute({"input": "x"}))["output"] == "payload"

    async def test_none_result_becomes_empty(self) -> None:
        tool = _Tool(output=None)
        node = ToolNode("n", tool=tool)
        assert (await node.execute({"input": "x"}))["output"] == ""

    async def test_custom_keys(self) -> None:
        tool = _Tool(output="ok")
        node = ToolNode("n", tool=tool, input_key="data", output_key="result")
        result = await node.execute({"data": 7})
        assert result == {"result": "ok"}
        assert tool.calls == [{"input": 7}]

    async def test_extra_keys_forwarded(self) -> None:
        tool = _Tool(output="ok")
        node = ToolNode("n", tool=tool, extra_keys=["user", "tenant"])
        result = await node.execute({"input": "q", "user": "u1", "tenant": "t1", "unused": 1})
        assert result == {"output": "ok"}
        assert tool.calls == [{"input": "q", "user": "u1", "tenant": "t1"}]

    async def test_missing_extra_key_skipped(self) -> None:
        tool = _Tool(output="ok")
        node = ToolNode("n", tool=tool, extra_keys=["user"])
        await node.execute({"input": "q"})
        assert tool.calls == [{"input": "q"}]

    async def test_missing_input_key_defaults_empty(self) -> None:
        tool = _Tool(output="ok")
        node = ToolNode("n", tool=tool)
        await node.execute({})
        assert tool.calls == [{"input": ""}]

    async def test_error_degrades_to_message(self) -> None:
        tool = _Tool(error=ValueError("broken"))
        node = ToolNode("n", tool=tool)
        result = await node.execute({"input": "x"})
        assert result["output"] == "Tool execution failed."
        assert "broken" not in result["output"]

    async def test_no_execute_method(self) -> None:
        node = ToolNode("n", tool=object())
        result = await node.execute({"input": "x"})
        assert result["output"] == "Tool execution is not configured."

    async def test_node_type_is_tool(self) -> None:
        from quadkit.workflow.graph.node import NodeType

        node = ToolNode("n", tool=_Tool())
        assert node.node_type is NodeType.TOOL
        assert node.name == "n"
