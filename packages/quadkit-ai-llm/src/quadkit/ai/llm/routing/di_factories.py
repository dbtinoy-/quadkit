"""Factory functions for constructing LLM routing clients.

Used by ``LLMRoutingProvider`` to build a dict of provider-keyed
:class:`~quadkit.contracts.ai.LLMClientProtocol` instances from a
:class:`~quadkit.ai.llm.routing.config.LLMConfig`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.ai.llm.config import ClientConfig
from quadkit.contracts.ai.thinking import ThinkingConfig
from quadkit.logging import get_logger, safe_error_type

if TYPE_CHECKING:
    from quadkit.ai.llm.routing.config import (
        LLMConfig,
        ProviderConfig,
    )
    from quadkit.contracts.ai import LLMClientProtocol

logger = get_logger(__name__)

__all__ = ["create_routing_clients"]


def _thinking_from_provider(p: ProviderConfig) -> ThinkingConfig | None:
    """Build a ThinkingConfig for suppress-thinking providers.

    Returns ``ThinkingConfig(suppress=True)`` when the provider is configured
    with ``suppress_thinking=True``, otherwise ``None`` (no thinking config).

    Args:
        p: Routing provider configuration.

    Returns:
        A :class:`ThinkingConfig` with ``suppress=True`` or ``None``.
    """
    if p.suppress_thinking:
        return ThinkingConfig(suppress=True)
    return None


def _build_openai_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.openai import OpenAIClient

    config = ClientConfig(
        provider="openai",
        model=p.model,
        api_key=p.api_key,
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return OpenAIClient(config)  # type: ignore[return-value]


def _build_anthropic_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.anthropic import AnthropicClient

    config = ClientConfig(
        provider="anthropic",
        model=p.model,
        api_key=p.api_key,
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return AnthropicClient(config)  # type: ignore[return-value]


def _build_groq_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.groq import GroqClient

    config = ClientConfig(
        provider="groq",
        model=p.model,
        api_key=p.api_key,
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return GroqClient(config)  # type: ignore[return-value]


def _build_gemini_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.gemini import GeminiClient

    config = ClientConfig(
        provider="gemini",
        model=p.model,
        api_key=p.api_key,
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return GeminiClient(config)  # type: ignore[return-value]


def _build_mistral_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.mistral import MistralClient

    config = ClientConfig(
        provider="mistral",
        model=p.model,
        api_key=p.api_key,
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return MistralClient(config)  # type: ignore[return-value]


def _build_cohere_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.cohere import CohereClient

    config = ClientConfig(
        provider="cohere",
        model=p.model,
        api_key=p.api_key,
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return CohereClient(config)  # type: ignore[return-value]


def _build_openrouter_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.openrouter import OpenRouterClient

    config = ClientConfig(
        provider="openrouter",
        model=p.model,
        api_key=p.api_key,
        api_base=p.base_url or "https://openrouter.ai/api/v1",
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return OpenRouterClient(config)  # type: ignore[return-value]


def _build_deepseek_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.openai_compatible import OpenAICompatibleClient

    config = ClientConfig(
        provider="deepseek",
        model=p.model,
        api_key=p.api_key,
        api_base=p.base_url or "https://api.deepseek.com/v1",
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return OpenAICompatibleClient(config)  # type: ignore[return-value]


def _build_together_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.openai_compatible import OpenAICompatibleClient

    config = ClientConfig(
        provider="together",
        model=p.model,
        api_key=p.api_key,
        api_base=p.base_url or "https://api.together.xyz/v1",
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return OpenAICompatibleClient(config)  # type: ignore[return-value]


def _build_fireworks_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.openai_compatible import OpenAICompatibleClient

    config = ClientConfig(
        provider="fireworks",
        model=p.model,
        api_key=p.api_key,
        api_base=p.base_url or "https://api.fireworks.ai/inference/v1",
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return OpenAICompatibleClient(config)  # type: ignore[return-value]


def _build_ollama_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.ollama import OllamaClient

    config = ClientConfig(
        provider="ollama",
        model=p.model,
        api_base=p.base_url,
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return OllamaClient(config)  # type: ignore[return-value]


def _build_openai_compatible_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.openai_compatible import OpenAICompatibleClient

    config = ClientConfig(
        provider="openai_compatible",
        model=p.model,
        api_key=p.api_key,
        api_base=p.base_url,
        timeout=float(p.timeout),
        thinking=_thinking_from_provider(p),
    )
    return OpenAICompatibleClient(config)  # type: ignore[return-value]


def _build_azure_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.azure_openai import AzureOpenAIClient

    config = ClientConfig(
        provider="azure",
        model=p.model,
        api_key=p.api_key,
        api_base=p.base_url,
        timeout=float(p.timeout),
        extra=p.extras,
        thinking=_thinking_from_provider(p),
    )
    return AzureOpenAIClient(config)  # type: ignore[return-value]


def _build_cloudflare_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.cloudflare_workers import CloudflareWorkersClient

    config = ClientConfig(
        provider="cloudflare",
        model=p.model,
        timeout=float(p.timeout),
        extra=p.extras,
        thinking=_thinking_from_provider(p),
    )
    return CloudflareWorkersClient(config)  # type: ignore[return-value]


def _build_bedrock_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

    config = ClientConfig(
        provider="bedrock",
        model=p.model,
        timeout=float(p.timeout),
        extra=p.extras,
        thinking=_thinking_from_provider(p),
    )
    return BedrockClient(config)  # type: ignore[return-value]


def _build_vertex_client(p: ProviderConfig) -> LLMClientProtocol:
    from quadkit.ai.llm.clients.vertex_ai import VertexAIClient

    config = ClientConfig(
        provider="vertex",
        model=p.model,
        timeout=float(p.timeout),
        extra=p.extras,
        thinking=_thinking_from_provider(p),
    )
    return VertexAIClient(config)  # type: ignore[return-value]


_CLIENT_FACTORIES: dict[str, object] = {
    "openai": _build_openai_client,
    "anthropic": _build_anthropic_client,
    "groq": _build_groq_client,
    "gemini": _build_gemini_client,
    "mistral": _build_mistral_client,
    "cohere": _build_cohere_client,
    "openrouter": _build_openrouter_client,
    "deepseek": _build_deepseek_client,
    "together": _build_together_client,
    "fireworks": _build_fireworks_client,
    "ollama": _build_ollama_client,
    "openai_compatible": _build_openai_compatible_client,
    "azure": _build_azure_client,
    "cloudflare": _build_cloudflare_client,
    "bedrock": _build_bedrock_client,
    "vertex": _build_vertex_client,
}


def create_routing_clients(config: LLMConfig) -> dict[str, LLMClientProtocol]:
    """Build a provider-keyed dict of :class:`~quadkit.contracts.ai.LLMClientProtocol` instances.

    Only providers with :attr:`~ProviderConfig.enabled` set to ``True``
    and a recognised factory are included.  Unknown provider names emit a
    warning and are silently skipped.

    Args:
        config: Root routing configuration.

    Returns:
        Mapping of cascade-entry key (``ProviderConfig.key``, i.e.
        ``name:model``) → :class:`~quadkit.contracts.ai.LLMClientProtocol`.
        One client per entry, so per-entry timeout/thinking settings and
        circuit breakers stay isolated even when entries share a name.
    """
    clients: dict[str, LLMClientProtocol] = {}

    for provider_cfg in config.providers:
        if not provider_cfg.enabled:
            logger.info("llm.routing: skipping disabled provider")
            continue

        factory = _CLIENT_FACTORIES.get(provider_cfg.name)
        if factory is None:
            logger.warning("llm.routing: no factory for provider; skipping")
            continue

        try:
            clients[provider_cfg.key] = factory(provider_cfg)  # type: ignore[operator]
            logger.info("llm.routing: built provider client")
        except Exception as exc:
            logger.error(
                "llm.routing: failed to build provider client",
                error_type=safe_error_type(exc),
            )

    return clients
