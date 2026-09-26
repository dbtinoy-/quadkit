"""Serializer/backend/service construction and lookup."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from quadkit.cache.service.core import CacheService
    from quadkit.contracts import CacheBackendProtocol

# Import from root config.py - Single source of truth
from quadkit.cache.config import (
    CacheBackendConfig,
    resolve_backend_type,
)
from quadkit.contracts.core import (
    HookRegistryProtocol,
)
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts import ContainerResolverProtocol

logger = get_logger(__name__)

T = TypeVar("T")


class _CacheServicesMixin:
    config: Any
    _backends: dict[str, CacheBackendProtocol]
    _protection: Any
    _services: dict[str, CacheService]
    """See :class:`CacheProvider`."""

    def _initialize_serializers(self) -> None:
        """Initialize available serializers.

        Note:
            Domain-model reconstruction for ``@cacheable`` envelopes is
            gated by ``DEFAULT_REGISTRY``
            (``quadkit.cache.serialization.type_registry``): the
            ``TypeRegistry()`` instance is the single
            registration surface — deny-by-default. The cache package
            defines no model types itself, so nothing is registered here;
            consumers register their domain models at boot via
            ``DEFAULT_REGISTRY.register(ModelClass)``.
        """
        from quadkit.cache.serialization.factory import create_serializers

        self._serializers = create_serializers()
        logger.debug("Initialized serializers: %s", list(self._serializers.keys()))

    async def _initialize_backends(
        self, container: ContainerResolverProtocol | None = None
    ) -> None:
        """Initialize configured cache backends."""
        if not self.config:
            logger.warning("No configuration provided for cache provider")
            return

        for backend_config in self.config.backends:
            if not backend_config.enabled:
                logger.debug("Skipping disabled backend: %s", backend_config.name)
                continue

            try:
                backend = await self._create_backend(backend_config, container)
                self._backends[backend_config.name] = backend
                logger.info(
                    "Initialized backend: %s (%s)",
                    backend_config.name,
                    resolve_backend_type(backend_config),
                )
            except Exception as e:
                logger.exception("Failed to initialize backend %s", backend_config.name)
                if backend_config.default:
                    raise RuntimeError(
                        f"Failed to initialize default backend: {backend_config.name}",
                    ) from e

    async def _create_backend(
        self,
        config: CacheBackendConfig,
        container: ContainerResolverProtocol | None = None,
    ) -> CacheBackendProtocol:
        """Create a backend instance from configuration."""
        from quadkit.cache.backends.factory import create_backend

        hooks = None
        if container is not None:
            resolve_optional = getattr(container, "resolve_optional", None)
            if callable(resolve_optional):
                maybe_hooks = resolve_optional(HookRegistryProtocol)
                hooks = (
                    await maybe_hooks
                    if inspect.isawaitable(maybe_hooks)
                    else maybe_hooks
                )

        return await create_backend(config, container, hooks=hooks)

    def _initialize_services(self) -> None:
        """Initialize cache services for each backend."""
        from quadkit.cache.service.factory import create_service

        if not self.config:
            return

        for backend_name, backend in self._backends.items():
            try:
                service = create_service(self, backend_name, backend, self._protection)
                self._services[backend_name] = service
                logger.info("Initialized cache service for backend: %s", backend_name)
            except Exception:  # noqa: BLE001 — one failing service must not stop initialization of the rest
                logger.exception(
                    "Failed to initialize service for backend %s", backend_name
                )

    def _create_service(
        self,
        backend_name: str,
        backend: CacheBackendProtocol,
    ) -> CacheService:
        """Create a cache service for a backend."""
        if not self.config:
            raise RuntimeError("Provider not configured")

        from quadkit.cache.service.core import CacheService

        return CacheService(
            provider=self,  # type: ignore[arg-type]
            protection=self._protection,
        )

    def get_service(self, backend_name: str | None = None) -> CacheService:
        """
        Get a cache service by backend name.

        Args:
            backend_name: Name of the backend, uses default if None

        Returns:
            CacheService instance

        Raises:
            ValueError: If backend not found
        """
        if backend_name is None and self.config:
            backend_name = self.config.service.default_backend
            if backend_name is None:
                # Find default backend
                default_config = self.config.get_default_backend()
                if default_config:
                    backend_name = default_config.name

        if backend_name not in self._services:
            available = list(self._services.keys())
            raise ValueError(
                f"Cache service '{backend_name}' not found. Available: {available}",
            )

        return self._services[backend_name]

    def get_backend(self, backend_name: str | None = None) -> Any:
        """
        Get a backend instance by name.

        Args:
            backend_name: Name of the backend, uses default if None

        Returns:
            Backend instance

        Raises:
            ValueError: If backend not found
        """
        if backend_name is None and self.config:
            backend_name = self.config.service.default_backend
            if backend_name is None:
                # Find default backend
                default_config = self.config.get_default_backend()
                if default_config:
                    backend_name = default_config.name

        if backend_name not in self._backends:
            available = list(self._backends.keys())
            raise ValueError(
                f"Backend '{backend_name}' not found. Available: {available}",
            )

        return self._backends[backend_name]

    def get_default_service(self) -> CacheService:
        """
        Get the default cache service.

        Returns:
            Default CacheService instance
        """
        return self.get_service()
