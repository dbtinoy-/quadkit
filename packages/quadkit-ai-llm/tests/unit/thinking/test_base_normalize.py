"""Tests for _normalize_thinking in AbstractLLMClient."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.ai.llm.clients.base import AbstractLLMClient
from quadkit.ai.llm.types import Completion
from quadkit.contracts.ai.thinking import ThinkingResult


def _make_client() -> AbstractLLMClient:
    """Create a minimal concrete subclass for testing."""
    from quadkit.ai.llm.config import ClientConfig

    config = MagicMock(spec=ClientConfig)
    config.provider = MagicMock()
    config.provider.value = "test"
    config.timeout = 30.0
    config.extra = {}

    class _ConcreteClient(AbstractLLMClient):
        async def _do_complete(self, messages, **kwargs):
            pass

        async def _do_stream_chat(self, messages, **kwargs):
            pass

        async def _do_chat(self, messages, tools=None, **kwargs):
            pass

        async def health_check(self, timeout=5.0):
            pass

    return _ConcreteClient(config=config)


class TestNormalizeThinking:
    def test_passes_through_when_thinking_already_set(self) -> None:
        client = _make_client()
        existing = ThinkingResult(content="already extracted")
        completion = Completion(
            content="Clean content",
            model="test-model",
            thinking=existing,
        )
        result = client._normalize_thinking(completion)
        assert result is completion  # same object — unchanged

    def test_strips_xml_think_tags(self) -> None:
        client = _make_client()
        completion = Completion(
            content="<think>Reasoning</think>Clean answer",
            model="test-model",
        )
        result = client._normalize_thinking(completion)
        assert result.content == "Clean answer"
        assert result.thinking is not None
        assert result.thinking.content == "Reasoning"

    def test_strips_gemma4_channel_format(self) -> None:
        client = _make_client()
        completion = Completion(
            content="<|channel>thought\nMy reasoning\n<channel|>\nThe answer",
            model="gemma-4",
        )
        result = client._normalize_thinking(completion)
        assert result.content == "The answer"
        assert result.thinking is not None
        assert result.thinking.content == "My reasoning"

    def test_passthrough_clean_content(self) -> None:
        client = _make_client()
        completion = Completion(
            content="No thinking here",
            model="test-model",
        )
        result = client._normalize_thinking(completion)
        assert result is completion  # unchanged
        assert result.thinking is None
