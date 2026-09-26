"""Sub-provider for ProjectionManager and SagaManagerProtocol (M-01)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerRegistrarProtocol
    from quadkit.events.config import EventsConfig


class ManagerSubProvider:
    """Focused sub-provider: creates and owns ProjectionManager and SagaManagerProtocol.

    Example::

        sub = ManagerSubProvider(config, event_store=store)
        await sub.setup()
        projections = sub.projection_manager
    """

    def __init__(
        self,
        config: EventsConfig,
        event_store: Any = None,
    ) -> None:
        self._config = config
        self._event_store = event_store
        self.projection_manager: Any = None
        self.saga_manager: Any = None

    async def setup(self, container: ContainerRegistrarProtocol | None = None) -> None:
        """Instantiate managers."""
        from quadkit.events.projections import ProjectionManager

        self.projection_manager = ProjectionManager(event_store=self._event_store)

        # SagaManagerProtocol is part of the same package; import directly
        from quadkit.events.sagas import SagaManagerProtocol, SagaStore

        # Prefer a container-registered SagaStore over the in-memory default
        saga_store: SagaStore | None = None
        if (
            container is not None
            and hasattr(container, "has")
            and hasattr(container, "resolve")
        ):
            try:
                if container.has(SagaStore):
                    import asyncio

                    resolve_coro = container.resolve(SagaStore)
                    if asyncio.iscoroutine(resolve_coro):
                        saga_store = await resolve_coro
                    else:
                        saga_store = resolve_coro
            except (LookupError, RuntimeError, AttributeError, TypeError) as exc:
                logger.debug("events.saga_store_not_registered", reason=str(exc))

        self.saga_manager = SagaManagerProtocol(store=saga_store)

    async def boot(self) -> None:
        """Start managers that expose a start() method."""
        if self.projection_manager and hasattr(self.projection_manager, "start"):
            await self.projection_manager.start()

    async def teardown(self) -> None:
        """Stop managers on shutdown."""
        if self.projection_manager and hasattr(self.projection_manager, "stop"):
            await self.projection_manager.stop()

    def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register managers into the DI container."""
        from typing import cast

        from quadkit.events.projections import ProjectionManager

        if self.projection_manager:
            container.singleton(cast("Any", ProjectionManager), self.projection_manager)

        if self.saga_manager:
            from quadkit.events.sagas import SagaManagerProtocol

            container.singleton(cast("Any", SagaManagerProtocol), self.saga_manager)


__all__ = ["ManagerSubProvider"]
