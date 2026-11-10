"""Top-level notification configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.notification.config.push import NamedPushConfig
from quadkit.notification.config.sms import NamedSMSConfig
from quadkit.notification.constants import (
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
)
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class NotificationConfig(BaseConfig):
    """Top-level notification configuration.

    Loaded from the ``notification:`` key in application.yaml, with environment
    variable overrides via ``QK_NOTIFICATION__*`` prefix.
    """

    config_section: ClassVar[str] = "notification"

    name: str = "notification"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")

    model_config: ClassVar[ConfigDict] = ConfigDict(  # type: ignore[typeddict-unknown-key]
        env_prefix=ENV_PREFIX,
        env_nested_delimiter=ENV_NESTED_DELIMITER,
        extra="ignore",
    )

    sms_backends: list[NamedSMSConfig] = Field(
        default_factory=list,
        description=(
            "Named SMS backends for multi-backend support. "
            "When non-empty, the provider registers each backend under "
            "Annotated[SMSChannelProtocol, Named(entry.name)]. "
            "The first entry (or the one with primary=True) also receives "
            "the unnamed SMSChannelProtocol binding for backward compatibility."
        ),
    )
    push_backends: list[NamedPushConfig] = Field(
        default_factory=list,
        description=(
            "Named push notification backends for multi-backend support. "
            "When non-empty, the provider registers each backend under "
            "Annotated[PushChannelProtocol, Named(entry.name)]. "
            "The first entry (or the one with primary=True) also receives "
            "the unnamed PushChannelProtocol binding for backward compatibility."
        ),
    )

    @classmethod
    def from_named_sms(cls, entry: NamedSMSConfig) -> NotificationConfig:
        """Build a single-SMS-backend NotificationConfig from a NamedSMSConfig entry.

        Used internally by NotificationProvider to create per-backend configs
        from a multi-backend declaration.

        Args:
            entry: The named SMS backend entry to materialise.

        Returns:
            A NotificationConfig configured for the single named SMS backend.
        """
        return cls(sms_backends=[entry])

    @classmethod
    def from_named_push(cls, entry: NamedPushConfig) -> NotificationConfig:
        """Build a single-push-backend NotificationConfig from a NamedPushConfig entry.

        Used internally by NotificationProvider to create per-backend configs
        from a multi-backend declaration.

        Args:
            entry: The named push backend entry to materialise.

        Returns:
            A NotificationConfig configured for the single named push backend.
        """
        return cls(push_backends=[entry])


__all__ = [
    "NotificationConfig",
]
