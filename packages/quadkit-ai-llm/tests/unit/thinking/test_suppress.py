"""Tests for ThinkingConfig.suppress field."""

from __future__ import annotations

from quadkit.contracts.ai.thinking import ThinkingConfig


class TestThinkingConfigSuppress:
    def test_suppress_defaults_to_false(self) -> None:
        config = ThinkingConfig()
        assert config.suppress is False

    def test_suppress_can_be_set_true(self) -> None:
        config = ThinkingConfig(suppress=True)
        assert config.suppress is True

    def test_suppress_independent_of_budget_tokens(self) -> None:
        config = ThinkingConfig(suppress=True, budget_tokens=5000)
        assert config.suppress is True
        assert config.budget_tokens == 5000

    def test_suppress_independent_of_effort(self) -> None:
        config = ThinkingConfig(suppress=True, effort="low")
        assert config.suppress is True
        assert config.effort == "low"


from unittest.mock import MagicMock  # noqa: E402
from types import SimpleNamespace  # noqa: E402
import sys  # noqa: E402

from quadkit.ai.llm.config import ClientConfig  # noqa: E402
from quadkit.ai.llm.clients.openai import OpenAIClient  # noqa: E402
from quadkit.validation import SecretStr  # noqa: E402


def _make_client(suppress: bool) -> OpenAIClient:
    """Create an OpenAIClient with suppress_thinking set."""
    fake_openai = SimpleNamespace(
        AsyncOpenAI=lambda **kw: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=MagicMock()))
        ),
        APIError=Exception,
        AuthenticationError=Exception,
        RateLimitError=Exception,
        NotFoundError=Exception,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
    )
    sys.modules.setdefault("openai", fake_openai)

    config = ClientConfig(
        provider="openai",
        model="test-model",
        api_key=SecretStr("test-key"),
        thinking=ThinkingConfig(suppress=suppress),
    )
    return OpenAIClient(config)


class TestApplyThinkingSuppress:
    def test_suppress_true_injects_enable_thinking_false(self) -> None:
        client = _make_client(suppress=True)
        params: dict = {}
        client._apply_thinking(params)
        assert params.get("extra_body") == {
            "enable_thinking": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }

    def test_suppress_true_does_not_inject_reasoning_effort(self) -> None:
        client = _make_client(suppress=True)
        params: dict = {}
        client._apply_thinking(params)
        assert "reasoning_effort" not in params

    def test_suppress_true_merges_with_existing_extra_body(self) -> None:
        client = _make_client(suppress=True)
        params: dict = {"extra_body": {"my_custom_key": "value"}}
        client._apply_thinking(params)
        assert params["extra_body"]["enable_thinking"] is False
        assert params["extra_body"]["chat_template_kwargs"] == {"enable_thinking": False}
        assert params["extra_body"]["my_custom_key"] == "value"

    def test_suppress_false_does_nothing(self) -> None:
        client = _make_client(suppress=False)
        params: dict = {}
        client._apply_thinking(params)
        assert "extra_body" not in params
        assert "reasoning_effort" not in params

    def test_suppress_none_thinking_does_nothing(self) -> None:
        fake_openai = SimpleNamespace(
            AsyncOpenAI=lambda **kw: SimpleNamespace(
                chat=SimpleNamespace(completions=SimpleNamespace(create=MagicMock()))
            ),
            APIError=Exception,
            AuthenticationError=Exception,
            RateLimitError=Exception,
            NotFoundError=Exception,
            APITimeoutError=Exception,
            APIConnectionError=Exception,
        )
        sys.modules.setdefault("openai", fake_openai)
        config = ClientConfig(
            provider="openai",
            model="gpt-4",
            api_key=SecretStr("sk-test"),
            thinking=None,
        )
        client = OpenAIClient(config)
        params: dict = {}
        client._apply_thinking(params)
        assert "extra_body" not in params
        assert "reasoning_effort" not in params


from unittest.mock import AsyncMock  # noqa: E402

import pytest  # noqa: E402


