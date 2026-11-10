"""Mailer backend registry — registry-based dispatch of mailer backends."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

MailerBackendBuilder = Callable[..., Any]


class MailerBackendRegistry:
    """Registry of mailer-backend builders, keyed by driver name.

    Each driver name maps to a sync builder that constructs the
    corresponding mailer from its named config entry.

    Usage::

        registry = MailerBackendRegistry.with_defaults()
        mailer = registry.create_backend("smtp", entry)
    """

    def __init__(self) -> None:
        """Initialise an empty backend registry."""
        self._builders: dict[str, MailerBackendBuilder] = {}

    @classmethod
    def with_defaults(cls) -> MailerBackendRegistry:
        """Return a registry populated with the built-in mailer backends.

        Returns:
            A :class:`MailerBackendRegistry` pre-registered for smtp,
            sendgrid, and console.
        """
        registry = cls()

        def _smtp(entry: Any) -> Any:
            from quadkit.notification.config import SMTPDriverConfig
            from quadkit.notification.mailer.smtp_mailer import SMTPMailer

            cfg = entry.smtp or SMTPDriverConfig()
            password: Any | None = None
            if cfg.password:
                password = getattr(
                    cfg.password, "get_secret_value", lambda: cfg.password or ""
                )()
            return SMTPMailer(
                host=cfg.host,
                port=cfg.port,
                username=cfg.username,
                password=password,
                use_tls=cfg.use_tls,
                use_ssl=cfg.use_ssl,
                timeout=cfg.timeout,
                from_email=entry.from_email,
            )

        def _sendgrid(entry: Any) -> Any:
            from quadkit.notification.config import SendGridDriverConfig
            from quadkit.notification.mailer.sendgrid_mailer import SendGridMailer

            cfg_sg = entry.sendgrid or SendGridDriverConfig()
            api_key: Any = ""
            if cfg_sg.api_key:
                api_key = (
                    getattr(
                        cfg_sg.api_key, "get_secret_value", lambda: cfg_sg.api_key or ""
                    )()
                    or ""
                )
            return SendGridMailer(
                api_key=api_key,
                timeout=cfg_sg.timeout,
                sandbox_mode=cfg_sg.sandbox_mode,
                from_email=entry.from_email,
            )

        def _console(entry: Any) -> Any:
            from quadkit.notification.mailer.console_mailer import ConsoleMailer

            return ConsoleMailer()

        registry.register("smtp", _smtp)
        registry.register("sendgrid", _sendgrid)
        registry.register("console", _console)
        return registry

    def register(self, driver: str, builder: MailerBackendBuilder) -> None:
        """Register a builder under a driver name.

        Args:
            driver: Driver name (e.g. ``"smtp"``).
            builder: Callable ``(entry) -> MailerProtocol``.
        """
        self._builders[driver] = builder

    def create_backend(self, driver: str, entry: Any) -> Any:
        """Build a mailer for a driver name.

        Args:
            driver: Driver name to dispatch on.
            entry: Named mailer configuration entry.

        Returns:
            An instantiated mailer.

        Raises:
            ValueError: If *driver* is not registered.
        """
        builder = self._builders.get(driver)
        if builder is None:
            raise ValueError(f"Unsupported mailer driver: {driver!r}")
        return builder(entry)

    def drivers(self) -> list[str]:
        """Return the registered driver names.

        Returns:
            List of driver names in registration order.
        """
        return list(self._builders.keys())

    def __contains__(self, driver: str) -> bool:
        return driver in self._builders


__all__ = ["MailerBackendBuilder", "MailerBackendRegistry"]
