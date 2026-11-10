"""P2 hook surface import verification for quadkit-ai-llm."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_llm_hooks_root_module_exists() -> None:
    import quadkit.ai.llm
    from quadkit.ai.llm.hooks import (
        LLMProviderRegisteredHook,
        LLMRequestSentHook,
        LLMResponseReceivedHook,
    )

    assert LLMRequestSentHook.__name__ == "LLMRequestSentHook"
    assert LLMResponseReceivedHook.__name__ == "LLMResponseReceivedHook"
    assert LLMProviderRegisteredHook.__name__ == "LLMProviderRegisteredHook"
    assert quadkit.ai.llm.LLMRequestSentHook is LLMRequestSentHook
    assert quadkit.ai.llm.LLMResponseReceivedHook is LLMResponseReceivedHook
    assert quadkit.ai.llm.LLMProviderRegisteredHook is LLMProviderRegisteredHook


def test_llm_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.ai.llm.hooks import (
        LLMProviderRegisteredHook,
        LLMRequestSentHook,
        LLMResponseReceivedHook,
    )

    sent = LLMRequestSentHook(provider="openai", model="gpt-4o")
    received = LLMResponseReceivedHook(provider="openai", model="gpt-4o")
    registered = LLMProviderRegisteredHook(provider="openai")

    assert is_dataclass(sent)
    assert is_dataclass(received)
    assert is_dataclass(registered)

    with pytest.raises(TypeError):
        LLMRequestSentHook("openai", "gpt-4o")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        sent.provider = "anthropic"  # type: ignore[misc]

    with pytest.raises(TypeError):
        LLMResponseReceivedHook("openai", "gpt-4o")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        received.provider = "anthropic"  # type: ignore[misc]

    with pytest.raises(TypeError):
        LLMProviderRegisteredHook("openai")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        registered.provider = "anthropic"  # type: ignore[misc]
