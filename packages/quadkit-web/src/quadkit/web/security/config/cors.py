"""CORS configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from quadkit.config.base import BaseConfig
from quadkit.contracts.core.config import ConfigIssue, Environment
from quadkit.validation import ConfigDict, Field, model_validator


@dataclass(init=False)
class CORSConfig(BaseConfig):
    """CORS configuration.

    Accepts ``allow_origins`` as a convenience alias for ``allowed_origins``
    at construction time (e.g. ``CORSConfig(allow_origins=["https://..."])``).
    Comma-separated strings are also accepted so that values can be supplied
    via a single environment variable.

    Attributes:
        enabled: Enable CORS headers.  When ``False`` the middleware should
            skip CORS processing entirely.
        allowed_origins: Origins that are permitted.
            Use ``['*']`` to allow all; combine with ``allow_credentials=False``
            only.
        allow_methods: HTTP methods permitted in CORS requests.
        allow_headers: Request headers permitted in CORS requests.
        expose_headers: Response headers the browser may expose to JS.
        allow_credentials: Allow cookies / auth headers in CORS requests.
        debug_permissive: When True and debug mode is active, allow any origin
            via wildcard (explicit opt-in; no implicit widening).
        max_age: Pre-flight cache duration in seconds.
        allow_origin_regex: Regex pattern matched against the ``Origin`` header
            as a fallback when the origin is not in ``allowed_origins``.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(default=True, description="Enable CORS")
    allowed_origins: list[str] = Field(
        default_factory=list,
        description=(
            "Allowed origins (use ['*'] to allow all). Deny-by-default: "
            "an empty list blocks every cross-origin request."
        ),
    )
    allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH"]
    )
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])
    expose_headers: list[str] = Field(default_factory=list)
    allow_credentials: bool = Field(default=False)
    debug_permissive: bool = Field(
        default=False,
        description="When True and debug mode is active, allow any origin via wildcard "
        "(explicit opt-in replacement for the old implicit debug widening)",
    )
    max_age: int = Field(default=600)
    allow_origin_regex: str | None = Field(
        default=None,
        description="Regex pattern for allowed origins (matched when not in allowed_origins)",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_origins(cls, data: Any) -> Any:
        """Accept ``allow_origins`` as alias for ``allowed_origins``.

        Also parses comma-separated strings into lists so that
        ``CORS_ORIGINS="https://a.com,https://b.com"`` works via env vars.
        """
        if not isinstance(data, dict):
            return data
        data = dict(data)

        # Alias allow_origins → allowed_origins (web-compat)
        if "allow_origins" in data and "allowed_origins" not in data:
            data["allowed_origins"] = data.pop("allow_origins")

        # Parse comma-separated strings
        origins = data.get("allowed_origins")
        if isinstance(origins, str):
            data["allowed_origins"] = [
                o.strip() for o in origins.split(",") if o.strip()
            ]

        return data

    @model_validator(mode="after")
    def _validate_credentials_with_wildcard(self) -> CORSConfig:
        """Reject wildcard origins combined with allow_credentials.

        This is a CORS misconfiguration — browsers will reject such responses.
        """
        if self.allow_credentials and "*" in self.allowed_origins:
            raise ValueError(
                "SECURITY ERROR: allow_credentials=True combined with allowed_origins=['*'] "
                "is a CORS misconfiguration. Specify explicit origins when credentials are enabled."
            )
        return self

    @property
    def allow_origins(self) -> list[str]:
        """Alias for ``allowed_origins`` for backward compatibility."""
        return self.allowed_origins

    def to_middleware_kwargs(self) -> dict[str, Any]:
        """Return kwargs suitable for passing directly to a CORS middleware."""
        return {
            "allow_origins": self.allowed_origins,
            "allow_credentials": self.allow_credentials,
            "allow_methods": self.allow_methods,
            "allow_headers": self.allow_headers,
            "max_age": self.max_age,
            "allow_origin_regex": self.allow_origin_regex,
            "expose_headers": self.expose_headers,
        }

    def validate_for_environment(
        self, env: Environment | None = None
    ) -> list[ConfigIssue]:
        """Validate CORS for production environments."""
        resolved = env or self.environment
        issues: list[ConfigIssue] = []

        if resolved == Environment.PRODUCTION:
            if "*" in self.allowed_origins and self.allow_credentials:
                issues.append(
                    ConfigIssue(
                        field="cors.allowed_origins",
                        message="Wildcard origins ('*') cannot be used with allow_credentials=True in production",
                        severity="error",
                        suggestion="Explicitly list allowed origins or disable credentials",
                    )
                )

        return issues


__all__ = [
    "CORSConfig",
]
