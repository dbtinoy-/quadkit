"""Tests for MailerConfig."""

from __future__ import annotations

from quadkit.notification.config import (
    MailerConfig,
    NamedMailerConfig,
    SendGridDriverConfig,
    SMTPDriverConfig,
)


class TestNamedMailerConfig:
    def test_defaults(self) -> None:
        cfg = NamedMailerConfig(name="default", driver="smtp")
        assert cfg.name == "default"
        assert cfg.primary is False
        assert cfg.driver == "smtp"
        assert cfg.from_email is None
        assert cfg.smtp is None
        assert cfg.sendgrid is None

    def test_primary_flag(self) -> None:
        cfg = NamedMailerConfig(name="main", driver="sendgrid", primary=True)
        assert cfg.primary is True


class TestMailerConfig:
    def test_empty_backends(self) -> None:
        cfg = MailerConfig()
        assert cfg.backends == []

    def test_multiple_backends(self) -> None:
        cfg = MailerConfig(
            backends=[
                NamedMailerConfig(
                    name="transactional", primary=True, driver="sendgrid"
                ),
                NamedMailerConfig(name="internal", driver="smtp"),
            ]
        )
        assert len(cfg.backends) == 2
        assert cfg.backends[0].name == "transactional"
        assert cfg.backends[0].primary is True
        assert cfg.backends[1].name == "internal"

    def test_from_named(self) -> None:
        entry = NamedMailerConfig(name="transactional", driver="sendgrid", primary=True)
        cfg = MailerConfig.from_named(entry)
        assert len(cfg.backends) == 1
        assert cfg.backends[0].name == "transactional"


class TestSMTPDriverConfig:
    def test_defaults(self) -> None:
        cfg = SMTPDriverConfig()
        assert cfg.port == 587
        assert cfg.use_tls is True
        assert cfg.use_ssl is False
        assert cfg.timeout == 30


class TestSendGridDriverConfig:
    def test_defaults(self) -> None:
        cfg = SendGridDriverConfig()
        assert cfg.timeout == 30
        assert cfg.sandbox_mode is False
