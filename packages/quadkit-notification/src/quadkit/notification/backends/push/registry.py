"""Push backend registry — registry-based dispatch of push notification backends."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

PushBackendBuilder = Callable[..., Any]


class PushBackendRegistry:
    """Registry of push-backend builders, keyed by driver name.

    Each driver name maps to a sync builder that constructs the
    corresponding push provider from a NamedPushConfig entry.

    Usage::

        registry = PushBackendRegistry.with_defaults()
        backend = registry.create_backend("fcm", entry)
    """

    def __init__(self) -> None:
        """Initialise an empty backend registry."""
        self._builders: dict[str, PushBackendBuilder] = {}

    @classmethod
    def with_defaults(cls) -> PushBackendRegistry:
        """Return a registry populated with the built-in push backends.

        Returns:
            A :class:`PushBackendRegistry` pre-registered for fcm, apns,
            and web_push.
        """
        registry = cls()

        def _fcm(entry: Any) -> Any:
            from quadkit.notification.backends.push.fcm import FCMPush
            from quadkit.notification.config import FCMDriverConfig

            if FCMPush is None:
                raise ImportError("FCMPush unavailable")
            cfg = entry.fcm or FCMDriverConfig()
            server_key = (
                cfg.server_key.get_secret_value()
                if hasattr(cfg.server_key, "get_secret_value")
                and cfg.server_key is not None
                else (cfg.server_key or "")
            )
            return FCMPush(server_key=server_key or "", timeout=cfg.timeout)

        def _apns(entry: Any) -> Any:
            from quadkit.notification.backends.push.apns import APNsPush
            from quadkit.notification.config import APNsDriverConfig

            if APNsPush is None:
                raise ImportError(
                    "APNsPush unavailable — install quadkit-notification[apns]"
                )
            cfg = entry.apns or APNsDriverConfig()
            return APNsPush(
                team_id=cfg.team_id or "",
                key_id=cfg.key_id or "",
                apns_auth_key=(
                    cfg.apns_auth_key.get_secret_value()
                    if hasattr(cfg.apns_auth_key, "get_secret_value")
                    and cfg.apns_auth_key is not None
                    else str(cfg.apns_auth_key or "")
                ),
                bundle_id=cfg.bundle_id or "",
                sandbox=cfg.sandbox,
                timeout=cfg.timeout,
            )

        def _web_push(entry: Any) -> Any:
            from quadkit.notification.backends.push.web_push import WebPushChannel
            from quadkit.notification.config import WebPushDriverConfig

            if WebPushChannel is None:
                raise ImportError(
                    "WebPushChannel unavailable — install quadkit-notification[web-push]"
                )
            cfg = entry.web_push or WebPushDriverConfig()
            return WebPushChannel(
                vapid_private_key=getattr(
                    cfg.vapid_private_key,
                    "get_secret_value",
                    lambda: cfg.vapid_private_key,  # type: ignore[arg-type]
                )(),
                vapid_public_key=cfg.vapid_public_key or "",
                vapid_claims_subject=cfg.vapid_claims_subject or "",
                http_timeout=cfg.timeout,
            )

        registry.register("fcm", _fcm)
        registry.register("apns", _apns)
        registry.register("web_push", _web_push)
        return registry

    def register(self, driver: str, builder: PushBackendBuilder) -> None:
        """Register a builder under a driver name.

        Args:
            driver: Driver name (e.g. ``"fcm"``).
            builder: Callable ``(entry) -> PushChannelProtocol``.
        """
        self._builders[driver] = builder

    def create_backend(self, driver: str, entry: Any) -> Any:
        """Build a push provider for a driver name.

        Args:
            driver: Driver name to dispatch on.
            entry: Named push configuration entry.

        Returns:
            An instantiated push provider.

        Raises:
            ValueError: If *driver* is not registered.
        """
        builder = self._builders.get(driver)
        if builder is None:
            raise ValueError(f"Unsupported push driver: {driver!r}")
        return builder(entry)

    def drivers(self) -> list[str]:
        """Return the registered driver names.

        Returns:
            List of driver names in registration order.
        """
        return list(self._builders.keys())

    def __contains__(self, driver: str) -> bool:
        return driver in self._builders


__all__ = ["PushBackendBuilder", "PushBackendRegistry"]
