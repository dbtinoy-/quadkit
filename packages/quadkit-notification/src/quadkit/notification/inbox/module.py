"""InboxModule — IoC module for user-facing inbox notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.notification.inbox import InboxStoreProtocol
from quadkit.di.module import DynamicModule, Module, module
from quadkit.notification.inbox.service import InboxService

if TYPE_CHECKING:
    from quadkit.notification.config import InboxConfig


@module(is_global=True)
class InboxModule(Module):
    """In-app notification inbox integration.

    Registers :class:`~quadkit.contracts.notification.inbox.InboxStoreProtocol`
    and :class:`~quadkit.notification.inbox.service.InboxService` for
    constructor injection, so an application's own writers (an announcement
    job, an alert evaluator) and its read API share one store instead of each
    keeping a private notifications table.

    Usage::

        from quadkit.notification.config import InboxConfig
        from quadkit.notification.inbox.module import InboxModule

        @module(imports=[InboxModule.configure(InboxConfig(max_page_size=50))])
        class AppModule(Module):
            pass

    The default ``database`` backend requires a bound
    ``DatabaseProviderProtocol`` and fails if it is missing. Explicitly choose
    ``InboxConfig(store_backend="memory")`` or :meth:`stub` for volatile
    in-process storage. This module supplies no request authentication or
    authorization; application adapters must enforce those boundaries.
    """

    @classmethod
    def configure(cls, config: InboxConfig | Any | None = None) -> DynamicModule:
        """Create an InboxModule with explicit configuration.

        Args:
            config: :class:`~quadkit.notification.config.InboxConfig` or
                ``None`` to use the framework defaults.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.notification.di.inbox_provider import InboxProvider

        return DynamicModule(
            module=cls,
            providers=[InboxProvider(config=config)],
            exports=[InboxService, InboxStoreProtocol],
        )

    @classmethod
    def stub(cls, config: Any = None) -> DynamicModule:
        """Return an InboxModule for unit tests — messages never persist.

        Args:
            config: Accepted to match :meth:`Module.stub`; deliberately not
                applied. A stub that could be handed a persistent backend would
                stop being a stub, so the in-memory store is forced.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor backed by
            the in-memory store.
        """
        from quadkit.notification.config import InboxConfig as _InboxConfig
        from quadkit.notification.di.inbox_provider import InboxProvider

        return DynamicModule(
            module=cls,
            providers=[InboxProvider(config=_InboxConfig(store_backend="memory"))],
            exports=[InboxService, InboxStoreProtocol],
        )


__all__ = ["InboxModule"]
