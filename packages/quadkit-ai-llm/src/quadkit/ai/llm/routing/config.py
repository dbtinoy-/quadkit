"""Configuration schema for LLM multi-provider routing.

Defines all typed configuration objects accepted by ``LLMRoutingProvider``
and ``LLMRouter``. Use ``LLMConfig.from_env()`` to build from environment
variables following the ``QK_AI_LLM__`` prefix convention.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import ClassVar, Literal

from quadkit.config.base import BaseConfig
from quadkit.validation import ConfigDict, Field, SecretStr

__all__ = [
    "GenerationDefaults",
    "LLMConfig",
    "LogConfig",
    "ProviderConfig",
    "QuotaConfig",
]

_ENV = "QK_AI_LLM__"


@dataclass(init=False)
class GenerationDefaults(BaseConfig):
    """Default generation parameters applied to every routing attempt.

    Example:
        >>> defaults = GenerationDefaults(temperature=0.3, max_tokens=2048)
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Default sampling temperature.",
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        description="Default maximum output tokens (None = provider default).",
    )


@dataclass(init=False)
class QuotaConfig(BaseConfig):
    """Configuration for the quota tracking backend.

    Example:
        >>> cfg = QuotaConfig(backend="database")
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    backend: Literal["memory", "database"] = Field(
        default="memory",
        description="Backend type: ``memory`` or ``database``.",
    )
    cooldown_seconds: int = Field(
        default=300,
        ge=1,
        description=(
            "Cooldown applied to a cascade entry after an HTTP 429. "
            "Env var: QK_AI_LLM__QUOTA__COOLDOWN_SECONDS."
        ),
    )


@dataclass(init=False)
class LogConfig(BaseConfig):
    """Configuration for inference attempt logging.

    Example:
        >>> cfg = LogConfig(backend="database", max_entries=5000)
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    backend: Literal["memory", "database"] = Field(
        default="memory",
        description="Backend type: ``memory`` or ``database``.",
    )
    max_entries: int = Field(
        default=1000,
        ge=1,
        description="Maximum in-memory log entries before FIFO eviction.",
    )
    store_content: bool = Field(
        default=False,
        description=(
            "Persist generated completion text in database logs. Disabled by default "
            "because completions can contain sensitive user or pet-health data."
        ),
    )


