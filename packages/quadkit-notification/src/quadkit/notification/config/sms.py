"""SMS driver configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quadkit.domain import DomainModel
from quadkit.notification.constants import DEFAULT_TWILIO_TIMEOUT
from quadkit.validation import Field, SecretStr, field_validator


@dataclass(init=False)
class TwilioDriverConfig(DomainModel):
    """Twilio SMS delivery configuration."""

    account_sid: str | None = Field(
        default=None,
        description="Twilio Account SID",
    )
    auth_token: SecretStr | None = Field(
        default=None,
        description="Twilio Auth Token",
    )
    from_number: str | None = Field(
        default=None,
        description="Twilio phone number (E.164 format)",
    )
    timeout: int = Field(
        default=DEFAULT_TWILIO_TIMEOUT,
        ge=1,
        description="HTTP timeout (s)",
    )

    @field_validator("auth_token")
    @classmethod
    def _coerce_auth_token(cls, value: Any) -> Any:
        if value is None or isinstance(value, SecretStr):
            return value
        return SecretStr(str(value))


@dataclass(init=False)
class NamedSMSConfig(DomainModel):
    """Configuration for a single named SMS backend.

    Used in NotificationConfig.sms_backends to declare multiple SMS backends
    that the framework registers as named DI bindings.

    Example:
        sms_backends:
          - name: alerts
            driver: twilio
            primary: true
            twilio:
              account_sid: AC...
              auth_token: ...
              from_number: +1234567890

    Args:
        name: Unique backend identifier. Used as the Named() DI key.
        primary: Whether this is the primary backend. Primary backends
            also receive the unnamed SMSChannelProtocol binding.
        driver: SMS driver. One of 'twilio' or other supported drivers.
        twilio: Twilio-specific config.
    """

    name: str = Field(..., description="Unique backend name used as the Named() DI key")
    primary: bool = Field(
        default=False,
        description="Also register under unnamed SMSChannelProtocol binding",
    )
    driver: str = Field(default="twilio", description="SMS driver name")
    twilio: TwilioDriverConfig | None = Field(
        default=None,
        description="Twilio driver config",
    )


__all__ = [
    "NamedSMSConfig",
    "TwilioDriverConfig",
]
