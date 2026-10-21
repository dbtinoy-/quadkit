"""Registration-phase methods (backends, semantic cache, admin)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

# Import from root config.py - Single source of truth
from quadkit.cache.backends.registry import BackendRegistry
from quadkit.cache.config import (
    resolve_backend_type,
)
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.cache.service.core import CacheService
    from quadkit.contracts import ContainerRegistrarProtocol
    from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol

logger = get_logger(__name__)

T = TypeVar("T")


class _CacheRegistrationMixin:
    config: Any
    _initialize_serializers: Callable[..., None]
    get_backend: Callable[..., CacheBackendProtocol]
    get_default_service: Callable[..., CacheService]
    get_service: Callable[..., CacheService]
    _backends: dict[str, CacheBackendProtocol]
    """See :class:`CacheProvider`."""

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register cache services with the container.

        Only binds factories — no I/O.  All real initialization happens in boot().
        """
        logger.info("Registering Quadkit Cache services with container")

        # Register config so downstream providers (e.g. RatesProvider) can
        # resolve CacheConfig from the container.
        from quadkit.cache.config import CacheConfig  # noqa: PLC0415

        container.singleton(CacheConfig, self.config)

        # Register backend registry
        self._backend_registry = BackendRegistry.with_defaults()
        container.singleton(BackendRegistry, self._backend_registry)

        # Register CacheStatusRegistry in the container (D4.1).
        # Using the container-managed singleton eliminates the module-level
        # global accessor (get_cache_status_registry).  Code that already
        # resolves via the container will use this instance; legacy call-sites
        # that still call get_cache_status_registry() will get the same object
        # once we assign it below.
        from quadkit.cache.service.registry import (
            CacheStatusRegistry,
            reset_cache_status_registry,
        )

        self._status_registry = CacheStatusRegistry()
        container.singleton(CacheStatusRegistry, self._status_registry)
        # Back-fill the module-level singleton so legacy call-sites resolve to
        # the same instance without requiring a container reference.
        reset_cache_status_registry()
        import quadkit.cache.service.registry as _reg_mod

        _reg_mod._registry = self._status_registry

        # AsyncStringSerializerProtocol initialization is synchronous — safe here
        self._initialize_serializers()

        # Register provider and protocol (no I/O)
        from quadkit.cache.di.provider import (
            CacheProvider,  # noqa: PLC0415 — breaks provider<->mixin cycle
        )
        from quadkit.contracts.infra.cache.protocols import (
            CacheProviderProtocol,  # noqa: PLC0415
        )

        container.singleton(CacheProvider, self)
        container.singleton(CacheProviderProtocol, self)

        # Bind lazy factories that resolve after boot() populates self._backends / _services.
        # CacheBackendProtocol → the default backend (Result-based contract), symmetric
        # with the per-name bindings below.  CacheService → the ergonomic bare-value facade.
        from quadkit.cache.service.core import CacheService  # noqa: PLC0415
        from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol

        container.singleton(
            CacheBackendProtocol, factory=lambda: self.get_backend(None)
        )
        container.singleton(CacheService, factory=self.get_default_service)

        # Named bindings — one per configured, enabled backend
        if self.config:
            for backend_cfg in self.config.backends:
                if not backend_cfg.enabled:
                    continue
                _name = backend_cfg.name
                container.singleton(
                    CacheBackendProtocol,
                    factory=lambda n=_name: self.get_backend(n),
                    name=_name,
                )
                container.singleton(
                    CacheService,
                    factory=lambda n=_name: self.get_service(n),
                    name=_name,
                )
                logger.debug("registered_named_cache_binding", backend=_name)

        # Register the warming service so it can be resolved from the container (lazy)
        from quadkit.cache.service.warmer import CacheWarmer

        container.singleton(
            CacheWarmer,
            lambda: CacheWarmer(cache=self.get_default_service()._backend),  # type: ignore[arg-type]
        )

        # Register semantic cache if faiss is available
        self._register_semantic_cache(container)

        # Register a RedisStateStore for each Redis backend so that
        # create_backend() can resolve state_store.{name} during boot().
        if self.config:
            from quadkit.cache.stores.redis_state import (
                RedisStateStore,
            )
            from quadkit.cache.types import BackendType

            for backend_config in self.config.backends:
                if (
                    backend_config.enabled
                    and resolve_backend_type(backend_config) == BackendType.REDIS
                    and backend_config.redis_url
                ):
                    store = RedisStateStore(
                        url=backend_config.redis_url,
                        prefix=backend_config.key_prefix,
                    )
                    container.singleton(f"state_store.{backend_config.name}", store)
                    logger.debug(
                        "registered_redis_state_store", backend=backend_config.name
                    )

        await self._discover_backends(container)

        # Register admin widget components
        self._register_admin_components(container)

        logger.info("Quadkit Cache services registered successfully")

    async def _discover_backends(self, container: ContainerRegistrarProtocol) -> None:
        """Scan the ``quadkit.cache.backends`` entry-point group.

        Any entry point that resolves to a
        :class:`~quadkit.di.provider.Provider` subclass is instantiated
        and its :meth:`~quadkit.di.provider.Provider.register` method is
        called, allowing third-party backend packages to self-register.

        Args:
            container: The DI container registrar.
        """
        import importlib.metadata as _meta

        from quadkit.di.provider import Provider as _Provider

        eps = _meta.entry_points(group="quadkit.cache.backends")
        for ep in eps:
            try:
                candidate = ep.load()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "cache_ep_load_failed",
                    entry_point=ep.name,
                    error=str(exc),
                )
                continue
            if not (isinstance(candidate, type) and issubclass(candidate, _Provider)):
                logger.debug(
                    "cache_ep_skipped",
                    entry_point=ep.name,
                    reason="not a Provider subclass",
                )
                continue
            logger.debug(
                "cache_ep_found",
                entry_point=ep.name,
                provider=candidate.__name__,
            )
            try:
                await candidate().register(container)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "cache_ep_register_failed",
                    entry_point=ep.name,
                    provider=candidate.__name__,
                    error=str(exc),
                )

    def _register_semantic_cache(self, container: ContainerRegistrarProtocol) -> None:
        """Register semantic cache components if faiss is available.

        Conditionally registers SemanticCacheStore and its dependencies
        (VectorIndexProtocol, FaissVectorIndex) only if faiss package
        is installed and EmbeddingClientProtocol is registered. If faiss
        is not available or EmbeddingClientProtocol is missing, logs a
        debug message and skips registration.

        Args:
            container: The DI container registrar.
        """
        if not self._faiss_available():
            logger.debug("semantic_cache_skipped_faiss_not_available")
            return

        # Check if EmbeddingClientProtocol is registered
        try:
            from quadkit.contracts.ai.llm import EmbeddingClientProtocol

            if not container.has(EmbeddingClientProtocol):
                logger.debug(
                    "semantic_cache_skipped_no_embedding_client",
                    required_type="EmbeddingClientProtocol",
                )
                return
        except ImportError as exc:
            logger.warning(
                "semantic_cache_registration_failed_import",
                error=str(exc),
            )
            return

        try:
            from quadkit.cache.semantic.cost_decision import CostAwareCacheDecision
            from quadkit.cache.semantic.protocols import VectorIndexProtocol
            from quadkit.cache.semantic.store import SemanticCacheStore
            from quadkit.cache.semantic.vector_index import FaissVectorIndex
            from quadkit.contracts.ai.llm import SemanticCacheProtocol

            # Register vector index (internal protocol, package-local)
            container.singleton(VectorIndexProtocol, FaissVectorIndex)

            # Register cost decision helper
            container.singleton(CostAwareCacheDecision, CostAwareCacheDecision)

            # Register semantic cache store as singleton
            # Constructor injection will wire up the dependencies:
            # - CacheBackendProtocol (already registered above)
            # - EmbeddingClientProtocol (verified available above)
            # - VectorIndexProtocol (registered above)
            container.singleton(SemanticCacheProtocol, SemanticCacheStore)

            logger.debug("semantic_cache_registered")
        except ImportError as exc:
            logger.warning(
                "semantic_cache_registration_failed_import",
                error=str(exc),
            )

    @staticmethod
    def _faiss_available() -> bool:
        """Check if faiss package is installed.

        Returns:
            True if faiss can be imported, False otherwise.
        """
        try:
            import faiss  # type: ignore[import-not-found]  # noqa: F401

            return True
        except ImportError:
            return False

    def _register_admin_components(self, container: ContainerRegistrarProtocol) -> None:
        """Register admin contributor.

        Args:
            container: The DI container registrar.
        """
        from quadkit.cache.admin.contributor import CacheAdminContributor

        container.singleton(CacheAdminContributor, CacheAdminContributor)

        logger.debug("Registered cache admin widget components")


__all__ = ["_CacheRegistrationMixin"]
