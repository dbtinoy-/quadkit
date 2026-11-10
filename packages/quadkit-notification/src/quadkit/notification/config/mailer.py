"""Mailer driver configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from quadkit.config.base import BaseConfig
from quadkit.domain import DomainModel
from quadkit.notification.constants import (
    DEFAULT_SENDGRID_TIMEOUT,
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_TIMEOUT,
)
from quadkit.validation import ConfigDict, Field, SecretStr, field_validator


@dataclass(init=False)
class SMTPDriverConfig(DomainModel):
    """SMTP-specific connection configuration."""

    host: str = Field(
        default="localhost",
        description="SMTP server hostname",
    )
    port: int = Field(
        default=DEFAULT_SMTP_PORT,
        ge=1,
        le=65535,
        description="SMTP port",
    )
    username: str | None = Field(
        default=None,
        description="SMTP auth username",
    )
    password: SecretStr | None = Field(
        default=None,
        description="SMTP auth password",
    )
    use_tls: bool = Field(
        default=True,
        description="Use STARTTLS (port 587)",
    )
    use_ssl: bool = Field(
        default=False,
        description="Use SSL from connect (port 465)",
    )
    timeout: int = Field(
        default=DEFAULT_SMTP_TIMEOUT,
        ge=1,
        description="Connection timeout (s)",
    )

    @field_validator("password")
    @classmethod
    def _coerce_password(cls, value: Any) -> Any:
        if value is None or isinstance(value, SecretStr):
            return value
        return SecretStr(str(value))


@dataclass(init=False)
class SendGridDriverConfig(DomainModel):
    """SendGrid API configuration."""

    api_key: SecretStr | None = Field(
        default=None,
        description="SendGrid API key",
    )
    timeout: int = Field(
        default=DEFAULT_SENDGRID_TIMEOUT,
        ge=1,
        description="HTTP timeout (s)",
    )
    sandbox_mode: bool = Field(
        default=False,
        description="Sandbox mode — emails not sent",
    )

    @field_validator("api_key")
    @classmethod
    def _coerce_api_key(cls, value: Any) -> Any:
        if value is None or isinstance(value, SecretStr):
            return value
        return SecretStr(str(value))


@dataclass(init=False)
class NamedMailerConfig(DomainModel):
    """Configuration for a single named mailer backend.

    Used in MailerConfig.backends to declare multiple mailer backends
    that the framework registers as named DI bindings.

    Example:
        backends:
          - name: transactional
            driver: sendgrid
            primary: true
            sendgrid:
              api_key: sg_...
          - name: internal
            driver: smtp
            smtp:
              host: smtp.example.com
              port: 587

    Args:
        name: Unique backend identifier. Used as the Named() DI key.
        primary: Whether this is the primary backend. Primary backends
            also receive the unnamed MailerProtocol binding.
        driver: Mailer driver. One of 'smtp' or 'sendgrid'.
        from_email: Default sender email address.
        from_name: Default sender display name.
        smtp: SMTP-specific connection config.
        sendgrid: SendGrid-specific config.
    """

    name: str = Field(..., description="Unique backend name used as the Named() DI key")
    primary: bool = Field(
        default=False,
        description="Also register under unnamed MailerProtocol binding",
    )
    driver: str = Field(default="smtp", description="Mailer driver name")
    from_email: str | None = Field(
        default=None,
        description="Default sender email address",
    )
    from_name: str | None = Field(
        default=None,
        description="Default sender display name",
    )
    smtp: SMTPDriverConfig | None = Field(
        default=None,
        description="SMTP driver config",
    )
    sendgrid: SendGridDriverConfig | None = Field(
        default=None,
        description="SendGrid driver config",
    )


@dataclass(init=False)
class MailerConfig(BaseConfig):
    """Top-level mailer configuration.

    Loaded from the ``mailer:`` key in application.yaml, with environment
    variable overrides via ``QK_NOTIFICATION__MAILER__*`` prefix.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(  # type: ignore[typeddict-unknown-key]
        env_prefix="QK_NOTIFICATION__MAILER__",
        env_nested_delimiter="__",
        extra="ignore",
    )

    backends: list[NamedMailerConfig] = Field(
        default_factory=list,
        description=(
            "Named mailer backends for multi-backend support. "
            "When non-empty, the provider registers each backend under "
            "Annotated[MailerProtocol, Named(entry.name)]. "
            "The first entry (or the one with primary=True) also receives "
            "the unnamed MailerProtocol binding for backward compatibility."
        ),
    )
    console_fallback: bool = Field(
        default=True,
        description=(
            "When no backends are configured, bind a ConsoleMailer as the "
            "default MailerProtocol so emails are logged to the application "
            "console instead of being silently dropped. Set to False to "
            "render email sending unavailable (MailerProtocol unbindable)."
        ),
    )
    retry_max_attempts: int = Field(
        default=0,
        ge=0,
        description=(
            "When > 0, wrap the default MailerProtocol in RetryingMailer with "
            "this many attempts, persisting delivery state so transient SMTP "
            "failures are retried instead of dropped."
        ),
    )
    retry_base_delay: float = Field(
        default=60.0,
        description="Base delay in seconds for the exponential backoff.",
    )

    @classmethod
    def from_named(cls, entry: NamedMailerConfig) -> MailerConfig:
        """Build a single-backend MailerConfig from a NamedMailerConfig entry.

        Used internally by MailerProvider to create per-backend configs
        from a multi-backend declaration.

        Args:
            entry: The named backend entry to materialise.

        Returns:
            A MailerConfig configured for the single named backend.
        """
        return cls(backends=[entry])


__all__ = [
    "MailerConfig",
    "NamedMailerConfig",
    "SMTPDriverConfig",
    "SendGridDriverConfig",
]
