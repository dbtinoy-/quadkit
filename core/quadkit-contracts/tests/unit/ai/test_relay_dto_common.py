"""Shared JSON/passthrough behavior across every relay wire DTO family."""
from __future__ import annotations

import pytest

from quadkit.contracts.ai.exceptions import RelayError
from quadkit.contracts.ai.relay.dto import (
    ClaudeRequest,
    GeminiRequest,
    OpenAIChatRequest,
    ResponsesRequest,
)


def test_known_fields_win_over_passthrough_keys() -> None:
    """Known fields are never shadowed by passthrough duplicates."""
    request = OpenAIChatRequest(
        model="gpt-4o",
        messages=[],
        temperature=0.0,
        passthrough={"temperature": 1.0, "extra": "kept"},
    )
    data = request.to_dict()
    assert data["temperature"] == 0.0
    assert data["extra"] == "kept"


def test_unknown_nested_objects_survive_round_trip() -> None:
    """Unknown nested structures survive from_dict -> to_dict."""
    raw = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": "hi",
                "custom_metadata": {"nested": [1, 2, {"deep": True}]},
            }
        ],
        "top_logprobs": {"top": [0.9, 0.1]},
    }
    request = OpenAIChatRequest.from_dict(raw)
    data = request.to_dict()
    assert data["messages"][0]["custom_metadata"] == {"nested": [1, 2, {"deep": True}]}
    assert data["top_logprobs"] == {"top": [0.9, 0.1]}


def test_none_means_omitted_for_optional_scalars() -> None:
    """Optional scalar fields are absent from the wire dict when None."""
    request = ResponsesRequest(model="gpt-4o", input=[])
    data = request.to_dict()
    assert "temperature" not in data
    assert "instructions" not in data
    assert "max_output_tokens" not in data


def test_explicit_zero_false_and_empty_lists_survive() -> None:
    """Explicit 0, false, and empty list values are preserved."""
    request = OpenAIChatRequest(
        model="gpt-4o",
        messages=[],
        temperature=0.0,
        stop=[],
        stream_options={"include_usage": False},
    )
    data = request.to_dict()
    assert data["temperature"] == 0.0
    assert data["stop"] == []
    assert data["stream_options"] == {"include_usage": False}


def test_malformed_required_fields_raise_relay_error() -> None:
    """Missing required fields return a typed malformed_payload error."""
    with pytest.raises(RelayError) as excinfo:
        OpenAIChatRequest.from_dict({"messages": []})
    assert excinfo.value.code == "malformed_payload"


def test_malformed_required_claude_max_tokens_raises_relay_error() -> None:
    """Claude max_tokens is required and yields a typed error when absent."""
    with pytest.raises(RelayError) as excinfo:
        ClaudeRequest.from_dict(
            {"model": "claude-sonnet-4-5", "messages": []}
        )
    assert excinfo.value.code == "malformed_payload"


def test_malformed_required_gemini_contents_raises_relay_error() -> None:
    """Gemini contents are required and yield a typed error when absent."""
    with pytest.raises(RelayError) as excinfo:
        GeminiRequest.from_dict({})
    assert excinfo.value.code == "malformed_payload"
