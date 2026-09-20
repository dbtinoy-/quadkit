"""Aggregate security configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.contracts.core.config import ConfigIssue, Environment
from quadkit.security.constants import ENV_NESTED_DELIMITER, ENV_PREFIX
from quadkit.validation import ConfigDict, Field, model_validator
from quadkit.web.security.config.cors import CORSConfig
from quadkit.web.security.config.csp import CSPConfig
from quadkit.web.security.config.csrf import CSRFConfig
from quadkit.web.security.config.headers import CrossOriginConfig, HSTSConfig


@dataclass(init=False)
class SecurityConfig(BaseConfig):
    """Root HTTP security configuration for quadkit-web.

    Aggregates CORS, CSRF, security-headers, and HTTP security-policy
    sub-configs into a single object.

    Attributes:
        cors: CORS policy configuration.
        csrf: CSRF protection configuration.
        hsts: Structured HSTS configuration.
        csp: Content Security Policy configuration.
        cross_origin: Cross-origin isolation policy headers.
        referrer_policy: Referrer-Policy header value.
        custom_headers: Additional response headers emitted verbatim.
        permissions_policy: Permissions-Policy directive map.
        enable_csrf: Convenience flag — enable/disable CSRF.
        enable_cors: Convenience flag — enable/disable CORS.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        env_prefix=ENV_PREFIX,  # type: ignore[typeddict-unknown-key]
        env_nested_delimiter=ENV_NESTED_DELIMITER,
        extra="ignore",
    )

    enabled: bool = Field(default=True, description="Enable the security subsystem")

    cors: CORSConfig = Field(default_factory=CORSConfig)
    csrf: CSRFConfig = Field(default_factory=CSRFConfig)

    # Convenience flags — an explicit ``False`` disables the sub-config
    enable_csrf: bool = Field(default=True)
    enable_cors: bool = Field(default=True)

    # Host validation (fail-closed; production requires a non-empty list)
    allowed_hosts: list[str] = Field(
        default_factory=list,
        description="Hostnames permitted to reach the application. Empty by "
        "default; must be configured before production deployment.",
    )

    # HTTP security-policy sub-configs
    hsts: HSTSConfig = Field(
        default_factory=HSTSConfig,
        description="HSTS configuration (enabled, max_age, subdomains, preload)",
    )
    csp: CSPConfig = Field(
        default_factory=CSPConfig,
        description="Content Security Policy configuration",
    )
    cross_origin: CrossOriginConfig = Field(
        default_factory=CrossOriginConfig,
        description="Cross-origin isolation policy headers",
    )
    referrer_policy: str = Field(
        default="strict-origin-when-cross-origin",
        description="Referrer-Policy header value",
    )
    custom_headers: dict[str, str] = Field(
        default_factory=lambda: {
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "x-xss-protection": "1; mode=block",
        },
        description="Additional HTTP response headers emitted verbatim",
    )
    permissions_policy: dict[str, str] = Field(
        default_factory=lambda: {
            "geolocation": "()",
            "microphone": "()",
            "camera": "()",
            "payment": "()",
            "usb": "()",
        },
        description="Permissions-Policy directive map",
    )

    def validate_for_environment(
        self, env: Environment | None = None
    ) -> list[ConfigIssue]:
        """Aggregate validation from all sub-configs."""
        issues: list[ConfigIssue] = []
        issues.extend(self.cors.validate_for_environment(env))
        issues.extend(self.csrf.validate_for_environment(env))
        issues.extend(self.hsts.validate_for_environment(env))
        return issues

    @model_validator(mode="after")
    def _sync_enable_flags(self) -> SecurityConfig:
        """Make the convenience flags authoritative for disabling their sub-config.

        An explicit ``enable_csrf=False`` / ``enable_cors=False`` overrides the
        matching sub-config so a convenience flag can never disagree with the
        wired middleware; an explicit sub-config still wins when the flag is
        left at its default ``True``.
        """
        if not self.enable_csrf:
            self.csrf.enabled = False
        if not self.enable_cors:
            self.cors.enabled = False
        return self


__all__ = [
    "SecurityConfig",
]