@dataclass(init=False)
class ProviderConfig(BaseConfig):
    """Configuration for a single provider in the routing cascade.

    Every provider in the cascade has the same shape regardless of type.
    Provider-specific fields (Azure deployment, Cloudflare account ID,
    Bedrock region, Vertex project) go in ``extras``.

    Example:
        >>> cfg = ProviderConfig(
        ...     name="groq",
        ...     model="llama-3.3-70b-versatile",
        ...     api_key="gsk_...",
        ... )
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        arbitrary_types_allowed=True, extra="ignore"
    )

    name: str = Field(description="Provider name (must match ProviderRegistry key).")
    model: str = Field(description="Primary model identifier.")
    api_key: SecretStr | None = Field(
        default=None,
        description="API key for key-authenticated providers.",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL override (local providers, Azure, custom endpoints).",
    )
    timeout: int = Field(
        default=30,
        ge=5,
        description="Per-request timeout in seconds.",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this provider participates in routing.",
    )
    suppress_thinking: bool = Field(
        default=False,
        description=(
            "When True, the LLM client actively disables thinking/chain-of-thought "
            "token generation by injecting ``enable_thinking: false`` into the request "
            "payload.  Use for models that think by default (Qwen3, Gemma-4 via LM Studio "
            "/ vLLM / SGLang) to eliminate the 20-30 s latency overhead.  "
            "Env var: ``QK_AI_LLM__PROVIDERS__{NAME}__SUPPRESS_THINKING=true``."
        ),
    )
    extras: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Provider-specific credential fields: "
            "azure_resource, azure_deployment, azure_api_version; "
            "cf_account_id, cf_api_token; "
            "aws_region, aws_access_key_id, aws_secret_access_key; "
            "vertex_project, vertex_location, vertex_credentials_file."
        ),
    )

    @property
    def key(self) -> str:
        """Unique cascade-entry identity: provider name + model.

        Multiple entries may share ``name`` (e.g. several OpenRouter models);
        quota, clients, and routing state must key on this, never on ``name``.
        """
        return f"{self.name}:{self.model}"


@dataclass(init=False)
class LLMConfig(BaseConfig):
    """Root configuration object for the LLM routing system.

    All providers are opt-in: a provider joins the cascade only when its
    credential environment variable is set.  Use :meth:`from_env` to build
    from ``QK_AI_LLM__`` environment variables.

    Example::

        config = LLMConfig(
            providers=[
                ProviderConfig(name="groq", model="llama-3.3-70b-versatile", api_key="gsk_..."),
                ProviderConfig(name="gemini", model="gemini-2.5-flash", api_key="AIza..."),
            ],
            defaults=GenerationDefaults(temperature=0.3),
        )

    Environment variables (prefix ``QK_AI_LLM__``)::

        Global:

            QK_AI_LLM__STRATEGY              sequential | parallel_race |
                                                   cost_optimized | latency_optimized
            QK_AI_LLM__DEFAULTS__TEMPERATURE float  (default 0.2)
            QK_AI_LLM__DEFAULTS__MAX_TOKENS  int    (default: provider default)
            QK_AI_LLM__QUOTA__BACKEND        memory | database  (default memory)
            QK_AI_LLM__LOG__BACKEND          memory | database  (default memory)
            QK_AI_LLM__LOG__MAX_ENTRIES      int    (default 1000)

        Per-provider (pattern: QK_AI_LLM__PROVIDERS__{NAME}__{FIELD}):

            __{NAME}__API_KEY    str   API key -- activates key-auth providers
            __{NAME}__BASE_URL   str   Endpoint -- activates local/custom providers
            __{NAME}__MODEL      str   Model override (has per-provider defaults)
            __{NAME}__TIMEOUT    int   Request timeout in seconds (default 30)
            __{NAME}__ENABLED    bool  Explicit enable/disable (default true)

        Supported provider names and their activation:

            OPENAI       API_KEY required   default model: gpt-4o
            ANTHROPIC    API_KEY required   default model: claude-3-5-sonnet-20241022
            GROQ         API_KEY required   default model: llama-3.3-70b-versatile
            GEMINI       API_KEY required   default model: gemini-2.5-flash
            MISTRAL      API_KEY required   default model: mistral-large-latest
            COHERE       API_KEY required   default model: command-r-plus
            OPENROUTER   API_KEY required   default model: openai/gpt-4o-mini
            DEEPSEEK     API_KEY required   default model: deepseek-chat
            TOGETHER     API_KEY required   default model: meta-llama/Llama-3-8b-chat-hf
            FIREWORKS    API_KEY required   default model: accounts/fireworks/models/llama-v3-70b-instruct
            OLLAMA       BASE_URL required  default model: llama3.2  (default base: http://localhost:11434)
            OPENAI_COMPATIBLE  BASE_URL + MODEL required  (generic OpenAI-compatible: LM Studio, VLLM, etc.)

        Azure-specific extras (activated by AZURE__API_KEY + AZURE__BASE_URL):

            QK_AI_LLM__PROVIDERS__AZURE__EXTRAS__AZURE_RESOURCE
            QK_AI_LLM__PROVIDERS__AZURE__EXTRAS__AZURE_DEPLOYMENT
            QK_AI_LLM__PROVIDERS__AZURE__EXTRAS__AZURE_API_VERSION

        Cloudflare-specific extras (activated by CLOUDFLARE__EXTRAS__CF_ACCOUNT_ID):

            QK_AI_LLM__PROVIDERS__CLOUDFLARE__EXTRAS__CF_ACCOUNT_ID  <- activates
            QK_AI_LLM__PROVIDERS__CLOUDFLARE__EXTRAS__CF_API_TOKEN
            QK_AI_LLM__PROVIDERS__CLOUDFLARE__MODEL

        AWS Bedrock extras (activated by BEDROCK__EXTRAS__AWS_REGION):

            QK_AI_LLM__PROVIDERS__BEDROCK__EXTRAS__AWS_REGION        <- activates
            QK_AI_LLM__PROVIDERS__BEDROCK__MODEL
            QK_AI_LLM__PROVIDERS__BEDROCK__EXTRAS__AWS_ACCESS_KEY_ID
            QK_AI_LLM__PROVIDERS__BEDROCK__EXTRAS__AWS_SECRET_ACCESS_KEY

        Google Vertex AI extras (activated by VERTEX__EXTRAS__VERTEX_PROJECT):

            QK_AI_LLM__PROVIDERS__VERTEX__EXTRAS__VERTEX_PROJECT      <- activates
            QK_AI_LLM__PROVIDERS__VERTEX__EXTRAS__VERTEX_LOCATION
            QK_AI_LLM__PROVIDERS__VERTEX__MODEL
            QK_AI_LLM__PROVIDERS__VERTEX__EXTRAS__VERTEX_CREDENTIALS_FILE
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    providers: list[ProviderConfig] = Field(
        default_factory=list,
        description="Ordered list of providers (cascade order). First = highest priority.",
    )
    defaults: GenerationDefaults = Field(
        default_factory=GenerationDefaults,
        description="Default generation parameters.",
    )
    quota: QuotaConfig = Field(
        default_factory=QuotaConfig,
        description="Quota backend configuration.",
    )
    logging: LogConfig = Field(
        default_factory=LogConfig,
        description="Inference logger configuration.",
    )
    strategy: Literal[
        "sequential",
        "parallel_race",
        "cost_optimized",
        "latency_optimized",
    ] = Field(
        default="sequential",
        description=(
            "Routing strategy. "
            "``sequential``: try providers in cascade order. "
            "``parallel_race``: fire all in parallel, take the first success. "
            "``cost_optimized``: cheapest providers first. "
            "``latency_optimized``: fastest recent provider first."
        ),
    )

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Build a routing config from ``QK_AI_LLM__`` environment variables.

        Returns:
            Populated :class:`LLMConfig`.
        """

        def _str(key: str, default: str = "") -> str:
            return os.environ.get(key, default).strip()

        def _int(key: str, default: int) -> int:
            raw = _str(key)
            return int(raw) if raw else default

        def _bool(key: str, default: bool = True) -> bool:
            raw = _str(key).lower()
            if raw in ("false", "0", "no"):
                return False
            if raw in ("true", "1", "yes"):
                return True
            return default

        def _secret(key: str) -> SecretStr | None:
            val = _str(key)
            return SecretStr(val) if val else None

        def _p(name: str, fld: str) -> str:
            """Build provider env var key."""
            return f"{_ENV}PROVIDERS__{name}__{fld}"

        def _extras(name: str, key: str) -> str:
            return _str(f"{_ENV}PROVIDERS__{name}__EXTRAS__{key}")

        providers: list[ProviderConfig] = []

        # Key-auth cloud providers
        _KEY_PROVIDERS: list[tuple[str, str]] = [
            ("OPENAI", "gpt-4o"),
            ("ANTHROPIC", "claude-3-5-sonnet-20241022"),
            ("GROQ", "llama-3.3-70b-versatile"),
            ("GEMINI", "gemini-2.5-flash"),
            ("MISTRAL", "mistral-large-latest"),
            ("COHERE", "command-r-plus"),
            ("OPENROUTER", "openai/gpt-4o-mini"),
            ("DEEPSEEK", "deepseek-chat"),
            ("TOGETHER", "meta-llama/Llama-3-8b-chat-hf"),
            ("FIREWORKS", "accounts/fireworks/models/llama-v3-70b-instruct"),
        ]
        for name, default_model in _KEY_PROVIDERS:
            key = _secret(_p(name, "API_KEY"))
            if not key:
                continue
            providers.append(
                ProviderConfig(
                    name=name.lower(),
                    model=_str(_p(name, "MODEL"), default_model),
                    api_key=key,
                    base_url=_str(_p(name, "BASE_URL")) or None,
                    timeout=_int(_p(name, "TIMEOUT"), 30),
                    enabled=_bool(_p(name, "ENABLED")),
                    suppress_thinking=_bool(
                        _p(name, "SUPPRESS_THINKING"), default=False
                    ),
                )
            )

        # Azure OpenAI (key-auth + extras)
        azure_key = _secret(_p("AZURE", "API_KEY"))
        azure_base = _str(_p("AZURE", "BASE_URL"))
        if azure_key and azure_base:
            providers.append(
                ProviderConfig(
                    name="azure",
                    model=_str(_p("AZURE", "MODEL"), "gpt-4o"),
                    api_key=azure_key,
                    base_url=azure_base,
                    timeout=_int(_p("AZURE", "TIMEOUT"), 30),
                    enabled=_bool(_p("AZURE", "ENABLED")),
                    extras={
                        k: v
                        for k, v in {
                            "azure_resource": _extras("AZURE", "AZURE_RESOURCE"),
                            "azure_deployment": _extras("AZURE", "AZURE_DEPLOYMENT"),
                            "azure_api_version": _extras("AZURE", "AZURE_API_VERSION"),
                        }.items()
                        if v
                    },
                )
            )

        # Cloudflare Workers AI
        cf_account = _extras("CLOUDFLARE", "CF_ACCOUNT_ID")
        cf_token = _extras("CLOUDFLARE", "CF_API_TOKEN")
        if cf_account and cf_token:
            providers.append(
                ProviderConfig(
                    name="cloudflare",
                    model=_str(
                        _p("CLOUDFLARE", "MODEL"), "@cf/meta/llama-3.1-8b-instruct"
                    ),
                    timeout=_int(_p("CLOUDFLARE", "TIMEOUT"), 30),
                    enabled=_bool(_p("CLOUDFLARE", "ENABLED")),
                    extras={"cf_account_id": cf_account, "cf_api_token": cf_token},
                )
            )

        # AWS Bedrock
        bedrock_region = _extras("BEDROCK", "AWS_REGION")
        if bedrock_region:
            extras: dict[str, str] = {"aws_region": bedrock_region}
            for k in (
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN",
                "AWS_PROFILE",
            ):
                val = _extras("BEDROCK", k)
                if val:
                    extras[k.lower()] = val
            providers.append(
                ProviderConfig(
                    name="bedrock",
                    model=_str(
                        _p("BEDROCK", "MODEL"), "anthropic.claude-3-haiku-20240307-v1:0"
                    ),
                    timeout=_int(_p("BEDROCK", "TIMEOUT"), 60),
                    enabled=_bool(_p("BEDROCK", "ENABLED")),
                    extras=extras,
                )
            )

        # Google Vertex AI
        vertex_project = _extras("VERTEX", "VERTEX_PROJECT")
        if vertex_project:
            vextras: dict[str, str] = {"vertex_project": vertex_project}
            for k in ("VERTEX_LOCATION", "VERTEX_CREDENTIALS_FILE"):
                val = _extras("VERTEX", k)
                if val:
                    vextras[k.lower()] = val
            providers.append(
                ProviderConfig(
                    name="vertex",
                    model=_str(_p("VERTEX", "MODEL"), "gemini-1.5-pro"),
                    timeout=_int(_p("VERTEX", "TIMEOUT"), 60),
                    enabled=_bool(_p("VERTEX", "ENABLED")),
                    extras=vextras,
                )
            )

        # Ollama
        ollama_base = _str(_p("OLLAMA", "BASE_URL"))
        if ollama_base:
            providers.append(
                ProviderConfig(
                    name="ollama",
                    model=_str(_p("OLLAMA", "MODEL"), "llama3.2"),
                    base_url=ollama_base,
                    timeout=_int(_p("OLLAMA", "TIMEOUT"), 120),
                    enabled=_bool(_p("OLLAMA", "ENABLED")),
                    suppress_thinking=_bool(
                        _p("OLLAMA", "SUPPRESS_THINKING"), default=False
                    ),
                )
            )

        # Generic OpenAI-compatible server (LM Studio, vLLM, etc.)
        openai_compatible_base = _str(_p("OPENAI_COMPATIBLE", "BASE_URL"))
        openai_compatible_model = _str(_p("OPENAI_COMPATIBLE", "MODEL"))
        if openai_compatible_base and openai_compatible_model:
            providers.append(
                ProviderConfig(
                    name="openai_compatible",
                    model=openai_compatible_model,
                    api_key=_secret(_p("OPENAI_COMPATIBLE", "API_KEY")),
                    base_url=openai_compatible_base,
                    timeout=_int(_p("OPENAI_COMPATIBLE", "TIMEOUT"), 120),
                    enabled=_bool(_p("OPENAI_COMPATIBLE", "ENABLED")),
                    suppress_thinking=_bool(
                        _p("OPENAI_COMPATIBLE", "SUPPRESS_THINKING"), default=False
                    ),
                )
            )

        # Global settings
        temperature_raw = _str(f"{_ENV}DEFAULTS__TEMPERATURE", "0.2")
        max_tokens_raw = _str(f"{_ENV}DEFAULTS__MAX_TOKENS")

        return cls(
            providers=providers,
            defaults=GenerationDefaults(
                temperature=float(temperature_raw),
                max_tokens=int(max_tokens_raw) if max_tokens_raw else None,
            ),
            quota=QuotaConfig(
                backend=_str(f"{_ENV}QUOTA__BACKEND", "memory"),
            ),
            logging=LogConfig(
                backend=_str(f"{_ENV}LOG__BACKEND", "memory"),
                max_entries=_int(f"{_ENV}LOG__MAX_ENTRIES", 1000),
                store_content=_bool(f"{_ENV}LOG__STORE_CONTENT", default=False),
            ),
            strategy=_str(f"{_ENV}STRATEGY", "sequential") or "sequential",
        )