def _make_ollama_client(thinking: ThinkingConfig | None = None):
    """Create an OllamaClient with a mock ollama.AsyncClient."""
    fake_ollama = SimpleNamespace(
        AsyncClient=lambda host: MagicMock(),
    )
    sys.modules["ollama"] = fake_ollama

    from quadkit.ai.llm.clients.ollama import OllamaClient

    config = ClientConfig(
        provider="ollama",
        model="llama3:8b",
        api_base="http://localhost:11434",
        thinking=thinking,
    )
    return OllamaClient(config)


class TestOllamaThinkingSuppress:
    @pytest.mark.asyncio
    async def test_suppress_true_injects_think_false(self) -> None:
        """When suppress=True, params must include think=False."""
        client = _make_ollama_client(ThinkingConfig(suppress=True))
        client.client.chat = AsyncMock(return_value={
            "message": {"content": "hello"},
            "model": "llama3:8b",
            "prompt_eval_count": 10,
            "eval_count": 5,
        })

        from quadkit.ai.llm.types import ChatMessage, Role

        await client._do_complete([ChatMessage(role=Role.USER, content="hi")])

        call_kwargs = client.client.chat.call_args[1]
        assert call_kwargs.get("think") is False

    @pytest.mark.asyncio
    async def test_suppress_false_does_not_inject_think(self) -> None:
        """When suppress=False, params must not include think key."""
        client = _make_ollama_client(ThinkingConfig(suppress=False))
        client.client.chat = AsyncMock(return_value={
            "message": {"content": "hello"},
            "model": "llama3:8b",
            "prompt_eval_count": 10,
            "eval_count": 5,
        })

        from quadkit.ai.llm.types import ChatMessage, Role

        await client._do_complete([ChatMessage(role=Role.USER, content="hi")])

        call_kwargs = client.client.chat.call_args[1]
        assert "think" not in call_kwargs

    @pytest.mark.asyncio
    async def test_thinking_none_does_not_inject_think(self) -> None:
        """When thinking=None, params must not include think key."""
        client = _make_ollama_client(thinking=None)
        client.client.chat = AsyncMock(return_value={
            "message": {"content": "hello"},
            "model": "llama3:8b",
            "prompt_eval_count": 10,
            "eval_count": 5,
        })

        from quadkit.ai.llm.types import ChatMessage, Role

        await client._do_complete([ChatMessage(role=Role.USER, content="hi")])

        call_kwargs = client.client.chat.call_args[1]
        assert "think" not in call_kwargs


def _make_anthropic_client(thinking: ThinkingConfig | None = None):
    """Create an AnthropicClient with a mock anthropic module."""
    fake_anthropic = SimpleNamespace(
        AsyncAnthropic=lambda **kw: SimpleNamespace(
            messages=SimpleNamespace(create=AsyncMock()),
        ),
    )
    sys.modules["anthropic"] = fake_anthropic

    from quadkit.ai.llm.clients.anthropic import AnthropicClient

    config = ClientConfig(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        api_key=SecretStr("sk-test"),
        thinking=thinking,
    )
    return AnthropicClient(config)


class TestAnthropicThinkingSuppress:
    def test_suppress_true_does_not_inject_thinking_param(self) -> None:
        """When suppress=True, _apply_thinking must NOT inject the thinking param."""
        client = _make_anthropic_client(ThinkingConfig(suppress=True))
        params: dict = {"temperature": 0.7}
        client._apply_thinking(params)
        assert "thinking" not in params
        # temperature should be preserved (not removed)
        assert params["temperature"] == 0.7

    def test_suppress_false_with_budget_injects_thinking(self) -> None:
        """When suppress=False with budget_tokens, thinking param must be injected."""
        client = _make_anthropic_client(ThinkingConfig(suppress=False, budget_tokens=8000))
        params: dict = {"temperature": 0.7}
        client._apply_thinking(params)
        assert params["thinking"] == {"type": "enabled", "budget_tokens": 8000}
        # temperature must be removed (incompatible with thinking)
        assert "temperature" not in params

    def test_thinking_none_does_nothing(self) -> None:
        """When thinking=None, _apply_thinking is a no-op."""
        client = _make_anthropic_client(thinking=None)
        params: dict = {"temperature": 0.5}
        client._apply_thinking(params)
        assert "thinking" not in params
        assert params["temperature"] == 0.5
