"""Storage module for dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts import BlobStoreProtocol
from quadkit.di.module import DynamicModule, Module, module

if TYPE_CHECKING:
    from quadkit.storage.config import StorageConfig


@module()
class StorageModule(Module):
    """Object storage backend (S3, GCS, Azure, R2, local filesystem).

    Registers :class:`~quadkit.contracts.BlobStoreProtocol` for constructor
    injection.

    Call :meth:`configure` to configure and register a storage driver,
    or :meth:`stub` for an isolated in-memory setup with no external
    service dependencies.

    Usage::

        from quadkit.storage.config import StorageConfig

        @module(
            imports=[StorageModule.configure(StorageConfig(default_driver="s3"))]
        )
        class AppModule(Module):
            pass
    """

    @classmethod
    def configure(
        cls,
        config: StorageConfig | Any | None = None,
        enable_encryption: bool = False,
    ) -> DynamicModule:
        """Create a StorageModule with explicit configuration.

        Args:
            config: :class:`~quadkit.storage.config.StorageConfig` or ``None``
                to resolve config from the container at boot time.
            enable_encryption: Enable server-side encryption for all stored
                objects.  Defaults to ``False``; configure encryption keys via
                :class:`~quadkit.storage.config.EncryptionConfig`.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.

        Raises:
            TypeError: If *config* is not a ``StorageConfig`` or ``None``.
        """
        from quadkit.storage.config import StorageConfig
        from quadkit.storage.di.provider import StorageProvider

        if config is not None and not isinstance(config, StorageConfig):
            raise TypeError(
                f"config must be StorageConfig, got {type(config).__name__}"
            )

        return DynamicModule(
            module=cls,
            providers=[StorageProvider(config=config)],
            exports=[BlobStoreProtocol],
        )

    @classmethod
    def stub(cls, config: StorageConfig | None = None) -> DynamicModule:
        """Create a StorageModule suitable for unit and integration testing.

        Uses an in-memory backend with no external service dependencies.

        Args:
            config: Optional :class:`~quadkit.storage.config.StorageConfig`
                override.  Uses safe in-memory defaults when ``None``.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.storage.config import StorageConfig
        from quadkit.storage.di.provider import StorageProvider

        if config is None:
            config = StorageConfig(default_driver="memory")

        return DynamicModule(
            module=cls,
            providers=[StorageProvider(config=config)],
            exports=[BlobStoreProtocol],
        )


__all__ = ["StorageModule"]
