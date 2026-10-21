"""CSRF configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from quadkit.config.base import BaseConfig
from quadkit.contracts.core.config import ConfigIssue, Environment
from quadkit.validation import ConfigDict, Field, SecretStr, field_validator


@dataclass(init=False)
class CSRFConfig(BaseConfig):
    """Configuration for CSRF protection middleware.

    Attributes:
        enabled: Whether CSRF protection is active.
        cookie_name: Name of the cookie storing the CSRF token.
        header_name: Name of the header containing the client CSRF token.
        cookie_secure: Whether the cookie should be marked as secure (HTTPS only).
        cookie_httponly: Whether the cookie should be marked as HttpOnly.
        cookie_samesite: Value for the SameSite attribute ('Lax', 'Strict', or 'None').
        cookie_domain: Optional domain attribute for the CSRF cookie.
        cookie_path: Path attribute for the CSRF cookie.
        token_length: Length of the generated CSRF token in bytes.
        token_ttl: Lifetime in seconds for synchronizer-mode tokens stored in cache.
        excluded_paths: URL path prefixes exempt from CSRF validation for
            requests that do not carry the CSRF cookie; requests that do carry
            it are still validated. Unrelated cookies do not disable the
            exemption.
        exclude_content_types: ``Content-Type`` values that bypass CSRF validation.
        exclude_auth_schemes: Authorization header schemes that bypass CSRF validation.
        secret_key: HMAC secret used to sign and verify CSRF tokens.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(default=False)
    cookie_name: str = Field(default="csrf_token")
    header_name: str = Field(default="X-CSRF-Token")
    cookie_secure: bool = Field(default=True)
    cookie_httponly: bool = Field(default=True)
    cookie_samesite: str = Field(default="Lax")
    cookie_domain: str | None = Field(default=None)
    cookie_path: str = Field(default="/")
    token_length: int = Field(
        default=32,
        ge=16,
        description="Length in bytes of a generated CSRF token",
    )
    token_ttl: int = Field(
        default=3600,
        description="TTL in seconds for synchronizer-mode tokens stored in cache.",
    )
    excluded_paths: list[str] = Field(
        default_factory=list,
        description="URL path prefixes exempt from CSRF validation for requests "
        "that do not carry the CSRF cookie; requests carrying it are still "
        "validated. Unrelated cookies (session, affinity, …) do not disable the "
        "exemption.",
    )
    exclude_content_types: list[str] = Field(
        default_factory=list,
        description="Content-Type values that bypass CSRF validation (explicit opt-in — "
        "JSON requests are validated by default so cookie-authenticated SPA flows "
        "cannot bypass CSRF).",
    )
    exclude_auth_schemes: list[str] = Field(
        default_factory=list,
        description="Authorization header schemes that bypass CSRF validation (explicit opt-in).",
    )
    secret_key: SecretStr | None = Field(
        default=None,
        exclude=True,
        description="HMAC secret used to sign and verify CSRF tokens "
        "(populated via QK_WEB__SECURITY__CSRF__SECRET_KEY)",
    )

    @field_validator("secret_key")
    @classmethod
    def _coerce_secret_key(cls, value: Any) -> Any:
        """Accept plain strings from env/YAML; store as SecretStr."""
        if value is None or isinstance(value, SecretStr):
            return value
        return SecretStr(str(value))

    def validate_for_environment(
        self, env: Environment | None = None
    ) -> list[ConfigIssue]:
        """CSRF production validation."""
        resolved = env or self.environment
        issues: list[ConfigIssue] = []

        if resolved == Environment.PRODUCTION and self.enabled:
            csrf_raw = self.secret_key
            csrf_key: str | None = (
                csrf_raw.get_secret_value()
                if isinstance(csrf_raw, SecretStr)
                else csrf_raw
            )
            if not csrf_key or csrf_key.strip() == "":
                issues.append(
                    ConfigIssue(
                        field="csrf.secret_key",
                        message="CSRF is enabled but no secret_key is set in production",
                        severity="warning",
                        suggestion="Set a strong, random secret_key if using HMAC-based CSRF protection",
                    )
                )

        return issues


__all__ = [
    "CSRFConfig",
]
