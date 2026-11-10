"""OpenAI-compatible LLM client base for third-party providers.

Many providers (DeepSeek, Together AI, Fireworks AI, etc.) expose an
OpenAI-compatible REST API.  This module provides an intermediate base class,
:class:`OpenAICompatibleClient`, that re-uses all logic from
:class:`~quadkit.ai.llm.clients.openai.OpenAIClient` while pointing the
``AsyncOpenAI`` client at a different ``base_url``.

Concrete subclasses only need to override :attr:`_provider_base_url` and
:attr:`_provider_name`; all other behaviour (streaming, tool calling, retry,
error handling) is inherited unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.ai.llm.clients.openai import OpenAIClient
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.logging import safe_error_type

if TYPE_CHECKING:
    from quadkit.ai.llm.config import ClientConfig

__all__ = [
    "DeepSeekClient",
    "FireworksClient",
    "OpenAICompatibleClient",
    "TogetherClient",
]


class OpenAICompatibleClient(OpenAIClient):
    """Thin base class for providers that expose an OpenAI-compatible API.

    Subclasses must declare :attr:`_provider_base_url` (the base URL of the
    provider's ``/v1`` endpoint) and :attr:`_provider_name` (used in health
    check payloads and log messages).

    The ``AsyncOpenAI`` client from the ``openai`` SDK is configured to send
    requests to the provider's base URL with ``Bearer`` authentication using
    ``ClientConfig.api_key``.
    """

    _provider_base_url: str = ""
    _provider_name: str = "openai_compatible"

    def __init__(self, config: ClientConfig) -> None:
        """Initialise the OpenAI-compatible client.

        Overrides the base URL used by the ``AsyncOpenAI`` client to point at
        the third-party provider's endpoint.

        Args:
            config: LLM configuration.  ``config.api_key`` must contain the
                provider's API key.  ``config.api_base``, when set, takes
                precedence over :attr:`_provider_base_url`.

        Raises:
            ImportError: If the ``openai`` package is not installed.
        """
        base_url = config.api_base or self._provider_base_url

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError(
                f"{type(self).__name__} requires the 'openai' package. "
                "Install with: pip install quadkit-ai-llm[openai]"
            ) from exc

        from quadkit.ai.llm.clients.base import AbstractLLMClient

        AbstractLLMClient.__init__(self, config=config)

        api_key = (
            config.api_key.get_secret_value()
            if config.api_key is not None
            else "sk-placeholder"
        )
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=config.timeout,
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Probe the provider's ``/models`` endpoint for connectivity.

        Args:
            timeout: Informational only; the SDK-level timeout governs the
                actual request duration.

        Returns:
            Structured :class:`~quadkit.contracts.core.health.HealthCheckResult`.
        """
        try:
            models = await self.client.models.list()
            first_model: str = models.data[0].id if models.data else ""
        except Exception as exc:  # noqa: BLE001 - transport/SDK errors are provider-specific
            return HealthCheckResult(
                component=f"llm.{self._provider_name}",
                status=HealthStatus.UNHEALTHY,
                error=f"Provider health check failed ({safe_error_type(exc)})",
            )

        return HealthCheckResult(
            component=f"llm.{self._provider_name}",
            status=HealthStatus.HEALTHY,
            details={"model": self.config.model, "probe_model": first_model},
        )


# ──────────────────────────────────────────────────────────────────────
# Concrete provider subclasses
# ──────────────────────────────────────────────────────────────────────


class DeepSeekClient(OpenAICompatibleClient):
    """LLM client for the DeepSeek API (OpenAI-compatible).

    Targets ``https://api.deepseek.com/v1``.  Authentication uses a Bearer
    token supplied as ``ClientConfig.api_key``.

    Supported models include ``deepseek-chat`` and ``deepseek-coder``.

    Example:
        >>> config = ClientConfig(
        ...     provider="deepseek",
        ...     model="deepseek-chat",
        ...     api_key=SecretStr("sk-..."),
        ... )
        >>> client = DeepSeekClient(config)
    """

    _provider_base_url = "https://api.deepseek.com/v1"
    _provider_name = "deepseek"


class TogetherClient(OpenAICompatibleClient):
    """LLM client for Together AI (OpenAI-compatible).

    Targets ``https://api.together.xyz/v1``.  Authentication uses a Bearer
    token supplied as ``ClientConfig.api_key``.

    Together AI hosts a large catalogue of open-source models; pass the full
    model path (e.g. ``meta-llama/Llama-3-8b-chat-hf``) as ``config.model``.

    Example:
        >>> config = ClientConfig(
        ...     provider="together",
        ...     model="meta-llama/Llama-3-8b-chat-hf",
        ...     api_key=SecretStr("tog-..."),
        ... )
        >>> client = TogetherClient(config)
    """

    _provider_base_url = "https://api.together.xyz/v1"
    _provider_name = "together"


class FireworksClient(OpenAICompatibleClient):
    """LLM client for Fireworks AI (OpenAI-compatible).

    Targets ``https://api.fireworks.ai/inference/v1``.  Authentication uses a
    Bearer token supplied as ``ClientConfig.api_key``.

    Pass model IDs in Fireworks format, e.g.
    ``accounts/fireworks/models/llama-v3-70b-instruct``.

    Example:
        >>> config = ClientConfig(
        ...     provider="fireworks",
        ...     model="accounts/fireworks/models/llama-v3-70b-instruct",
        ...     api_key=SecretStr("fw-..."),
        ... )
        >>> client = FireworksClient(config)
    """

    _provider_base_url = "https://api.fireworks.ai/inference/v1"
    _provider_name = "fireworks"
