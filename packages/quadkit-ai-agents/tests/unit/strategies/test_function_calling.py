"""Unit tests for quadkit-ai-agents FunctionCallingStrategy."""

from __future__ import annotations

import pytest

from quadkit.ai.agents import tool
from quadkit.ai.agents.strategies import FunctionCallingStrategy
from quadkit.contracts.ai.agents import ToolDefinition
from quadkit.contracts.ai.llm import FunctionCall, ToolCall
from quadkit.result import Ok


@tool
async def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"Weather in {city}: sunny"


class ScriptedLLM:
    """LLM that returns a scripted sequence of completions."""

    def __init__(self, *completions: Completion):
        self.completions = list(completions)
        self.calls: list[dict[str, object]] = []

    async def complete(self, messages, tools=None):
        self.calls.append({"messages": list(messages), "tools": tools})
        if not self.completions:
            return Ok(_StubCompletion(content="done"))
        return Ok(self.completions.pop(0))


class _StubCompletion:
    """Completion-shaped object with native tool_calls (provider-style)."""

    def __init__(self, content: str, tool_calls: list[ToolCall] | None = None):
        self.content = content
        self.model = "test"
        self.tool_calls = tool_calls
        self.usage = None


def _completion(
    content: str, tool_calls: list[ToolCall] | None = None
) -> _StubCompletion:
    return _StubCompletion(content=content, tool_calls=tool_calls)


class TestFunctionCallingStrategy:
    """Tests for native tool-call execution."""

    @pytest.mark.asyncio
    async def test_native_tool_call_round_trip(self) -> None:
        """Tool calls from the model are executed and results fed back."""
        llm = ScriptedLLM(
            _completion(
                content="Checking the weather.",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        type="function",
                        function=FunctionCall(
                            name="get_weather",
                            arguments='{"city": "Berlin"}',
                        ),
                    )
                ],
            ),
            _completion(content="It is sunny in Berlin."),
        )
        strategy = FunctionCallingStrategy()

        result = await strategy.execute(
            message="Weather in Berlin?",
            tools=[get_weather],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert response.message == "It is sunny in Berlin."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "get_weather"
        assert response.tool_calls[0].result == "Weather in Berlin: sunny"
        assert response.metadata["strategy"] == "function_calling"

        # Schema sent to the LLM as native ToolDefinitions
        sent_tools = llm.calls[0]["tools"]
        assert isinstance(sent_tools, list)
        assert sent_tools[0].name == "get_weather"
        assert sent_tools[0].parameters["properties"]["city"]["type"] == "string"

        # Round trip: assistant message with native calls + tool message
        round_trip = llm.calls[1]["messages"]
        assistant = [m for m in round_trip if m.role.value == "assistant"]
        tool_msgs = [m for m in round_trip if m.role.value == "tool"]
        assert assistant[0].tool_calls[0].function.name == "get_weather"
        assert tool_msgs[0].tool_call_id == "call_1"
        assert "sunny" in tool_msgs[0].content

    @pytest.mark.asyncio
    async def test_plain_text_answer_without_tools(self) -> None:
        """A completion without tool calls is the final answer."""
        llm = ScriptedLLM(_completion(content="Sure, here you go."))
        strategy = FunctionCallingStrategy()

        result = await strategy.execute(
            message="Hi",
            tools=[],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        assert result.unwrap().message == "Sure, here you go."

    @pytest.mark.asyncio
    async def test_dict_arguments_passed_through(self) -> None:
        """Native calls with dict arguments are executed directly."""
        llm = ScriptedLLM(
            _completion(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_2",
                        type="function",
                        function=FunctionCall(
                            name="get_weather",
                            arguments={"city": "Paris"},
                        ),
                    )
                ],
            ),
            _completion(content="Paris is rainy."),
        )
        strategy = FunctionCallingStrategy()

        result = await strategy.execute(
            message="Paris?",
            tools=[get_weather],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        assert result.unwrap().tool_calls[0].result == "Weather in Paris: sunny"

    @pytest.mark.asyncio
    async def test_unknown_tool_recorded_as_error(self) -> None:
        """Unknown tool names produce error records without crashing."""
        llm = ScriptedLLM(
            _completion(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_3",
                        type="function",
                        function=FunctionCall(
                            name="private_internal_tool_tenant_42",
                            arguments={},
                        ),
                    )
                ],
            ),
            _completion(content="Recovered."),
        )
        strategy = FunctionCallingStrategy()

        result = await strategy.execute(
            message="Try it",
            tools=[get_weather],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        record = result.unwrap().tool_calls[0]
        assert record.error is not None
        assert "Unknown tool" in record.error
        assert "private_internal_tool_tenant_42" not in record.error

    @pytest.mark.asyncio
    async def test_text_marker_fallback(self) -> None:
        """Models ignoring native schemas are handled via text markers."""
        llm = ScriptedLLM(
            _completion(
                content=(
                    "THOUGHT: I need the weather.\n"
                    "ACTION: get_weather\n"
                    'ACTION_INPUT: {"city": "Rome"}'
                )
            ),
            _completion(content="FINAL_ANSWER: Rome is hot."),
        )
        strategy = FunctionCallingStrategy()

        result = await strategy.execute(
            message="Rome?",
            tools=[get_weather],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert response.message == "Rome is hot."
        assert response.tool_calls[0].tool_name == "get_weather"
        assert response.tool_calls[0].result == "Weather in Rome: sunny"

    @pytest.mark.asyncio
    async def test_max_iterations_reached(self) -> None:
        """An LLM that never resolves ends with a max-iterations response."""
        llm = ScriptedLLM(_completion(content=""), _completion(content=""))
        strategy = FunctionCallingStrategy(max_iterations=2)

        result = await strategy.execute(
            message="Loop?",
            tools=[],
            history=[],
            llm=llm,
        )

        assert result.is_ok()
        assert result.unwrap().metadata["max_iterations_reached"] is True

    @pytest.mark.asyncio
    async def test_registry_schemas_merged(self) -> None:
        """ToolRegistry.list_tool_schemas output is sent to the model."""

        class FakeRegistry:
            def list_tool_schemas(self) -> list[dict[str, object]]:
                return [
                    {
                        "type": "function",
                        "function": {
                            "name": "registry_tool",
                            "description": "From the registry",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ]

        llm = ScriptedLLM(_completion(content="ok"))
        strategy = FunctionCallingStrategy()

        result = await strategy.execute(
            message="Go",
            tools=[],
            history=[],
            llm=llm,
            tool_registry=FakeRegistry(),
        )

        assert result.is_ok()
        sent = llm.calls[0]["tools"]
        names = {t.name for t in sent}
        assert names == {"registry_tool"}
        assert isinstance(sent[0], ToolDefinition)

    @pytest.mark.asyncio
    async def test_llm_failure_returns_err(self) -> None:
        """An LLM that fails produces Err(AgentError)."""

        class FailingLLM:
            async def complete(self, messages, tools=None):
                raise OSError("connection reset")

        strategy = FunctionCallingStrategy()
        result = await strategy.execute(
            message="Hi",
            tools=[],
            history=[],
            llm=FailingLLM(),
        )

        assert result.is_err()
        assert "LLM failed" in str(result.unwrap_err())
