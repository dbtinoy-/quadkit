"""MailerModule — IoC module for email delivery."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.mailer.protocols import MailerProtocol
from quadkit.contracts.notification.delivery import DeliveryStoreProtocol
from quadkit.di.module import DynamicModule, Module, module

if TYPE_CHECKING:
    from quadkit.notification.config import MailerConfig


@module(is_global=True)
class MailerModule(Module):
    """Email delivery integration with Named DI multi-backend support.

    Registers :class:`~quadkit.contracts.mailer.protocols.MailerProtocol` for
    constructor injection, supporting SMTP and SendGrid backends.

    Usage::

        from quadkit.notification.config import MailerConfig, NamedMailerConfig
        from quadkit.notification.mailer.module import MailerModule

        @module(
            imports=[
                MailerModule.configure(
                    MailerConfig(
                        backends=[
                            NamedMailerConfig(
                                name="transactional",
                                primary=True,
                                driver="sendgrid",
                            )
                        ]
                    )
                )
            ]
        )
        class AppModule(Module):
            pass

    Named injection::

        class MyService:
            def __init__(
                self,
                mailer: MailerProtocol,                                          # primary
                bulk: Annotated[MailerProtocol, Named("bulk")],                  # named
            ) -> None: ...
    """

    @classmethod
    def configure(cls, config: MailerConfig | Any | None = None) -> DynamicModule:
        """Create a MailerModule with explicit configuration.

        Args:
            config: :class:`~quadkit.notification.config.MailerConfig` or ``None``
                to use defaults (no backends).

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.notification.di.mailer_provider import MailerProvider
        from quadkit.notification.mailer.runtime import MailerDeliveryRuntime

        exports: list[type] = [MailerProtocol, DeliveryStoreProtocol]
        if (
            config is None
            or bool(getattr(config, "backends", []))
            or bool(getattr(config, "console_fallback", False))
        ):
            exports.append(MailerDeliveryRuntime)
        return DynamicModule(
            module=cls,
            providers=[MailerProvider(config=config)],
            exports=exports,
        )

    @classmethod
    def stub(cls, config: MailerConfig | Any | None = None) -> DynamicModule:
        """Return a MailerModule for unit tests — no emails sent.

        Uses an empty config (no backends configured) so all mail operations
        are dropped and no external services are contacted.

        Args:
            config: Optional :class:`~quadkit.notification.config.MailerConfig`
                for test scenarios that need specific stubs.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.notification.config import MailerConfig as _MailerConfig
        from quadkit.notification.di.mailer_provider import MailerProvider

        stub_config = config or _MailerConfig()
        if not stub_config.backends:
            stub_config.console_fallback = False
        return DynamicModule(
            module=cls,
            providers=[MailerProvider(config=stub_config)],
            exports=[MailerProtocol],
        )


__all__ = ["MailerModule"]
