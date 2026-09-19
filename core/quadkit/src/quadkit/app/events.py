"""Application lifecycle events published through the EventBusProtocol.

These events allow plugins, middleware, and application code to hook
into the application lifecycle without coupling to the ``Application``
class directly.

Example::

    from quadkit.app.events import ApplicationStarted
    from quadkit.logging import get_logger

    logger = get_logger(__name__)

    async def on_started(event: ApplicationStarted) -> None:
        logger.info(
            "application_started",
            app_name=event.app_name,
        )

    bus.subscribe(ApplicationStarted, on_started)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ApplicationStarting:
    """Emitted when the application begins its start sequence.

    Fired before providers are booted, allowing early subscribers
    to perform pre-boot setup.

    Attributes:
        app_name: The application name.
    """

    app_name: str


@dataclass(frozen=True)
class ApplicationStarted:
    """Emitted after all providers have been booted and the application is running.

    Attributes:
        app_name: The application name.
    """

    app_name: str


@dataclass(frozen=True)
class ApplicationStopping:
    """Emitted when the application begins its shutdown sequence.

    Fired before providers are shut down.

    Attributes:
        app_name: The application name.
    """

    app_name: str


@dataclass(frozen=True)
class ApplicationStopped:
    """Emitted after all providers have been shut down.

    Attributes:
        app_name: The application name.
        uptime_seconds: Total time the application was running, in seconds.
    """

    app_name: str
    uptime_seconds: float


@dataclass(frozen=True)
class ProviderRegistered:
    """Emitted when a provider is added to the application.

    Attributes:
        provider_name: The name of the registered provider.
    """

    provider_name: str


@dataclass(frozen=True)
class ProviderBooted:
    """Emitted after a individual provider finishes booting.

    Attributes:
        provider_name: The name of the booted provider.
        duration_ms: Time taken to boot, in milliseconds.
    """

    provider_name: str
    duration_ms: float


@dataclass(frozen=True)
class HealthCheckCompleted:
    """Emitted after a health check cycle completes.

    Attributes:
        status: Overall health status string.
        details: Detailed health information per component.
    """

    status: str
    details: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ApplicationStarted",
    "ApplicationStarting",
    "ApplicationStopped",
    "ApplicationStopping",
    "HealthCheckCompleted",
    "ProviderBooted",
    "ProviderRegistered",
]
