"""Tests for MailerProvider's retry wiring (`MailerConfig.retry_max_attempts`).

`retry_max_attempts`/`retry_base_delay` were configuration the framework never
read: the fields existed, `RetryingMailer` existed, and nothing joined them. The
provider now wraps its *primary* binding, resolving the delivery store from the
container at first use — `SqlDeliveryStore` when the app binds a database
provider, `MemoryDeliveryStore` otherwise. Named bindings stay unwrapped.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
from quadkit.contracts.mailer.protocols import MailerProtocol
from quadkit.notification.config import (
    MailerConfig,
    NamedMailerConfig,
    SMTPDriverConfig,
)
from quadkit.notification.delivery.stores import MemoryDeliveryStore, SqlDeliveryStore
from quadkit.notification.di.mailer_provider import MailerProvider
from quadkit.notification.mailer.retrying_mailer import RetryingMailer


class _Registrar:
    """Minimal registrar double recording singleton bindings."""

    def __init__(self) -> None:
        self.entries: list[tuple[Any, Any, Any]] = []

    def singleton(
        self, service_type: Any, factory: Any = None, *, name: Any = None
    ) -> None:
        self.entries.append((service_type, factory, name))

    def binding(self, *, name: Any = None) -> Any:
        """Return the recorded factory for ``MailerProtocol`` under ``name``."""
        for service_type, factory, entry_name in self.entries:
            if service_type is MailerProtocol and entry_name == name:
                return factory
        raise AssertionError(f"no MailerProtocol binding for name={name!r}")


class _Resolver:
    """Minimal resolver double with an optional database provider."""

    def __init__(self, db: Any = None) -> None:
        self._db = db

    def has(self, service_type: Any) -> bool:
        return service_type is DatabaseProviderProtocol and self._db is not None

    def can_resolve(self, service_type: Any) -> bool:
        return self.has(service_type)

    async def resolve(self, service_type: Any) -> Any:
        if not self.has(service_type):
            raise LookupError(service_type)
        return self._db

    async def resolve_optional(self, service_type: Any) -> Any:
        if self.has(service_type):
            return self._db
        from quadkit.contracts.notification.delivery import DeliveryStoreProtocol

        if service_type is DeliveryStoreProtocol and self._db is not None:
            return SqlDeliveryStore(self._db)
        return None


async def _build(factory: Any, resolver: Any) -> Any:
    """Call a DI factory, awaiting it when it is async.

    Raw bindings are sync factories and the retry wrapper is an async one —
    both shapes are legal, so the test handles both.
    """
    result = factory(resolver)
    return await result if inspect.isawaitable(result) else result


@pytest.fixture
def smtp_config() -> MailerConfig:
    """A single SMTP backend with retries configured."""
    return MailerConfig(
        backends=[
            NamedMailerConfig(
                name="transactional",
                primary=True,
                driver="smtp",
                smtp=SMTPDriverConfig(host="smtp.example.com"),
            )
        ],
        retry_max_attempts=2,
        retry_base_delay=0.01,
    )


class TestRetryWiring:
    @pytest.mark.asyncio
    async def test_primary_binding_is_wrapped_when_retries_configured(
        self, smtp_config: MailerConfig
    ) -> None:
        provider = MailerProvider(config=smtp_config)
        registrar = _Registrar()
        await provider.register(registrar)

        mailer = await _build(registrar.binding(), _Resolver())

        assert isinstance(mailer, RetryingMailer)
        assert isinstance(mailer._delivery_store, MemoryDeliveryStore)
        assert mailer._max_attempts == 2
        assert mailer._base_delay == 0.01

    @pytest.mark.asyncio
    async def test_primary_binding_is_raw_when_retries_disabled(
        self, smtp_config: MailerConfig
    ) -> None:
        smtp_config.retry_max_attempts = 0
        provider = MailerProvider(config=smtp_config)
        registrar = _Registrar()
        await provider.register(registrar)

        mailer = await _build(registrar.binding(), _Resolver())

        assert not isinstance(mailer, RetryingMailer)

    @pytest.mark.asyncio
    async def test_delivery_store_is_sql_when_a_database_is_bound(
        self, smtp_config: MailerConfig
    ) -> None:
        """The store follows the app: a bound provider means durable state."""
        db = object()
        provider = MailerProvider(config=smtp_config)
        registrar = _Registrar()
        await provider.register(registrar)

        mailer = await _build(registrar.binding(), _Resolver(db))

        assert isinstance(mailer, RetryingMailer)
        assert isinstance(mailer._delivery_store, SqlDeliveryStore)

    @pytest.mark.asyncio
    async def test_named_bindings_stay_unwrapped(self, smtp_config: MailerConfig) -> None:
        """`retry_max_attempts` configures the default mailer, not named ones."""
        provider = MailerProvider(config=smtp_config)
        registrar = _Registrar()
        await provider.register(registrar)

        named = await _build(registrar.binding(name="transactional"), _Resolver())

        assert not isinstance(named, RetryingMailer)

    @pytest.mark.asyncio
    async def test_console_fallback_stays_unwrapped(self) -> None:
        """With no backend configured, the dev fallback is not retried.

        The console mailer cannot fail, so wrapping it would only write
        delivery rows for every dev email.
        """
        provider = MailerProvider(
            config=MailerConfig(console_fallback=True, retry_max_attempts=3)
        )
        registrar = _Registrar()
        await provider.register(registrar)

        mailer = await _build(registrar.binding(), _Resolver())

        assert not isinstance(mailer, RetryingMailer)
