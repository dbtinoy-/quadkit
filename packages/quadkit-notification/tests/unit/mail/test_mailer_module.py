"""Tests for MailerModule IoC module."""

from __future__ import annotations

from quadkit.contracts.mailer.protocols import MailerProtocol
from quadkit.di.module import DynamicModule
from quadkit.notification.config import MailerConfig
from quadkit.notification.di.mailer_provider import MailerProvider
from quadkit.notification.mailer.module import MailerModule


def test_mailer_module_configure_returns_dynamic_module() -> None:
    """configure() returns a DynamicModule instance."""
    result = MailerModule.configure()
    assert isinstance(result, DynamicModule)


def test_mailer_module_configure_exports_mailer_protocol() -> None:
    """configure() exports MailerProtocol for constructor injection."""
    module = MailerModule.configure()
    assert MailerProtocol in module.exports


def test_mailer_module_configure_providers_contains_mailer_provider() -> None:
    """configure() includes one MailerProvider in providers list."""
    module = MailerModule.configure()
    assert len(module.providers) == 1
    assert isinstance(module.providers[0], MailerProvider)


def test_mailer_module_configure_with_config() -> None:
    """configure() accepts explicit MailerConfig."""
    config = MailerConfig()
    module = MailerModule.configure(config)
    assert isinstance(module, DynamicModule)
    assert MailerProtocol in module.exports


def test_mailer_module_configure_with_none() -> None:
    """configure(None) works — config is optional."""
    result = MailerModule.configure(None)
    assert isinstance(result, DynamicModule)
    assert MailerProtocol in result.exports


def test_mailer_module_stub_returns_dynamic_module() -> None:
    """stub() returns a DynamicModule instance for testing."""
    result = MailerModule.stub()
    assert isinstance(result, DynamicModule)


def test_mailer_module_stub_exports_mailer_protocol() -> None:
    """stub() exports MailerProtocol for testing setups."""
    module = MailerModule.stub()
    assert MailerProtocol in module.exports


def test_mailer_module_stub_with_config() -> None:
    """stub() accepts optional MailerConfig."""
    config = MailerConfig()
    module = MailerModule.stub(config)
    assert isinstance(module, DynamicModule)
    assert MailerProtocol in module.exports
