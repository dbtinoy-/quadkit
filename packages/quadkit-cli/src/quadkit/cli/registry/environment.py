"""Environment registry for managing different environments.

This module provides a registry pattern for environment configurations.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
import os
from typing import ClassVar


@dataclass
class EnvironmentConfig:
    """Configuration for an environment."""

    name: str
    description: str = ""
    variables: dict[str, str] = field(default_factory=dict)
    database_url: str = ""
    debug: bool = False
    log_level: str = "INFO"


class Environment(abc.ABC):
    """Abstract base class for environments."""

    name: ClassVar[str]
    description: ClassVar[str]

    @abc.abstractmethod
    def get_config(self) -> EnvironmentConfig:
        """Get environment configuration."""

    @abc.abstractmethod
    def validate(self) -> tuple[bool, str]:
        """Validate the environment is properly configured."""
        raise NotImplementedError


class DevelopmentEnvironment(Environment):
    """Development environment."""

    name = "development"
    description = "Local development environment"

    def get_config(self) -> EnvironmentConfig:
        return EnvironmentConfig(
            name=self.name,
            description=self.description,
            database_url=os.environ.get("DATABASE_URL", "sqlite:///./dev.db"),
            debug=True,
            log_level="DEBUG",
        )

    def validate(self) -> tuple[bool, str]:
        return True, "Development environment is valid"


class StagingEnvironment(Environment):
    """Staging environment."""

    name = "staging"
    description = "Staging/QA environment"

    def get_config(self) -> EnvironmentConfig:
        return EnvironmentConfig(
            name=self.name,
            description=self.description,
            database_url=os.environ.get("DATABASE_URL", ""),
            debug=False,
            log_level="INFO",
        )

    def validate(self) -> tuple[bool, str]:
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            return False, "DATABASE_URL is required for staging"
        return True, "Staging environment is valid"


class ProductionEnvironment(Environment):
    """Production environment."""

    name = "production"
    description = "Production environment"

    def get_config(self) -> EnvironmentConfig:
        return EnvironmentConfig(
            name=self.name,
            description=self.description,
            database_url=os.environ.get("DATABASE_URL", ""),
            debug=False,
            log_level="WARNING",
        )

    def validate(self) -> tuple[bool, str]:
        errors = []

        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            errors.append("DATABASE_URL is required")

        if "localhost" in db_url or "127.0.0.1" in db_url:
            errors.append("Database URL should not point to localhost in production")

        secret = os.environ.get("AUTH_SECRET", "")
        if not secret or len(secret) < 32:
            errors.append("AUTH_SECRET should be at least 32 characters")

        if errors:
            return False, "; ".join(errors)
        return True, "Production environment is valid"


class TestEnvironment(Environment):
    """Test environment."""

    name = "test"
    description = "Testing environment"

    def get_config(self) -> EnvironmentConfig:
        return EnvironmentConfig(
            name=self.name,
            description=self.description,
            database_url=os.environ.get("DATABASE_URL", "sqlite:///./test.db"),
            debug=True,
            log_level="DEBUG",
        )

    def validate(self) -> tuple[bool, str]:
        return True, "Test environment is valid"


class EnvironmentRegistry:
    """Registry for environments.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin environments.
    """

    def __init__(self) -> None:
        self._environments: dict[str, Environment] = {}
        self._current: str = "development"

    def register(self, env: type[Environment]) -> None:
        """Register an environment class."""
        instance = env()
        self._environments[env.name] = instance

    def get(self, name: str) -> Environment | None:
        """Get an environment by name."""
        return self._environments.get(name)

    def get_all(self) -> dict[str, Environment]:
        """Get all registered environments."""
        return self._environments.copy()

    def get_choices(self) -> list[str]:
        """Get list of available environment names."""
        return list(self._environments.keys())

    def set_current(self, name: str) -> None:
        """Set the current environment."""
        if name not in self._environments:
            raise ValueError(f"Unknown environment: {name}")
        self._current = name
        os.environ["QK_ENV"] = name

    def get_current(self) -> str:
        """Get the current environment name."""
        return os.environ.get("QK_ENV", self._current)

    def get_current_env(self) -> Environment | None:
        """Get the current environment object."""
        return self._environments.get(self.get_current())

    @classmethod
    def _default_entries(cls) -> tuple[type[Environment], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            DevelopmentEnvironment,
            StagingEnvironment,
            ProductionEnvironment,
            TestEnvironment,
        )

    @classmethod
    def with_defaults(cls) -> EnvironmentRegistry:
        """Return an instance populated with the built-in environments."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


class EnvironmentManager:
    """Manages environment switching and validation."""

    def __init__(self) -> None:
        self.registry = EnvironmentRegistry.with_defaults()

    def switch(self, name: str) -> bool:
        """Switch to a different environment."""
        env = self.registry.get(name)
        if not env:
            return False

        valid, _message = env.validate()
        if not valid:
            return False

        self.registry.set_current(name)
        return True

    def validate_current(self) -> tuple[bool, str]:
        """Validate the current environment."""
        env = self.registry.get_current_env()
        if not env:
            return False, "No current environment"
        return env.validate()

    def get_config(self) -> EnvironmentConfig | None:
        """Get configuration for current environment."""
        env = self.registry.get_current_env()
        if env:
            return env.get_config()
        return None


__all__ = [
    "DevelopmentEnvironment",
    "Environment",
    "EnvironmentConfig",
    "EnvironmentManager",
    "EnvironmentRegistry",
    "ProductionEnvironment",
    "StagingEnvironment",
    "TestEnvironment",
]
