"""DI provider for quadkit-notification."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.contracts.notification.protocols import (
    PushChannelProtocol,
    SMSChannelProtocol,
)
from quadkit.di.provider import Provider
from quadkit.logging import get_logger
from quadkit.notification.backends.push.registry import PushBackendRegistry
from quadkit.notification.config import (
    NamedPushConfig,
    NamedSMSConfig,
    NotificationConfig,
    TwilioDriverConfig,
)

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)

try:
    from quadkit.notification.backends.sms.twilio import TwilioSMS
except ImportError:
    TwilioSMS = None  # type: ignore[assignment,misc]


class NotificationProvider(Provider):
    """Register SMS and push notification services into the DI container.

    Reads :class:`~quadkit.notification.config.NotificationConfig`, creates
    the appropriate backends, and registers them as ``SMSChannelProtocol`` and
    ``PushChannelProtocol``.

    Supports multi-backend (``NotificationConfig.sms_backends`` and
    ``NotificationConfig.push_backends``) mode. Each entry is registered under
    its name via ``container.singleton(name=entry.name)``. The primary backend
    (``primary=True`` or the first entry) also receives the unnamed bindings
    for backward compatibility.

    Dual-mode configuration: an explicit ``config`` wins; otherwise the
    typed ``notification`` yaml section injected by the orchestrator (via
    ``config_key``) is used; otherwise defaults apply.
    """

    name = "notification"
    priority = ProviderPriority.INFRASTRUCTURE
    config_key: str | None = "notification"
    config_model: type | None = NotificationConfig

    def __init__(
        self,
        config: NotificationConfig | None = None,
        *,
        push_registry: PushBackendRegistry | None = None,
    ) -> None:
        super().__init__()
        self._requested_config = config
        self._config: NotificationConfig | None = config
        self._push_registry = push_registry or PushBackendRegistry.with_defaults()
        self._sms_services: list[tuple[str, Any]] = []
        self._push_services: list[tuple[str, Any]] = []

    @classmethod
    def from_config(
        cls, config: NotificationConfig, **context: Any
    ) -> NotificationProvider:
        """Factory method for DI container setup."""
        return cls(config)

    def _create_sms(self, entry: NamedSMSConfig) -> Any:
        """Instantiate the correct SMS implementation for a config."""
        if entry.driver == "twilio":
            if TwilioSMS is None:
                raise ImportError("TwilioSMS unavailable")
            cfg = entry.twilio or TwilioDriverConfig()
            token = (
                cfg.auth_token.get_secret_value()
                if hasattr(cfg.auth_token, "get_secret_value")
                and cfg.auth_token is not None
                else (cfg.auth_token or "")
            )
            return TwilioSMS(
                account_sid=cfg.account_sid or "",
                auth_token=token or "",
                from_number=cfg.from_number,
                timeout=cfg.timeout,
            )
        raise ValueError(f"Unsupported SMS driver: {entry.driver!r}")

    def _create_push(self, entry: NamedPushConfig) -> Any:
        """Instantiate the correct push implementation for a config."""
        return self._push_registry.create_backend(entry.driver, entry)

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind all SMS and push backends into the container."""
        injected = self.config if isinstance(self.config, NotificationConfig) else None
        cfg = self._requested_config or injected or NotificationConfig()
        self._config = cfg
        container.singleton(NotificationConfig, cfg)

        for sms_entry in cfg.sms_backends:
            backend = self._create_sms(sms_entry)
            self._sms_services.append((sms_entry.name, backend))
            container.singleton(
                SMSChannelProtocol,
                factory=lambda *_, b=backend: b,
                name=sms_entry.name,
            )
            is_primary = sms_entry.primary or (
                not any(e.primary for e in cfg.sms_backends)
                and cfg.sms_backends[0] is sms_entry
            )
            if is_primary:
                container.singleton(SMSChannelProtocol, factory=lambda *_, b=backend: b)

        for push_entry in cfg.push_backends:
            backend = self._create_push(push_entry)
            self._push_services.append((push_entry.name, backend))
            container.singleton(
                PushChannelProtocol,
                factory=lambda *_, b=backend: b,
                name=push_entry.name,
            )
            is_primary = push_entry.primary or (
                not any(e.primary for e in cfg.push_backends)
                and cfg.push_backends[0] is push_entry
            )
            if is_primary:
                container.singleton(
                    PushChannelProtocol, factory=lambda *_, b=backend: b
                )

        logger.info(
            "notification_registered",
            sms=[n for n, _ in self._sms_services],
            push=[n for n, _ in self._push_services],
        )

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Health-check all backends; log warnings for degraded ones."""
        all_services = self._sms_services + self._push_services
        if not all_services:
            return
        results = await asyncio.gather(
            *[svc.health_check() for _, svc in all_services],
            return_exceptions=True,
        )
        for (name, _), result in zip(all_services, results, strict=True):
            if isinstance(result, Exception):
                logger.warning(
                    "notification_boot_unhealthy", backend=name, error=str(result)
                )

    async def shutdown(self) -> None:
        """Shutdown in reverse registration order."""
        for name, _ in reversed(self._push_services + self._sms_services):
            logger.info("notification_shutdown", backend=name)
        self._sms_services.clear()
        self._push_services.clear()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Aggregate health across all registered notification backends."""
        all_services = self._sms_services + self._push_services
        if not all_services:
            return HealthCheckResult(
                component="notification",
                status=HealthStatus.HEALTHY,
                details={"backends": []},
            )

        results = await asyncio.gather(
            *[svc.health_check() for _, svc in all_services],
            return_exceptions=True,
        )
        worst = HealthStatus.HEALTHY
        details: dict[str, Any] = {}
        for (name, _), result in zip(all_services, results, strict=True):
            if isinstance(result, Exception):
                worst = HealthStatus.UNHEALTHY
                details[name] = {"status": "error", "error": str(result)}
            elif isinstance(result, HealthCheckResult):
                details[name] = {"status": result.status.value}
                if result.status == HealthStatus.UNHEALTHY:
                    worst = HealthStatus.UNHEALTHY
                elif (
                    result.status == HealthStatus.DEGRADED
                    and worst == HealthStatus.HEALTHY
                ):
                    worst = HealthStatus.DEGRADED

        return HealthCheckResult(
            component="notification", status=worst, details=details
        )


__all__ = ["NotificationProvider"]
