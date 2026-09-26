"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Configuration models for auth-web demo services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, cast

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class PasswordResetConfig(BaseConfig):
    """Configuration for the password reset service.

    Controls token length, expiry, and rate limiting for
    password reset requests.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    token_length: int = Field(
        default=32,
        description="Length of the reset token in bytes (before URL encoding)",
    )
    token_expiry_hours: int = Field(
        default=24,
        description="Hours before a reset token expires",
    )
    rate_limit_per_hour: int = Field(
        default=5,
        description="Maximum reset requests per email per hour",
    )


@dataclass(init=False)
class AccountVerificationConfig(BaseConfig):
    """Configuration for the account verification service.

    Controls token length, expiry, and whether new accounts
    must verify their email before accessing protected resources.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    token_length: int = Field(
        default=32,
        description="Length of the verification token in bytes",
    )
    token_expiry_days: int = Field(
        default=7,
        description="Days before a verification token expires",
    )
    required_for_login: bool = Field(
        default=False,
        description="Require email verification before allowing login",
    )


@dataclass(init=False)
class RegistrationConfig(BaseConfig):
    """Configuration for the registration flow.

    Controls whether verification emails are sent automatically
    after registration and whether new users require admin approval.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    auto_send_verification: bool = Field(
        default=True,
        description="Automatically send a verification email after registration",
    )
    default_role: str = Field(
        default="viewer",
        description="Default role assigned to newly registered users",
    )
    require_admin_approval: bool = Field(
        default=False,
        description="Require admin approval before new accounts are activated",
    )


@dataclass(init=False)
class AuthWebConfig(BaseConfig):
    """Root configuration for auth-web demo services.

    Aggregates password reset, account verification, and registration
    configuration under a single config section.
    """

    model_config = cast(
        "ConfigDict",
        {
            "env_prefix": "QK_AUTH_WEB__",
            "env_nested_delimiter": "__",
            "extra": "ignore",
        },
    )

    config_section: ClassVar[str] = "auth_web"
    name: str = "auth_web"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")

    password_reset: PasswordResetConfig = Field(
        default_factory=PasswordResetConfig,
        description="Password reset service configuration",
    )
    account_verification: AccountVerificationConfig = Field(
        default_factory=AccountVerificationConfig,
        description="Account verification service configuration",
    )
    registration: RegistrationConfig = Field(
        default_factory=RegistrationConfig,
        description="Registration flow configuration",
    )


__all__ = [
    "AccountVerificationConfig",
    "AuthWebConfig",
    "PasswordResetConfig",
    "RegistrationConfig",
]
