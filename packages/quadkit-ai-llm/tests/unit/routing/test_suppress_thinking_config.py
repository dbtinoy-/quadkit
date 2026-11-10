"""Tests for suppress_thinking env-var parsing in LLMConfig.from_env()."""
from __future__ import annotations

import pytest

from quadkit.ai.llm.routing.config import LLMConfig, ProviderConfig


class TestSuppressThinkingEnvParsing:
    def test_openai_compatible_suppress_thinking_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QK_AI_LLM__PROVIDERS__OPENAI_COMPATIBLE__BASE_URL", "http://localhost:1234/v1")
        monkeypatch.setenv("QK_AI_LLM__PROVIDERS__OPENAI_COMPATIBLE__MODEL", "gemma-4")
        monkeypatch.setenv("QK_AI_LLM__PROVIDERS__OPENAI_COMPATIBLE__SUPPRESS_THINKING", "true")
        config = LLMConfig.from_env()
        openai_compatible = next(p for p in config.providers if p.name == "openai_compatible")
        assert openai_compatible.suppress_thinking is True

    def test_openai_compatible_suppress_thinking_false_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("QK_AI_LLM__PROVIDERS__OPENAI_COMPATIBLE__BASE_URL", "http://localhost:1234/v1")
        monkeypatch.setenv("QK_AI_LLM__PROVIDERS__OPENAI_COMPATIBLE__MODEL", "gemma-4")
        monkeypatch.delenv("QK_AI_LLM__PROVIDERS__OPENAI_COMPATIBLE__SUPPRESS_THINKING", raising=False)
        config = LLMConfig.from_env()
        openai_compatible = next(p for p in config.providers if p.name == "openai_compatible")
        assert openai_compatible.suppress_thinking is False

    def test_ollama_suppress_thinking_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QK_AI_LLM__PROVIDERS__OLLAMA__BASE_URL", "http://localhost:11434")
        monkeypatch.setenv("QK_AI_LLM__PROVIDERS__OLLAMA__SUPPRESS_THINKING", "true")
        config = LLMConfig.from_env()
        ollama = next(p for p in config.providers if p.name == "ollama")
        assert ollama.suppress_thinking is True

    def test_key_auth_provider_suppress_thinking(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("QK_AI_LLM__PROVIDERS__OPENAI__API_KEY", "sk-test")
        monkeypatch.setenv("QK_AI_LLM__PROVIDERS__OPENAI__SUPPRESS_THINKING", "true")
        config = LLMConfig.from_env()
        openai_p = next(p for p in config.providers if p.name == "openai")
        assert openai_p.suppress_thinking is True


from unittest.mock import patch
from quadkit.ai.llm.routing.di_factories import _build_openai_compatible_client
from quadkit.contracts.ai.thinking import ThinkingConfig  # noqa: F401


class TestDiFactorySuppressThinking:
    def test_openai_compatible_suppress_true_creates_thinking_config(self) -> None:
        p = ProviderConfig(
            name="openai_compatible",
            model="gemma-4",
            base_url="http://localhost:1234/v1",
            suppress_thinking=True,
        )
        captured: list = []

        def fake_init(self_inner, config):
            captured.append(config)

        with patch(
            "quadkit.ai.llm.clients.openai_compatible.OpenAICompatibleClient.__init__",
            fake_init,
        ):
            _build_openai_compatible_client(p)

        assert len(captured) == 1
        client_config = captured[0]
        assert client_config.thinking is not None
        assert client_config.thinking.suppress is True

    def test_openai_compatible_suppress_false_no_thinking_config(self) -> None:
        p = ProviderConfig(
            name="openai_compatible",
            model="gemma-4",
            base_url="http://localhost:1234/v1",
            suppress_thinking=False,
        )
        captured: list = []

        def fake_init(self_inner, config):
            captured.append(config)

        with patch(
            "quadkit.ai.llm.clients.openai_compatible.OpenAICompatibleClient.__init__",
            fake_init,
        ):
            _build_openai_compatible_client(p)

        assert len(captured) == 1
        client_config = captured[0]
        assert client_config.thinking is None
