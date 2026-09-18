"""Normalization tests for the canonical relay IR."""
from __future__ import annotations

import pytest

from quadkit.contracts.ai import (
    ChatMessage,
    FunctionCall,
    RelayResponse,
    RelayUsage,
    StreamDelta,
    StreamState,
    ThinkingConfig,
    ThinkingResult,
    ToolCall,
)
from quadkit.contracts.ai.llm import TokenUsage
from quadkit.contracts.ai.relay.ir import normalize_finish_reason
from quadkit.contracts.ai.relay.types import RelayFormat


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("stop", "stop"),
        ("end_turn", "stop"),
        ("stop_sequence", "stop"),
        ("STOP", "stop"),
        ("length", "length"),
        ("max_tokens", "length"),
        ("tool_calls", "tool_calls"),
        ("tool_use", "tool_calls"),
        ("function_call", "function_call"),
        ("malformed_function_call", "function_call"),
        ("content_filter", "content_filter"),
        ("safety", "content_filter"),
        ("recitation", "content_filter"),
        ("prohibited_content", "content_filter"),
        ("other", "other"),
        ("model_finish_reason_unspecified", "other"),
        ("unknown_reason", "other"),
        (None, None),
        ("", None),
    ],
)
def test_finish_reason_normalization(raw: str | None, expected: str | None) -> None:
    """Finish reasons from every wire format normalize to the canonical set."""
    assert normalize_finish_reason(raw) == expected


def test_usage_total_derivation() -> None:
    """RelayUsage derives total tokens from prompt plus completion."""
    usage = RelayUsage(prompt_tokens=12, completion_tokens=7)
    assert usage.total_tokens == 19
    assert usage.cache_read_tokens == 0
    assert usage.reasoning_tokens == 0


def test_usage_converts_to_shared_token_usage() -> None:
    """RelayUsage maps onto the shared TokenUsage without double counting."""
    usage = RelayUsage(
        prompt_tokens=10,
        completion_tokens=5,
        cache_read_tokens=3,
        reasoning_tokens=2,
    )
    token_usage = usage.to_token_usage()
    assert token_usage == TokenUsage(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )


def test_empty_response_shape() -> None:
    """A response with no content and no tool calls is structurally valid."""
    response = RelayResponse(model="gpt-4o")
    assert response.content == ""
    assert response.tool_calls == []
    assert response.tool_results == []
    assert response.thinking is None
    assert response.status is None
    assert response.incomplete_details is None


def test_tool_only_response() -> None:
    """A tool-only turn keeps content empty while carrying tool calls."""
    call = ToolCall(
        id="call_1",
        function=FunctionCall(name="get_weather", arguments={"city": "Paris"}),
    )
    response = RelayResponse(
        model="claude-sonnet-4-5",
        content="",
        tool_calls=[call],
        finish_reason="tool_calls",
    )
    assert response.content == ""
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].function is not None
    assert response.tool_calls[0].function.name == "get_weather"
    assert response.finish_reason == "tool_calls"


def test_content_plus_tool_calls_response() -> None:
    """Content and tool calls can coexist in one assistant turn."""
    call = ToolCall(id="call_2", function=FunctionCall(name="search", arguments={}))
    response = RelayResponse(
        model="gpt-4o",
        content="I will look that up.",
        tool_calls=[call],
        finish_reason="tool_calls",
    )
    assert response.content == "I will look that up."
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].id == "call_2"


def test_response_carries_tool_results() -> None:
    """Tool results flow back as canonical role='tool' messages."""
    response = RelayResponse(
        model="gpt-4o",
        content="",
        tool_results=[
            ChatMessage(role="tool", content="72 degrees", tool_call_id="call_1")
        ],
    )
    assert len(response.tool_results) == 1
    assert response.tool_results[0].tool_call_id == "call_1"
    assert response.tool_results[0].content == "72 degrees"


def test_thinking_signature_preserved() -> None:
    """ThinkingResult signatures survive on the response and the stream state."""
    thinking = ThinkingResult(
        content="Let me reason step by step.",
        signature="sig_abc123",
        tokens=42,
    )
    response = RelayResponse(model="claude-sonnet-4-5", content="", thinking=thinking)
    assert response.thinking is not None
    assert response.thinking.signature == "sig_abc123"
    assert response.thinking.tokens == 42

    state = StreamState(
        source=RelayFormat.CLAUDE,
        target=RelayFormat.OPENAI_CHAT,
        model="claude-sonnet-4-5",
        thinking_signatures=["sig_abc123"],
    )
    assert state.thinking_signatures == ["sig_abc123"]


def test_request_thinking_is_config_not_result() -> None:
    """RelayRequest.thinking is an input config, never an output result."""
    request = ThinkingConfig(effort="high")
    assert request.effort == "high"
    assert request.suppress is False


def test_stream_delta_carries_block_and_output_indices() -> None:
    """StreamDelta tracks both Claude block and Responses output indices."""
    delta = StreamDelta(content="Hi", block_index=0, output_index=1)
    assert delta.block_index == 0
    assert delta.output_index == 1
    assert delta.passthrough == {}


def test_stream_delta_passthrough_metadata() -> None:
    """StreamDelta preserves extra per-event metadata verbatim."""
    delta = StreamDelta(kind="content", content="x", passthrough={"custom": 1})
    assert delta.passthrough == {"custom": 1}
