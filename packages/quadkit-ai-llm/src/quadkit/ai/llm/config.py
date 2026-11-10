"""Configuration schema for the LLM package.

Defines LLMConfig, the typed configuration object accepted by LLMProvider
and all LLM client implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from quadkit.ai.llm.pinning import ModelPinPolicy
from quadkit.config.base import BaseConfig
from quadkit.contracts.ai.thinking import ThinkingConfig
from quadkit.contracts.ai.types import ModelProvider
from quadkit.contracts.core.config import Environment
from quadkit.domain import DomainModel
from quadkit.validation import ConfigDict, Field, SecretStr

if TYPE_CHECKING:
    from quadkit.ai.llm.pricing.sources import AbstractPricingSource


@dataclass(init=False)
class PricingSourceConfig(DomainModel):
    """A single pricing data source, configurable from YAML.

    Attributes:
        type: Source kind. One of ``"litellm"``, ``"openrouter"``, ``"json"``,
            or ``"static"``.
        endpoint: API endpoint URL. Used by ``litellm`` (defaults to the
            LiteLLM model cost map on GitHub) and ``openrouter`` (defaults to
            ``https://openrouter.ai/api/v1/models``).
        file_path: Path to a local pricing JSON file (``json`` type only).
        timeout: HTTP timeout in seconds for API sources.
        models: Inline static prices (``static`` type only). Maps a model
            name to ``{prompt_per_1m, completion_per_1m, provider?}``.

    Example:
        .. code-block:: yaml

            ai_llm:
              pricing:
                enabled: true
                sources:
                  - type: openrouter
                  - type: litellm
                  - type: json
                    file_path: pricing/custom.json
                  - type: static
                    models:
                      internal-model:
                        prompt_per_1m: 0.5
                        completion_per_1m: 1.5
                        provider: custom
    """

    type: str = Field(
        ...,
        description='Source kind: "litellm", "openrouter", "json", or "static".',
    )
    endpoint: str | None = Field(
        default=None,
        description="API endpoint URL (litellm/openrouter sources).",
    )
    file_path: str | None = Field(
        default=None,
        description="Path to a pricing JSON file (json source).",
    )
    timeout: float = Field(
        default=10.0,
        ge=1.0,
        description="HTTP timeout in seconds for API sources.",
    )
    models: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Inline prices per model (static source).",
    )


@dataclass(init=False)
class PricingConfig(DomainModel):
    """Pricing and cost-estimation configuration for the LLM subsystem.

    When attached to :class:`ClientConfig` (``ai_llm.pricing`` section in
    YAML), the LLM provider registers a ``CostEstimatorProtocol`` backed by
    a ``PricingManager`` over the configured sources.  Agents wired to the
    container then get real USD cost estimates per execution.

    Sources are queried in the configured order; the first source that knows
    a model wins.  When no sources are listed, defaults are used:
    OpenRouter (freshest prices for OpenAI/Anthropic/Google/Meta/Cohere/
    DeepSeek/xAI/Qwen) then the LiteLLM model cost map (covers the long
    tail including Groq and Mistral).

    Example:
        .. code-block:: yaml

            ai_llm:
              pricing:
                enabled: true
                cache_ttl: 43200
                enable_fuzzy_match: true
                sources:
                  - type: openrouter
                  - type: litellm
                  - type: json
                    file_path: pricing/private.json
                  - type: static
                    models:
                      my-internal-model:
                        prompt_per_1m: 0.25
                        completion_per_1m: 0.75
    """

    enabled: bool = Field(
        default=True,
        description="Register pricing manager and cost estimator.",
    )
    cache_ttl: int = Field(
        default=86400,
        ge=60,
        description="Pricing cache TTL in seconds (default: 24 hours).",
    )
    enable_fuzzy_match: bool = Field(
        default=True,
        description="Allow substring matching of model names to prices.",
    )
    sources: list[PricingSourceConfig] = Field(
        default_factory=list,
        description="Pricing sources in priority order.",
    )

    def build_sources(self) -> list[AbstractPricingSource]:
        """Build pricing source instances from this config.

        Returns:
            Configured ``AbstractPricingSource`` instances in priority
            order.  Empty sources list yields the defaults (OpenRouter
            then LiteLLM).

        Raises:
            ValueError: On unknown source type or a ``json`` source
                without ``file_path``.
        """
        from quadkit.ai.llm.pricing.pricing_source_registry import (
            PricingSourceRegistry,
        )
        from quadkit.ai.llm.pricing.sources import (
            APIPricingSource,
            OpenRouterPricingSource,
        )

        litellm_url = (
            "https://raw.githubusercontent.com/BerriAI/litellm/main/"
            "model_prices_and_context_window.json"
        )

        if not self.sources:
            return [
                OpenRouterPricingSource(),
                APIPricingSource(litellm_url),
            ]

        registry = PricingSourceRegistry.with_defaults()
        return [registry.create_source(cfg) for cfg in self.sources]


@dataclass(init=False)
class ClientConfig(BaseConfig):
    """Configuration for LLM clients.

    Example:
        >>> config = ClientConfig(
        ...     provider="openai",
        ...     model="gpt-4-turbo",
        ...     api_key="sk-...",
        ...     temperature=0.7,
        ...     max_tokens=2000,
        ... )
    """

    config_section: ClassVar[str] = "ai_llm"

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="ignore",
        arbitrary_types_allowed=True,
    )

    enabled: bool = Field(default=True, description="Enable the LLM subsystem")
    name: str = "ai_llm"
    env: Environment | None = Field(None, description="Deployment environment")

    provider: ModelProvider = Field(
        default=ModelProvider.OPENAI,
        description="LLM provider name.",
    )
    model: str = Field(default="gpt-4-turbo", description="Model name or identifier.")
    model_revision: str | None = Field(
        default=None,
        description="Pinned model revision (provider-specific, e.g. date or version string).",
    )
    pin_policy: ModelPinPolicy = Field(
        default=ModelPinPolicy.LATEST,
        description="Policy for enforcing the model revision pin.",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description="API key for the chosen provider.",
    )
    api_base: str | None = Field(
        default=None,
        description="Custom API base URL (for Azure, local, or proxied endpoints).",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature.",
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        description="Maximum tokens in response.",
    )
    timeout: float = Field(
        default=60.0,
        ge=1.0,
        description="Request timeout in seconds.",
    )
    enable_cache: bool = Field(
        default=False,
        description="Enable response caching (requires CacheBackendProtocol in container).",
    )
    cache_ttl: int = Field(
        default=3600,
        description="Cache TTL in seconds.",
    )
    thinking: ThinkingConfig | None = Field(
        default=None,
        description=(
            "Thinking/reasoning configuration.  ``None`` disables thinking. "
            "Set to a ``ThinkingConfig`` instance to enable provider-appropriate "
            "reasoning output (Anthropic extended thinking, Gemini thinking, "
            "OpenAI reasoning effort, Bedrock Claude reasoning, OpenRouter reasoning)."
        ),
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific extra parameters passed verbatim.",
    )
    pricing: PricingConfig | None = Field(
        default=None,
        description=(
            "Pricing source configuration. When set, registers a pricing "
            "manager and a CostEstimatorProtocol in the container so agents "
            "get USD cost estimates. See PricingConfig for the YAML schema."
        ),
    )

    def __post_init__(self) -> None:
        """Coerce provider string to ModelProvider enum and api_key to SecretStr."""
        if isinstance(self.provider, str):
            self.provider = ModelProvider(self.provider)
        api_key: Any = self.api_key
        if api_key is not None and not isinstance(api_key, SecretStr):
            self.api_key = SecretStr(api_key)


__all__ = ["ClientConfig", "PricingConfig", "PricingSourceConfig"]
