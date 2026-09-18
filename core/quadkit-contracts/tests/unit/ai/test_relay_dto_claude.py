"""Tests for the Claude Messages wire DTO."""
from __future__ import annotations

from quadkit.contracts.ai.relay.dto import (
    ClaudeContent,
    ClaudeMessage,
    ClaudeRequest,
    ClaudeResponse,
    ClaudeStreamEvent,
    ClaudeUsage,
)


class TestClaudeDto:
    def test_text_content_block(self) -> None:
        block = ClaudeContent.from_dict({"type": "text", "text": "hi"})
        assert block.type == "text"
        assert block.text == "hi"

    def test_message_to_dict(self) -> None:
        message = ClaudeMessage(
            role="user",
            content=[ClaudeContent(type="text", text="hi")],
        )
        data = message.to_dict()
        assert data == {"role": "user", "content": [{"type": "text", "text": "hi"}]}

    def test_request_max_tokens_required(self) -> None:
        request = ClaudeRequest.from_dict(
            {"model": "claude-sonnet-4-5", "max_tokens": 1024,
             "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]}
        )
        assert request.max_tokens == 1024
        assert request.stream is False

    def test_request_to_dict_omits_none(self) -> None:
        request = ClaudeRequest(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[ClaudeMessage(role="user", content=[ClaudeContent(type="text", text="hi")])],
        )
        data = request.to_dict()
        assert "system" not in data
        assert data["max_tokens"] == 1024

    def test_request_carries_top_p_and_metadata(self) -> None:
        """top_p and metadata survive the round trip."""
        request = ClaudeRequest.from_dict(
            {
                "model": "claude-sonnet-4-5",
                "max_tokens": 1024,
                "messages": [],
                "top_p": 0.9,
                "metadata": {"user_id": "u1"},
            }
        )
        assert request.top_p == 0.9
        assert request.metadata == {"user_id": "u1"}
        data = request.to_dict()
        assert data["top_p"] == 0.9
        assert data["metadata"] == {"user_id": "u1"}

    def test_thinking_and_tool_blocks_round_trip(self) -> None:
        """Thinking/signature and tool_use blocks survive from_dict -> to_dict."""
        message = ClaudeMessage.from_dict(
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "let me think", "signature": "sig_1"},
                    {"type": "tool_use", "id": "tu_1", "name": "get_weather", "input": {"city": "Paris"}},
                ],
            }
        )
        data = message.to_dict()
        assert data["content"][0] == {
            "type": "thinking",
            "thinking": "let me think",
            "signature": "sig_1",
        }
        assert data["content"][1] == {
            "type": "tool_use",
            "id": "tu_1",
            "name": "get_weather",
            "input": {"city": "Paris"},
        }


class TestClaudeResponseDto:
    def test_response_round_trip(self) -> None:
        response = ClaudeResponse(
            id="msg_1",
            model="claude-sonnet-4-5",
            content=[
                ClaudeContent(type="text", text="Hi"),
                ClaudeContent(type="tool_use", name="get_weather", input={"city": "Paris"}),
            ],
            stop_reason="tool_use",
            usage=ClaudeUsage(input_tokens=10, output_tokens=5),
            passthrough={"stop_sequence": None},
        )
        data = response.to_dict()
        assert data["id"] == "msg_1"
        assert data["model"] == "claude-sonnet-4-5"
        assert data["type"] == "message"
        assert data["role"] == "assistant"
        assert data["content"][1]["type"] == "tool_use"
        assert data["stop_reason"] == "tool_use"
        assert data["usage"]["input_tokens"] == 10
        assert data["usage"]["output_tokens"] == 5

    def test_response_from_dict(self) -> None:
        response = ClaudeResponse.from_dict(
            {
                "id": "msg_2",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": "Hi"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 3,
                    "output_tokens": 2,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            }
        )
        assert response.id == "msg_2"
        assert response.content[0].text == "Hi"
        assert response.stop_reason == "end_turn"
        assert response.usage is not None
        assert response.usage.total_tokens == 5

    def test_usage_derives_total(self) -> None:
        usage = ClaudeUsage(input_tokens=2, output_tokens=3, cache_read_input_tokens=4)
        assert usage.total_tokens == 5


class TestClaudeStreamEvents:
    def test_message_start_event(self) -> None:
        event = ClaudeStreamEvent.from_dict(
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-5",
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 10, "output_tokens": 0},
                },
            }
        )
        assert event.type == "message_start"
        assert event.message is not None
        assert event.message.id == "msg_1"
        assert event.message.usage is not None
        assert event.message.usage.input_tokens == 10

    def test_content_block_start_and_delta(self) -> None:
        start = ClaudeStreamEvent.from_dict(
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
        )
        delta = ClaudeStreamEvent.from_dict(
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Hel"},
            }
        )
        assert start.index == 0
        assert start.content_block is not None and start.content_block.type == "text"
        assert delta.delta == {"type": "text_delta", "text": "Hel"}

    def test_message_delta_and_stop(self) -> None:
        delta = ClaudeStreamEvent.from_dict(
            {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
             "usage": {"output_tokens": 5}}
        )
        stop = ClaudeStreamEvent.from_dict({"type": "message_stop"})
        assert delta.delta == {"stop_reason": "end_turn", "stop_sequence": None}
        assert delta.usage is not None and delta.usage.output_tokens == 5
        assert stop.type == "message_stop"

    def test_ping_and_error_events(self) -> None:
        ping = ClaudeStreamEvent.from_dict({"type": "ping"})
        error = ClaudeStreamEvent.from_dict(
            {"type": "error", "error": {"type": "overloaded_error", "message": "busy"}}
        )
        assert ping.type == "ping"
        assert error.error == {"type": "overloaded_error", "message": "busy"}

    def test_unknown_event_fields_retained(self) -> None:
        event = ClaudeStreamEvent.from_dict(
            {"type": "content_block_stop", "index": 0, "extra": {"x": 1}}
        )
        assert event.passthrough == {"extra": {"x": 1}}
