"""LLM Provider for Quadkit Framework dependency injection.

Registers all LLM-layer services (clients, cache, model manager) with
the container so they can be injected throughout the application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from quadkit.ai.llm.exceptions import LLMError
from quadkit.contracts.ai import LLMClientProtocol
from quadkit.contracts.ai.providers import ProviderRegistryProtocol
from quadkit.contracts.core.health import HealthCheckResult
from quadkit.di.decorators import inject
from quadkit.di.provider import Provider, ProviderPriority
from quadkit.logging import get_logger, safe_error_type

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )
    from quadkit.contracts.infra.cache import CacheBackendProtocol

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.di.factories import create_llm_cache, create_llm_client
from quadkit.ai.llm.model_manager import LLMModelManager
from quadkit.ai.llm.registry.core import ProviderRegistry

logger = get_logger(__name__)

__all__ = ["LLMProvider"]


@inject
class LLMProvider(Provider):
    """Provider that registers LLM services with the Quadkit DI container.

    Registers an LLMClientProtocol, optional LLM response cache, and an LLMModelManager
    so all three are injectable throughout the application.

    Example:
        >>> from quadkit.ai.llm.di.provider import LLMProvider
        >>> from quadkit.ai.llm.config import ClientConfig
        >>>
        >>> app.use(LLMProvider(ClientConfig(provider="openai", model="gpt-4o")))
        >>>
        >>> # LLMClientProtocol is now injectable:
        >>> class MyService:
        ...     def __init__(self, llm: LLMClientProtocol) -> None:
        ...         self.llm = llm
    """

    name = "llm"
    priority = ProviderPriority.DOMAIN
    config_key: str | None = "ai_llm"
    config_model: type | None = ClientConfig

    def __init__(
        self,
        config: ClientConfig | None = None,
        enable_model_manager: bool = False,
        enable_streaming: bool = True,
        audit_calls: bool = False,
        name: str = "llm",
        cache_backend: CacheBackendProtocol | None = None,
        stub_mode: bool = False,
    ) -> None:
        """Initialize the LLM Provider.

        Args:
            config: LLM client configuration; defaults to ClientConfig() (reads env).
            enable_model_manager: Register LLMModelManager for local model control.
            enable_streaming: Enable streaming response support.
            audit_calls: Register :class:`~quadkit.ai.llm.audit_bridge.LLMAuditBridge`
                to emit audit entries per completion.
            name: Provider name used for identification.
            cache_backend: Injected cache backend for optional response caching.
        """
        super().__init__(name=name)
        self._requested_config = config
        self.config = config or ClientConfig()
        self.enable_model_manager = enable_model_manager
        self.enable_streaming = enable_streaming
        self.audit_calls = audit_calls
        self.cache_backend = cache_backend
        self.stub_mode = stub_mode
        self._llm_client: LLMClientProtocol | None = None
        self._cache_deferred = False
        self._cache_wrapper: LLMClientProtocol | None = None

    @property
    def llm_client(self) -> LLMClientProtocol | None:
        """The constructed LLM client (optional wrapper chain).

        ``None`` until :meth:`register` has built the client (or when the
        provider runs in a mode that registers no client). Consumers that
        need the client — e.g. the ``the optional provider`` orchestrator — should use
        this accessor rather than reaching into the private attribute.
        """
        return self._llm_client

    @staticmethod
    def _instructor_available() -> bool:
        """Check if the instructor library is available."""
        import importlib.util

        try:
            return importlib.util.find_spec("instructor") is not None
        except (ValueError, AttributeError):
            return False

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register LLM services with the DI container.

        Args:
            container: The Quadkit DI container registrar.
        """
        from quadkit.ai.llm.pricing.registry import TokenCounterRegistry
        from quadkit.contracts.ai.llm import TokenCounterProtocol

        self.config = self._requested_config or self.config
        container.singleton(ClientConfig, self.config)

        if not self.config.enabled:
            logger.info("llm_disabled", reason="ClientConfig.enabled=False")
            return

        logger.info("llm_services_registration_started")

        registry = ProviderRegistry.with_defaults()
        container.singleton(ProviderRegistry, registry)
        container.singleton(ProviderRegistryProtocol, registry)

        # Register TokenCounterRegistry
        token_registry = TokenCounterRegistry.with_defaults()
        container.singleton(TokenCounterRegistry, token_registry)

        # Register ParserRegistry with default parsers
        from quadkit.ai.llm.parsers.registry import ParserRegistry

        parser_registry = ParserRegistry.with_defaults()
        container.singleton(ParserRegistry, parser_registry)
        logger.info("Registered ParserRegistry with default parsers")

        llm_client: LLMClientProtocol
        try:
            if self.stub_mode:
                from quadkit.ai.llm.clients.noop import NoOpLLMClient

                llm_client = cast("LLMClientProtocol", NoOpLLMClient(self.config))
            else:
                llm_client = await create_llm_client(self.config, registry)
        except (ImportError, LLMError) as exc:
            logger.warning(
                "llm_client_skipped",
                error_type=safe_error_type(exc),
            )
            return

        # Always enrich completions with provenance (provider, model_revision,
        # prompt_hash) — innermost wrap so downstream layers see fully-populated
        # Completion objects.  LXF-003 wiring.
        from quadkit.ai.llm.wrappers import CompletionEnricher, LLMCacheWrapper

        llm_client = CompletionEnricher.wrap(
            llm_client,
            provider=self.config.provider,
            model=self.config.model,
            model_revision=getattr(self.config, "model_revision", None),
        )

        container.singleton(LLMClientProtocol, llm_client)
        container.singleton("llm", llm_client)
        self._llm_client = llm_client
        logger.info("llm_client_registered")

        if self.config.enable_cache:
            if self.cache_backend is not None:
                llm_cache = await create_llm_cache(self.config, self.cache_backend)
                container.singleton("llm_cache", llm_cache)
                logger.info("Registered LLM response cache")
            else:
                # Defer to boot(): the orchestrator registers sub-providers
                # before the container is booted (and frozen), so the
                # platform cache backend is not resolvable yet. The wrapper
                # is registered against a pass-through cache and receives
                # the real backend-backed cache in boot().
                from quadkit.ai.llm.caching.core import NoOpLLMCache

                llm_cache = NoOpLLMCache()
                container.singleton("llm_cache", llm_cache)
                self._cache_deferred = True
                logger.info(
                    "LLM response cache deferred: backend will be bound at boot"
                )

        if self.enable_model_manager:
            container.singleton(LLMModelManager)
            container.singleton("llm_model_manager", LLMModelManager)
            logger.info("Registered LLMModelManager")

        if self.audit_calls:
            from quadkit.ai.llm.audit_bridge import LLMAuditBridge

            container.singleton(LLMAuditBridge)
            wrapped_client = LLMAuditBridge.wrap(llm_client, container)
            container.singleton(LLMClientProtocol, wrapped_client)
            container.singleton("llm", wrapped_client)
            self._llm_client = wrapped_client
            llm_client = wrapped_client  # subsequent wraps build on this
            logger.info("Registered LLMAuditBridge (audit_calls=True)")

        # Cache wrap sits outermost: cache hits short-circuit before audit
        # fires (no real LLM call happened, so no audit entry).  LXF-003 wiring
        # — actually invokes build_llm_cache_key in production paths.
        if self.config.enable_cache:
            cache_wrapped = LLMCacheWrapper.wrap(
                llm_client,
                cache=llm_cache,
                provider=self.config.provider,
                model=self.config.model,
                model_revision=getattr(self.config, "model_revision", None),
                ttl_seconds=getattr(self.config, "cache_ttl", None),
            )
            container.singleton(LLMClientProtocol, cache_wrapped)
            container.singleton("llm", cache_wrapped)
            self._llm_client = cache_wrapped
            self._cache_wrapper = cache_wrapped
            logger.info("Registered LLMCacheWrapper (cache hits skip audit)")

        # Register default TokenCounterProtocol
        default_counter = token_registry.for_model(self.config.model or "gpt-3.5-turbo")
        container.singleton(TokenCounterProtocol, default_counter)

        # Register pricing manager + cost estimator when pricing is configured
        if self.config.pricing and self.config.pricing.enabled:
            from quadkit.ai.llm.pricing.estimator import PricingCostEstimator
            from quadkit.ai.llm.pricing.manager import PricingManager
            from quadkit.contracts.ai.llm import CostEstimatorProtocol

            pricing_manager = PricingManager(
                sources=self.config.pricing.build_sources(),
                cache_ttl=self.config.pricing.cache_ttl,
                enable_fuzzy_match=self.config.pricing.enable_fuzzy_match,
            )
            container.singleton(PricingManager, pricing_manager)
            container.singleton(
                CostEstimatorProtocol,
                PricingCostEstimator(
                    {},
                    enable_fuzzy_match=self.config.pricing.enable_fuzzy_match,
                ),
            )
            logger.info(
                "Registered pricing manager and cost estimator",
                sources=[s.source_name for s in pricing_manager.sources],
            )

        # Register InstructorExtractor if instructor is available
        if self._instructor_available():
            from quadkit.ai.llm.extraction.extractor import InstructorExtractor

            container.singleton(InstructorExtractor, InstructorExtractor)
            logger.info("Registered InstructorExtractor")

        logger.info("LLM services registered")

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Boot the LLM provider — validates API key presence and format.

        Args:
            container: The DI container resolver.
        """
        from quadkit.contracts.ai.types import ModelProvider

        # Bind the deferred cache backend (registered at register() before
        # the container was booted, so the platform cache backend was not
        # resolvable yet). The container is frozen at this point, so the
        # wrapper's backing cache is swapped in place instead of
        # re-registering the binding.
        if self._cache_deferred and self._cache_wrapper is not None:
            from quadkit.ai.llm.wrappers import LLMCacheWrapper
            from quadkit.contracts.infra.cache import CacheBackendProtocol

            backend = await container.resolve_optional(CacheBackendProtocol)
            if backend is None:
                msg = (
                    "LLM response caching is enabled (llm.enable_cache=True) "
                    "but no CacheBackendProtocol is available in the container. "
                    "Enable the cache package or a compatible backend provider."
                )
                raise ValueError(msg)
            llm_cache = await create_llm_cache(self.config, backend)
            LLMCacheWrapper.bind_cache(self._cache_wrapper, llm_cache)
            self.cache_backend = backend
            self._cache_deferred = False
            logger.info(
                "LLM response cache bound at boot",
                backend=type(backend).__name__,
            )

        # Providers that require an API key
        _REQUIRES_KEY: set[str] = {
            ModelProvider.OPENAI,
            ModelProvider.ANTHROPIC,
            ModelProvider.COHERE,
            ModelProvider.GROQ,
            ModelProvider.MISTRAL,
            ModelProvider.OPENROUTER,
            ModelProvider.GEMINI,
            ModelProvider.CLOUDFLARE,
            ModelProvider.AZURE_OPENAI,
            ModelProvider.DEEPSEEK,
            ModelProvider.TOGETHER,
            ModelProvider.FIREWORKS,
        }

        provider = str(self.config.provider)
        if provider in _REQUIRES_KEY:
            if not self.config.api_key:
                logger.warning(
                    "llm_provider_boot_warning",
                    reason="API key is not set; requests will likely fail with AuthenticationError",
                )
            else:
                key_val = self.config.api_key.get_secret_value()
                if len(key_val) < 8:
                    logger.warning(
                        "llm_provider_boot_warning",
                        reason="API key appears too short; verify the key is correct",
                    )

        # Warm the cost estimator pricing snapshot from configured sources
        if self.config.pricing and self.config.pricing.enabled:
            try:
                from quadkit.ai.llm.pricing.estimator import PricingCostEstimator
                from quadkit.ai.llm.pricing.manager import PricingManager
                from quadkit.contracts.ai.llm import CostEstimatorProtocol

                manager = await container.resolve(PricingManager)
                estimator = await container.resolve(CostEstimatorProtocol)
                await cast("PricingCostEstimator", estimator).warm(manager)
            except Exception as e:  # noqa: BLE001 — pricing preload is best-effort
                logger.warning(
                    "pricing_preload_failed",
                    error_type=safe_error_type(e),
                    reason="cost estimates will return 0.0 until sources are reachable",
                )

        # Optional: register this client in the provider registry
        if self._llm_client is not None:
            try:
                from quadkit.contracts.ai.providers import ProviderRegistryProtocol

                registry = await container.resolve(ProviderRegistryProtocol)
                await registry.register_provider(
                    name=str(self.config.provider),
                    client=self._llm_client,
                    models=[],
                )
                logger.debug("llm_registered_in_provider_registry")
            except Exception:  # noqa: BLE001 — provider registry registration is best-effort
                logger.debug("llm_provider_registry_not_available")

    async def shutdown(self) -> None:
        """Close client connections on application shutdown."""
        if self._llm_client and hasattr(self._llm_client, "close"):
            try:
                await self._llm_client.close()
            except Exception as exc:  # noqa: BLE001 — client close is best-effort — shutdown must not raise
                logger.warning(
                    "Error closing LLM client",
                    error_type=type(exc).__name__,
                )
        self._llm_client = None
        logger.info("LLM provider shutdown complete")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return basic health information for the registered LLM client."""
        from quadkit.contracts.core.health import HealthCheckResult, HealthStatus

        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY
            if self._llm_client is not None
            else HealthStatus.DEGRADED,
            details={
                "provider": str(self.config.provider),
                "model": self.config.model,
            },
        )
