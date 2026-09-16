"""Provider types for Quadkit Framework."""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )


class ProviderPriority(IntEnum):
    """Provider initialization priority.

    Providers are booted in ascending order of priority.  Lower values run
    first; the typical ordering is:

    * ``CRITICAL`` (0) – absolutely foundational services that others depend on
      (e.g. configuration, diagnostics).
    * ``INFRASTRUCTURE`` (10) – low-level plumbing such as database connections,
      messaging clients, and cache providers.
    * ``SECURITY`` (20) – authentication/authorization infrastructure.
    * ``NORMAL`` (30) – everyday domain services with no special ordering.
    * ``APPLICATION`` (40) – application-level tools (CLI, admin utilities)
      that depend on domain services but are not themselves domain logic.
    * ``DOMAIN`` (50) – business-logic providers that may depend on earlier
      layers.
    * ``PRESENTATION`` (80) – web/API layers and other entry points.
    * ``COMMS`` (90) – outbound communication providers (email, SMS, webhooks)
      often run late to avoid interfering with core initialization.
    * ``LOW`` (100) – lowest-priority, optional providers that can boot last.
    """

    CRITICAL = 0
    INFRASTRUCTURE = 10
    SECURITY = 20
    NORMAL = 30
    APPLICATION = 40
    DOMAIN = 50
    PRESENTATION = 80
    COMMS = 90
    LOW = 100


@runtime_checkable
class ProviderProtocol(Protocol):
    """Contract for framework providers.

    Providers are responsible for:
    - Registering bindings into the container (register phase)
    - Initializing external resources (boot phase)
    - Cleaning up resources on shutdown (shutdown phase)

    Expected Behavior:
    - register: MUST be declarative. No external side effects or resolution.
    - boot: CAN resolve services. MUST be idempotent if called twice.
    - shutdown: MUST gracefully close resources. SHOULD NOT raise.
    """

    @property
    def name(self) -> str:
        """Unique provider identifier (e.g. 'auth', 'database')."""
        ...

    @property
    def priority(self) -> ProviderPriority:
        """Initialization order hint."""
        ...

    @property
    def dependencies(self) -> Sequence[str]:
        """Names of providers that must be booted before this one."""
        ...

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind services into the container. declarative phase."""
        ...

    async def boot(self, container: BootContainerProtocol) -> None:
        """Initialize and wire services. Resolution and registration allowed here."""
        ...

    async def shutdown(self) -> None:
        """Tear down resources on application exit."""
        ...

    async def on_error(self, error: Exception, phase: str) -> None:
        """Called when boot() or shutdown() raises an exception.

        Override to perform cleanup on startup/shutdown failure.

        Args:
            error: The exception that was raised.
            phase: Either 'boot' or 'shutdown'.
        """
        ...


class Lifecycle(StrEnum):
    """Provider lifecycle stages."""

    REGISTER = "register"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"


__all__ = ["Lifecycle", "ProviderPriority", "ProviderProtocol"]
