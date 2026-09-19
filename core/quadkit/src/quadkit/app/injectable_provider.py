"""Internal provider that auto-registers @injectable / @singleton decorated classes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.provider import Provider, ProviderPriority

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerRegistrarProtocol


class InjectableAutoProvider(Provider):
    """Synthetic provider that registers auto-discovered injectable classes.

    Created internally by :meth:`Application.discover_providers` and by the
    module scan mechanism (``@module(scan=[...])``).
    """

    def __init__(self, injectables: list[tuple[type, Any]]) -> None:
        super().__init__(name="_injectable_auto", priority=ProviderPriority.NORMAL)
        self._injectables = injectables

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register each discovered injectable class into the container."""
        for cls, scope in self._injectables:
            if scope == ServiceScope.SINGLETON:
                container.singleton(cls, cls)
            elif scope == ServiceScope.SCOPED:
                container.scoped(cls, cls)
            else:
                container.transient(cls, cls)


__all__ = ["InjectableAutoProvider"]
