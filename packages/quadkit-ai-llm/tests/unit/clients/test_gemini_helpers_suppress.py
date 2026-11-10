"""Tests for inject_thinking_config suppress path."""

from __future__ import annotations

from quadkit.ai.llm.clients.gemini_helpers import inject_thinking_config
from quadkit.ai.llm.config import ClientConfig
from quadkit.contracts.ai.thinking import ThinkingConfig


def _make_config(thinking: ThinkingConfig | None = None) -> ClientConfig:
    return ClientConfig(
        provider="gemini",
        model="gemini-2.5-flash",
        api_key=None,
        thinking=thinking,
    )


class TestInjectThinkingConfigSuppress:
    def test_suppress_true_sets_thinking_budget_zero(self) -> None:
        """When suppress=True, thinkingConfig.thinkingBudget must be 0."""
        config = _make_config(ThinkingConfig(suppress=True))
        gen_config: dict = {}
        inject_thinking_config(gen_config, config)
        assert gen_config["thinkingConfig"] == {"thinkingBudget": 0}

    def test_suppress_false_with_budget_uses_budget(self) -> None:
        """When suppress=False with budget_tokens, uses the budget value."""
        config = _make_config(ThinkingConfig(suppress=False, budget_tokens=5000))
        gen_config: dict = {}
        inject_thinking_config(gen_config, config)
        assert gen_config["thinkingConfig"] == {"thinkingBudget": 5000}

    def test_suppress_false_with_level_uses_level(self) -> None:
        """When level is set, thinkingLevel takes precedence."""
        config = _make_config(ThinkingConfig(suppress=False, level="medium"))
        gen_config: dict = {}
        inject_thinking_config(gen_config, config)
        assert gen_config["thinkingConfig"] == {"thinkingLevel": "medium"}

    def test_thinking_none_does_nothing(self) -> None:
        """When thinking=None, gen_config is not modified."""
        config = _make_config(thinking=None)
        gen_config: dict = {}
        inject_thinking_config(gen_config, config)
        assert "thinkingConfig" not in gen_config

    def test_suppress_true_overrides_level(self) -> None:
        """Suppress=True takes precedence even if level is also set."""
        config = _make_config(ThinkingConfig(suppress=True, level="high"))
        gen_config: dict = {}
        inject_thinking_config(gen_config, config)
        assert gen_config["thinkingConfig"] == {"thinkingBudget": 0}
