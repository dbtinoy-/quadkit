"""Tests for the relay conversion IR and canonical shared types."""
from __future__ import annotations

from quadkit.contracts.ai import (
    ChatMessage,
    ConversionQuality,
    RelayConvertResult,
    RelayError,
    RelayFormat,
    RelayRequest,
    RelayResponse,
    RelayUsage,
    StreamDelta,
    StreamState,
    ThinkingConfig,
    ToolCall,
)


def test_relay_format_values() -> None:
    """RelayFormat maps to the four supported wire protocols."""
    assert RelayFormat.OPENAI_CHAT.value == "openai_chat"
    assert RelayFormat.CLAUDE.value == "claude"
    assert RelayFormat.GEMINI.value == "gemini"
    assert RelayFormat.OPENAI_RESPONSES.value == "openai_responses"


def test_relay_usage_defaults_to_zero() -> None:
    """RelayUsage defaults to zero tokens in every breakdown field."""
    usage = RelayUsage()
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.total_tokens == 0
    assert usage.cache_read_tokens == 0
    assert usage.reasoning_tokens == 0


def test_relay_usage_derives_total() -> None:
    """total_tokens is derived as prompt + completion."""
    usage = RelayUsage(prompt_tokens=10, completion_tokens=5)
    assert usage.total_tokens == 15


def test_relay_request_defaults() -> None:
    """RelayRequest defaults to non-streaming with empty tools."""
    request = RelayRequest(model="gpt-4o", messages=[])
    assert request.stream is False
    assert request.tools == []
    assert request.metadata == {}
    assert request.passthrough == {}
    assert request.temperature is None
    assert request.top_p is None
    assert request.top_k is None
    assert request.system is None
    assert request.tool_choice is None
    assert request.response_format is None
    assert request.parallel_tool_calls is None
    assert request.thinking is None


def test_relay_request_carries_parameters() -> None:
    """RelayRequest carries flattened generation knobs."""
    request = RelayRequest(
        model="claude-sonnet-4-5",
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.0,
        top_p=0.9,
        top_k=40,
        max_tokens=100,
        stream=True,
        include_usage=True,
        stop_sequences=["STOP"],
        system="Be helpful",
        tool_choice="auto",
        parallel_tool_calls=True,
        thinking=ThinkingConfig(budget_tokens=5000),
    )
    assert request.temperature == 0.0
    assert request.top_p == 0.9
    assert request.top_k == 40
    assert request.max_tokens == 100
    assert request.stream is True
    assert request.include_usage is True
    assert request.stop_sequences == ["STOP"]
    assert request.system == "Be helpful"
    assert request.tool_choice == "auto"
    assert request.parallel_tool_calls is True
    assert request.thinking is not None
    assert request.thinking.budget_tokens == 5000


def test_relay_response_defaults() -> None:
    """RelayResponse defaults to empty content and no tool calls."""
    response = RelayResponse(model="gpt-4o")
    assert response.content == ""
    assert response.tool_calls == []
    assert response.finish_reason is None
    assert response.usage is None


def test_convert_result_carries_metadata() -> None:
    """RelayConvertResult carries conversion audit metadata."""
    result = RelayConvertResult(
        value=RelayRequest(model="m", messages=[]),
        source=RelayFormat.OPENAI_CHAT,
        target=RelayFormat.CLAUDE,
        converter_id="openai_chat_to_claude",
        quality=ConversionQuality.GOOD,
        steps=["openai_chat", "ir", "claude"],
    )
    assert result.source is RelayFormat.OPENAI_CHAT
    assert result.target is RelayFormat.CLAUDE
    assert result.converter_id == "openai_chat_to_claude"
    assert result.quality == ConversionQuality.GOOD
    assert result.steps == ["openai_chat", "ir", "claude"]


def test_relay_error_is_ai_error() -> None:
    """RelayError subclasses AIError and carries the QK_ERR_AI code."""
    from quadkit.contracts.ai.exceptions import AIError

    error = RelayError("cannot convert")
    assert isinstance(error, AIError)
    assert error._code == "QK_ERR_AI_006"
    assert "cannot convert" in str(error)


def test_stream_delta_fields() -> None:
    """StreamDelta models one canonical stream update."""
    usage = RelayUsage(prompt_tokens=2, completion_tokens=3)
    delta = StreamDelta(content="Hi", usage=usage, finish_reason="stop")
    assert delta.content == "Hi"
    assert delta.usage is not None and delta.usage.total_tokens == 5
    assert delta.thinking_delta is None
    assert delta.kind == "content"
    assert delta.tool_call_index is None
    assert delta.tool_call_arguments is None
    assert delta.status is None
    assert delta.block_index is None
    assert delta.output_index is None


def test_stream_state_fields() -> None:
    """StreamState describes one upstream stream."""
    state = StreamState(
        source=RelayFormat.OPENAI_CHAT,
        target=RelayFormat.CLAUDE,
        model="gpt-4o",
        include_usage=True,
    )
    assert state.source is RelayFormat.OPENAI_CHAT
    assert state.target is RelayFormat.CLAUDE
    assert state.model == "gpt-4o"
    assert state.include_usage is True
    assert state.is_done is False
    assert state.tool_calls == []