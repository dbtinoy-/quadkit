"""Security headers, HSTS, and cross-origin configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.contracts.core.config import ConfigIssue, Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class SecurityHeadersConfig(BaseConfig):
    """Configuration for security response headers.

    Attributes:
        hsts_max_age: Strict-Transport-Security max age in seconds.
        hsts_include_subdomains: Whether HSTS applies to subdomains.
        content_type_nosniff: Sets X-Content-Type-Options to 'nosniff'.
        frame_options: X-Frame-Options value ('DENY', 'SAMEORIGIN').
        xss_protection: X-XSS-Protection value.
        referrer_policy: Referrer-Policy value.
        csp: Content-Security-Policy header string.
        permissions_policy: Permissions-Policy header string.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    hsts_max_age: int = Field(default=31536000)
    hsts_include_subdomains: bool = Field(default=True)
    content_type_nosniff: bool = Field(default=True)
    frame_options: str = Field(default="DENY")
    xss_protection: str = Field(default="1; mode=block")
    referrer_policy: str = Field(default="strict-origin-when-cross-origin")
    csp: str | None = Field(default=None)
    permissions_policy: str | None = Field(default=None)

    def validate_for_environment(
        self, env: Environment | None = None
    ) -> list[ConfigIssue]:
        """Validate security headers for production."""
        resolved = env or self.environment
        issues: list[ConfigIssue] = []

        if resolved == Environment.PRODUCTION:
            if self.hsts_max_age < 31536000:
                issues.append(
                    ConfigIssue(
                        field="headers.hsts_max_age",
                        message="HSTS max_age should be at least 1 year (31536000 seconds) in production",
                        severity="warning",
                        suggestion="Increase hsts_max_age to 31536000 or higher",
                    )
                )

        return issues


@dataclass(init=False)
class HSTSConfig(BaseConfig):
    """HTTP Strict Transport Security configuration.

    Attributes:
        enabled: Emit the ``Strict-Transport-Security`` header.
        max_age: ``max-age`` directive in seconds.
        include_subdomains: Append the ``includeSubDomains`` directive.
        preload: Append the ``preload`` directive.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=False, description="Emit the Strict-Transport-Security header"
    )
    max_age: int = Field(
        default=31536000, description="HSTS max-age in seconds (default 1 year)"
    )
    include_subdomains: bool = Field(
        default=True, description="Apply HSTS to all subdomains"
    )
    preload: bool = Field(
        default=False, description="Include site in HSTS preload list"
    )


@dataclass(init=False)
class CrossOriginConfig(BaseConfig):
    """Cross-Origin policy configuration.

    Controls whether and with what values the three cross-origin
    isolation headers are sent:

    * ``Cross-Origin-Embedder-Policy``
    * ``Cross-Origin-Opener-Policy``
    * ``Cross-Origin-Resource-Policy``

    Attributes:
        enabled: Emit the cross-origin isolation headers.
        embedder_policy: ``COEP`` value (e.g. ``'require-corp'``).
        opener_policy: ``COOP`` value (e.g. ``'same-origin'``).
        resource_policy: ``CORP`` value (e.g. ``'same-origin'``).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=False,
        description="Emit cross-origin isolation headers",
    )
    embedder_policy: str = Field(
        default="require-corp",
        description="Cross-Origin-Embedder-Policy header value",
    )
    opener_policy: str = Field(
        default="same-origin",
        description="Cross-Origin-Opener-Policy header value",
    )
    resource_policy: str = Field(
        default="same-origin",
        description="Cross-Origin-Resource-Policy header value",
    )


__all__ = [
    "CrossOriginConfig",
    "HSTSConfig",
    "SecurityHeadersConfig",
]
