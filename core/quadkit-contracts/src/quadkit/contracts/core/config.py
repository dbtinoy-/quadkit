"""Configuration protocol for the Quadkit framework.

Defines the runtime-checkable protocol that all configuration implementations
must satisfy. This enables DI-based config access without coupling to concrete
config classes (Pydantic, DomainModel, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import os
from typing import Any, Protocol, TypeVar, overload, runtime_checkable

T = TypeVar("T")


class Environment(StrEnum):
    """Deployment environment discriminator.

    Use ``Environment.from_env()`` to read the current environment from the
    ``QK_ENV`` (or ``APP_ENV``) environment variable.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"

    @classmethod
    def from_env(cls, default: Environment = "development") -> Environment:  # type: ignore[assignment]
        """Read the active environment from ``QK_ENV`` or ``APP_ENV``.

        .. note::
            When neither variable is set (or its value is not a valid
            environment name), the result falls back to *default*, which is
            **development**. Production deployments MUST set ``QK_ENV`` (or
            ``APP_ENV``) to ``production`` explicitly: every production
            gate (e.g. ``debug=True`` rejection at boot) only applies when
            the resolved environment is production.

        Args:
            default: Fallback when neither variable is set (or unparseable).

        Returns:
            The resolved ``Environment`` member.
        """
        raw = os.environ.get("QK_ENV") or os.environ.get("APP_ENV") or default
        try:
            return cls(raw.lower())
        except ValueError:
            return cls(default)


@dataclass(frozen=True)
class ConfigIssue:
    """A single configuration validation issue.

    Attributes:
        field: Dot-notation path to the offending field (e.g. ``"db.url"``).
        message: Human-readable description of the problem.
        severity: ``"error"`` blocks startup; ``"warning"`` is informational.
        suggestion: Optional remediation hint shown to operators.
    """

    field: str
    message: str
    severity: str = "error"
    suggestion: str = ""


@runtime_checkable
class ConfigProtocol(Protocol):
    """Protocol for configuration access across the framework.

    Any configuration object (BaseConfig, QuadkitConfig, or custom
    implementations) can satisfy this protocol by implementing ``get()``,
    ``get_section()``, and ``has_section()``.

    Example::

        config = container.resolve(ConfigProtocol)
        db_url = config.get("database.url", "sqlite:///default.db")
        logging = config.get_section("logging", LoggingConfig)
    """

    @property
    def environment(self) -> Environment:
        """The active deployment environment."""
        ...

    @property
    def is_production(self) -> bool:
        """Return ``True`` when the active environment is production."""
        ...

    @property
    def is_development(self) -> bool:
        """Return ``True`` when the active environment is development."""
        ...

    @property
    def is_testing(self) -> bool:
        """Return ``True`` when the active environment is testing."""
        ...

    @property
    def is_staging(self) -> bool:
        """Return ``True`` when the active environment is staging."""
        ...

    @property
    def is_debug(self) -> bool:
        """Return ``True`` when debug mode is enabled."""
        ...

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g. ``"app.name"`` or ``"database.url"``).
            default: Value returned when the key is not found.

        Returns:
            The configuration value, or *default* if not found.
        """
        ...

    @overload
    def get_section(
        self, name: str, model_cls: None = None
    ) -> dict[str, Any] | None: ...

    @overload
    def get_section(self, name: str, model_cls: type[T]) -> T: ...

    def get_section(
        self,
        name: str,
        model_cls: type[T] | None = None,
    ) -> T | dict[str, Any] | None:
        """Get a typed configuration section.

        Args:
            name: Section name (e.g. ``"logging"``).
            model_cls: Optional model class to coerce the section into.

        Returns:
            A model instance when *model_cls* is provided, otherwise a raw
            dict or the attribute value; ``None`` when the section is absent
            and no model class was supplied.
        """
        ...

    def has_section(self, name: str) -> bool:
        """Check whether a configuration section exists.

        Args:
            name: Section name to check.

        Returns:
            True if the section is present.
        """
        ...


__all__ = ["ConfigIssue", "ConfigProtocol", "Environment"]
