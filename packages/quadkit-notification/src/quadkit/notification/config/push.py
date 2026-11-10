"""Push notification driver configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quadkit.domain import DomainModel
from quadkit.notification.constants import (
    DEFAULT_APNS_TIMEOUT,
    DEFAULT_FCM_TIMEOUT,
)
from quadkit.validation import Field, SecretStr, field_validator


@dataclass(init=False)
class FCMDriverConfig(DomainModel):
    """Firebase Cloud Messaging (FCM) push notification configuration."""

    server_key: SecretStr | None = Field(
        default=None,
        description="FCM Server API Key",
    )

    @field_validator("server_key")
    @classmethod
    def _coerce_server_key(cls, value: Any) -> Any:
        if value is None or isinstance(value, SecretStr):
            return value
        return SecretStr(str(value))

    timeout: int = Field(
        default=DEFAULT_FCM_TIMEOUT,
        ge=1,
        description="HTTP timeout (s)",
    )


@dataclass(init=False)
class APNsDriverConfig(DomainModel):
    """Apple Push Notification service (APNs) configuration."""

    team_id: str | None = Field(
        default=None,
        description="Apple Developer Team ID (10-character string)",
    )
    key_id: str | None = Field(
        default=None,
        description="APNs Auth Key ID (10-character string)",
    )
    apns_auth_key: SecretStr | None = Field(
        default=None,
        description=(
            "ECDSA private key — PEM string starting with "
            "'-----BEGIN PRIVATE KEY-----' or path to a .p8 key file"
        ),
    )
    bundle_id: str | None = Field(
        default=None,
        description="App bundle identifier (e.g. com.example.MyApp)",
    )
    sandbox: bool = Field(
        default=False,
        description="Use the APNs sandbox endpoint instead of production",
    )
    timeout: int = Field(
        default=DEFAULT_APNS_TIMEOUT,
        ge=1,
        description="HTTP timeout (s)",
    )

    @field_validator("apns_auth_key")
    @classmethod
    def _coerce_apns_auth_key(cls, value: Any) -> Any:
        if value is None or isinstance(value, SecretStr):
            return value
        return SecretStr(str(value))


@dataclass(init=False)
class WebPushDriverConfig(DomainModel):
    """Web Push (RFC 8030) driver configuration."""

    vapid_private_key: SecretStr | None = Field(
        default=None,
        description="VAPID private key (PEM-encoded EC prime256v1)",
    )
    vapid_public_key: str | None = Field(
        default=None,
        description="VAPID public key (base64url-encoded)",
    )
    vapid_claims_subject: str | None = Field(
        default=None,
        description="VAPID claims subject URI (e.g. mailto:ops@example.com)",
    )
    timeout: int = Field(
        default=30,
        ge=1,
        description="HTTP timeout (s)",
    )

    @field_validator("vapid_private_key")
    @classmethod
    def _coerce_vapid_private_key(cls, value: Any) -> Any:
        if value is None or isinstance(value, SecretStr):
            return value
        return SecretStr(str(value))


@dataclass(init=False)
class NamedPushConfig(DomainModel):
    """Configuration for a single named push notification backend.

    Used in NotificationConfig.push_backends to declare multiple push backends
    that the framework registers as named DI bindings.

    Example:
        push_backends:
          - name: mobile
            driver: fcm
            primary: true
            fcm:
              server_key: AAAA...

    Args:
        name: Unique backend identifier. Used as the Named() DI key.
        primary: Whether this is the primary backend. Primary backends
            also receive the unnamed PushChannelProtocol binding.
        driver: Push driver. One of 'fcm' or other supported drivers.
        fcm: FCM-specific config.
    """

    name: str = Field(..., description="Unique backend name used as the Named() DI key")
    primary: bool = Field(
        default=False,
        description="Also register under unnamed PushChannelProtocol binding",
    )
    driver: str = Field(default="fcm", description="Push driver name")
    fcm: FCMDriverConfig | None = Field(
        default=None,
        description="FCM driver config",
    )
    apns: APNsDriverConfig | None = Field(
        default=None,
        description="APNs driver config",
    )
    web_push: WebPushDriverConfig | None = Field(
        default=None,
        description="Web Push driver config",
    )


__all__ = [
    "APNsDriverConfig",
    "FCMDriverConfig",
    "NamedPushConfig",
    "WebPushDriverConfig",
]
