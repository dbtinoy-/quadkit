"""Root hook payload surface for quadkit-ai-llm.

Defines canonical payload dataclasses for LLM-lifecycle hook points. Actual
hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "LLMProviderRegisteredHook",
    "LLMRequestSentHook",
    "LLMResponseReceivedHook",
]


@dataclass(frozen=True, kw_only=True)
class LLMRequestSentHook:
    """Payload fired when an LLM request is dispatched to a provider.

    Attributes:
        provider: Provider identifier (e.g. ``"openai"``).
        model: Model name targeted by the request (e.g. ``"gpt-4o"``).
    """

    provider: str
    model: str


@dataclass(frozen=True, kw_only=True)
class LLMResponseReceivedHook:
    """Payload fired when a complete LLM response is received from a provider.

    Attributes:
        provider: Provider identifier that returned the response.
        model: Model name that produced the response.
    """

    provider: str
    model: str


@dataclass(frozen=True, kw_only=True)
class LLMProviderRegisteredHook:
    """Payload fired when an LLM provider is registered in the provider registry.

    Attributes:
        provider: Identifier of the provider that was registered.
    """

    provider: str
