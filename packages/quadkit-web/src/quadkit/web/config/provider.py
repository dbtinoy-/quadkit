"""Web provider configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.validation import ConfigDict, Field, SecretStr


@dataclass(init=False)
class WebProviderConfig(BaseConfig):
    """Configuration for the WebProvider itself.

    This provides provider-specific settings that complement the main WebConfig.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    # OpenAPI settings
    openapi_title: str = Field(default="API", description="OpenAPI title")
    openapi_version: str = Field(default="1.0.0", description="OpenAPI version")

    # Middleware and filters
    middleware: list[str] = Field(
        default_factory=list,
        description="Middleware class names",
    )
    exception_filters: list[str] = Field(
        default_factory=list,
        description="Exception filter class names",
    )

    # Whether to raise on duplicate route registrations
    fail_on_route_conflict: bool = Field(
        default=False,
        description="If true, duplicate route registrations will raise during startup; otherwise a warning is emitted",
    )

    # Debug routes settings
    debug_routes: bool = Field(default=False, description="Enable debug routes")
    debug_routes_token: SecretStr | None = Field(
        default=None,
        description="Token for debug routes access",
    )
    debug_routes_require_middleware: str | None = Field(
        default=None,
        description="Required middleware for debug routes",
    )
    debug_routes_rate_limit: int = Field(
        default=0,
        description="Rate limit for debug routes",
    )
    debug_routes_rate_window_seconds: int = Field(
        default=60,
        description="Rate limit window for debug routes",
    )

    @property
    def is_production(self) -> bool:
        """Returns True if running in production environment."""
        return self.environment.value == "production"

    @property
    def is_development(self) -> bool:
        """Returns True if running in development environment."""
        return self.environment.value == "development"

    @property
    def is_test(self) -> bool:
        """Returns True if running in test environment."""
        return self.environment.value == "test"


__all__ = [
    "WebProviderConfig",
]
