"""Tests for the OpenAI Chat Completions wire DTO."""
from __future__ import annotations

from quadkit.contracts.ai.relay.dto import (
    OpenAIChatChoice,
    OpenAIChatMessage,
    OpenAIChatRequest,
    OpenAIChatResponse,
    OpenAIChatStreamChunk,
    OpenAIChatStreamChoice,
    OpenAIChatStreamDelta,
)


class TestOpenAIChatDto:
    def test_to_dict_string_content(self) -> None:
        message = OpenAIChatMessage(role="user", content="Hello")
        data = message.to_dict()
        assert data == {"role": "user", "content": "Hello"}

    def test_to_dict_preserves_passthrough(self) -> None:
        message = OpenAIChatMessage(
            role="assistant",
            content="Hi",
            passthrough={"refusal": None},
        )
        data = message.to_dict()
        assert data["refusal"] is None

    def test_from_dict_drops_none_optional_fields(self) -> None:
        request = OpenAIChatRequest.from_dict(
            {"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}
        )
        assert request.temperature is None
        assert request.max_tokens is None

    def test_request_to_dict_omits_none(self) -> None:
        request = OpenAIChatRequest(
            model="gpt-4o",
            messages=[OpenAIChatMessage(role="user", content="hi")],
        )
        data = request.to_dict()
        assert data == {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        }

    def test_request_to_dict_keeps_explicit_zero(self) -> None:
        request = OpenAIChatRequest(
            model="gpt-4o",
            messages=[],
            temperature=0.0,
        )
        data = request.to_dict()
        assert data["temperature"] == 0.0

    def test_request_carries_normalization_fields(self) -> None:
        """top_p, max_completion_tokens, parallel_tool_calls, reasoning, tier survive."""
        request = OpenAIChatRequest.from_dict(
            {
                "model": "gpt-4o",
                "messages": [],
                "top_p": 0.9,
                "max_completion_tokens": 100,
                "parallel_tool_calls": False,
                "reasoning": {"effort": "medium"},
                "service_tier": "flex",
            }
        )
        assert request.top_p == 0.9
        assert request.max_completion_tokens == 100
        assert request.parallel_tool_calls is False
        assert request.reasoning == {"effort": "medium"}
        assert request.service_tier == "flex"
        data = request.to_dict()
        assert data["max_completion_tokens"] == 100
        assert data["parallel_tool_calls"] is False


class TestOpenAIChatResponseDto:
    def test_response_round_trip(self) -> None:
        response = OpenAIChatResponse(
            id="chatcmpl-1",
            model="gpt-4o",
            choices=[
                OpenAIChatChoice(
                    index=0,
                    message=OpenAIChatMessage(
                        role="assistant",
                        content="Hi",
                        tool_calls=[
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"city": "Paris"}',
                                },
                            }
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            system_fingerprint="fp_1",
            passthrough={"created": 123, "object": "chat.completion", "unknown": {"a": 1}},
        )
        data = response.to_dict()
        assert data["id"] == "chatcmpl-1"
        assert data["model"] == "gpt-4o"
        assert data["choices"][0]["index"] == 0
        assert data["choices"][0]["finish_reason"] == "tool_calls"
        assert data["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "get_weather"
        assert data["usage"]["total_tokens"] == 15
        assert data["unknown"] == {"a": 1}

    def test_response_from_dict(self) -> None:
        response = OpenAIChatResponse.from_dict(
            {
                "id": "chatcmpl-2",
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hi"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "system_fingerprint": "fp_2",
            }
        )
        assert response.id == "chatcmpl-2"
        assert response.choices[0].message is not None
        assert response.choices[0].message.content == "Hi"
        assert response.choices[0].finish_reason == "stop"
        assert response.usage is not None and response.usage["total_tokens"] == 2


class TestOpenAIChatStreamDto:
    def test_stream_chunk_round_trip(self) -> None:
        chunk = OpenAIChatStreamChunk(
            id="chatcmpl-3",
            model="gpt-4o",
            choices=[
                OpenAIChatStreamChoice(
                    index=0,
                    delta=OpenAIChatStreamDelta(
                        role="assistant",
                        content="Hel",
                        tool_calls=[
                            {
                                "index": 0,
                                "id": "call_1",
                                "function": {"name": "get_weather", "arguments": '{"c'},
                            }
                        ],
                        reasoning_content="thinking...",
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
            system_fingerprint="fp_3",
        )
        data = chunk.to_dict()
        assert data["object"] == "chat.completion.chunk"
        assert data["choices"][0]["delta"]["content"] == "Hel"
        assert data["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"] == '{"c'
        assert data["choices"][0]["delta"]["reasoning_content"] == "thinking..."
        assert "usage" not in data

    def test_stream_chunk_usage_only_finish(self) -> None:
        chunk = OpenAIChatStreamChunk.from_dict(
            {
                "id": "chatcmpl-4",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "gpt-4o",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            }
        )
        assert chunk.choices[0].finish_reason == "stop"
        assert chunk.choices[0].delta is not None
        assert chunk.usage is not None and chunk.usage["total_tokens"] == 5