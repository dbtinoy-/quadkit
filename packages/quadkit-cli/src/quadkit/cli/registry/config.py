"""Config validators registry for configuration validation.

This module provides a registry pattern for validating configuration
settings and checking for common issues.
"""

from __future__ import annotations

import abc
from enum import Enum
import os
import re
from typing import Any

from quadkit.contracts.core.config import ConfigIssue


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ``ValidationIssue`` is now backed by the contracts ``ConfigIssue``.
# The alias preserves backwards-compatibility for code that still
# references ``ValidationIssue`` directly.
ValidationIssue = ConfigIssue


class ConfigValidator(abc.ABC):
    """Abstract base class for configuration validators."""

    @abc.abstractmethod
    def validate(
        self,
        config: dict[str, Any],
        env: str = "development",
    ) -> list[ValidationIssue]:
        """Validate the configuration and return a list of issues."""

    @abc.abstractmethod
    def get_name(self) -> str:
        """Get the name of this validator."""


class RequiredFieldsValidator(ConfigValidator):
    """Check for required configuration fields."""

    REQUIRED_FIELDS: dict[str, list[str]] = {}

    def get_name(self) -> str:
        return "Required Fields"

    def validate(
        self,
        config: dict[str, Any],
        env: str = "development",
    ) -> list[ValidationIssue]:
        issues = []

        for section, fields in self.REQUIRED_FIELDS.items():
            if section not in config:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        field=section,
                        message=f"Missing required section: {section}",
                        suggestion=f"Add '{section}' section to application.yaml",
                    ),
                )
                continue

            section_data = config[section]
            if not isinstance(section_data, dict):
                continue

            for field_name in fields:
                if field_name not in section_data:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            field=f"{section}.{field_name}",
                            message=f"Missing required field: {section}.{field_name}",
                            suggestion=f"Add '{field_name}' to the {section} section",
                        ),
                    )

        return issues


class SecretValidationValidator(ConfigValidator):
    """Validate that secrets are properly configured."""

    SECRET_FIELDS = ["secret", "password", "key", "token", "api_key", "api-key"]

    def get_name(self) -> str:
        return "Secrets"

    def validate(
        self,
        config: dict[str, Any],
        env: str = "development",
    ) -> list[ValidationIssue]:
        issues = []

        def check_value(path: str, value: Any) -> None:
            if isinstance(value, dict):
                for k, v in value.items():
                    field_lower = k.lower()
                    if any(s in field_lower for s in self.SECRET_FIELDS) and not v:
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                field=f"{path}.{k}",
                                message=f"Empty secret value for {path}.{k}",
                                suggestion="Set a secure secret value",
                            ),
                        )
                    check_value(f"{path}.{k}", v)
            elif isinstance(value, str):
                # Placeholder detection on the secret's own value (the path's
                # last segment is the field name).
                field_lower = path.rsplit(".", 1)[-1].lower()
                if any(s in field_lower for s in self.SECRET_FIELDS) and any(
                    placeholder in value.lower()
                    for placeholder in [
                        "your-",
                        "change-me",
                        "changeme",
                        "password",
                        "placeholder",
                        "xxx",
                    ]
                ):
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            field=path,
                            message=f"Default/placeholder secret detected for {path}",
                            suggestion="Set a production-ready secret value",
                        ),
                    )
                matches = re.findall(r"\$\{([^}:]+)(?::[^}]*)?\}", value)
                for var in matches:
                    if not os.environ.get(var):
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                field=path,
                                message=f"Environment variable {var} is not set",
                                suggestion=f"Set {var} environment variable or provide a default value",
                            ),
                        )

        for section, data in config.items():
            check_value(section, data)

        return issues


class ProductionValidator(ConfigValidator):
    """Validate production-specific configuration."""

    def get_name(self) -> str:
        return "Production Settings"

    def validate(
        self,
        config: dict[str, Any],
        env: str = "development",
    ) -> list[ValidationIssue]:
        if env != "production":
            return []

        issues = []

        if "web" in config:
            web = config["web"]
            if isinstance(web, dict):
                debug = web.get("debug", False)
                if debug:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            field="web.debug",
                            message="Debug mode is enabled in production",
                            suggestion="Set web.debug to false for production",
                        ),
                    )

        if "database" in config:
            db = config["database"]
            if isinstance(db, dict):
                url = db.get("url", "")
                if "localhost" in url or "127.0.0.1" in url:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            field="database.url",
                            message="Database URL points to localhost in production",
                            suggestion="Use a remote database for production",
                        ),
                    )

        return issues


class DatabaseConfigValidator(ConfigValidator):
    """Validate database configuration."""

    def get_name(self) -> str:
        return "Database"

    def validate(
        self,
        config: dict[str, Any],
        env: str = "development",
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if "database" not in config:
            return issues

        db = config["database"]
        if not isinstance(db, dict):
            return issues

        url = db.get("url", "")
        if not url:
            issues.append(
                ValidationIssue(
                    severity="error",
                    field="database.url",
                    message="database.url is required",
                    suggestion="Set database.url in application.yaml or DATABASE_URL env var",
                ),
            )
            return issues

        if url.startswith("sqlite"):
            path = url.replace("sqlite:///", "")
            if path == ":memory:":
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        field="database.url",
                        message="Using in-memory SQLite database",
                        suggestion="Use file-based SQLite or another database for persistent storage",
                    ),
                )

        return issues


class AuthConfigValidator(ConfigValidator):
    """Validate authentication configuration."""

    def get_name(self) -> str:
        return "Authentication"

    def validate(
        self,
        config: dict[str, Any],
        env: str = "development",
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if "auth" not in config:
            return issues

        auth = config["auth"]
        if not isinstance(auth, dict):
            return issues

        enabled = auth.get("enabled", False)
        if not enabled:
            return issues

        if "secret" not in auth or not auth["secret"]:
            issues.append(
                ValidationIssue(
                    severity="error",
                    field="auth.secret",
                    message="Auth is enabled but no secret is configured",
                    suggestion="Set auth.secret to a secure value",
                ),
            )

        return issues


class EnvironmentVariablesValidator(ConfigValidator):
    """Check for missing environment variables."""

    def get_name(self) -> str:
        return "Environment Variables"

    def validate(
        self,
        config: dict[str, Any],
        env: str = "development",
    ) -> list[ValidationIssue]:
        issues = []

        env_vars: set[str] = set()

        def find_vars(obj: Any) -> None:
            if isinstance(obj, dict):
                for v in obj.values():
                    find_vars(v)
            elif isinstance(obj, str):
                matches = re.findall(r"\$\{([^}:]+)(?::[^}]*)?\}", obj)
                env_vars.update(matches)

        find_vars(config)

        for var in env_vars:
            if var not in os.environ:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        field="env",
                        message=f"Environment variable {var} is not set",
                        suggestion=f"Set {var} or provide a default value in application.yaml",
                    ),
                )

        return issues


class ConfigValidatorRegistry:
    """Registry for configuration validators.

    Provides a pluggable way to add new validators.
    """

    def __init__(self) -> None:
        self._validators: list[type[ConfigValidator]] = []

    def register(self, validator: type[ConfigValidator]) -> None:
        """Register a validator class."""
        self._validators.append(validator)

    def get_all_validators(self) -> list[type[ConfigValidator]]:
        """Get all registered validator classes."""
        return self._validators.copy()

    @classmethod
    def _default_entries(cls) -> tuple[type[ConfigValidator], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            RequiredFieldsValidator,
            SecretValidationValidator,
            ProductionValidator,
            DatabaseConfigValidator,
            AuthConfigValidator,
            EnvironmentVariablesValidator,
        )

    @classmethod
    def with_defaults(cls) -> ConfigValidatorRegistry:
        """Return an instance populated with the built-in validators."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


def validate_config(
    config: dict[str, Any],
    env: str = "development",
) -> dict[str, list[ValidationIssue]]:
    """Run all validators and return issues organized by validator name."""
    validators = ConfigValidatorRegistry.with_defaults().get_all_validators()
    results: dict[str, list[ValidationIssue]] = {}

    for validator_class in validators:
        try:
            validator = validator_class()
            issues = validator.validate(config, env)
            results[validator.get_name()] = issues
        except Exception as e:  # noqa: BLE001 — validator failures are recorded as errors
            results[validator_class().get_name()] = [
                ValidationIssue(
                    severity="error",
                    field="",
                    message=f"Validator failed: {e}",
                ),
            ]

    return results


def has_errors(results: dict[str, list[ValidationIssue]]) -> bool:
    """Check if any results contain errors."""
    for issues in results.values():
        for issue in issues:
            if issue.severity == "error":
                return True
    return False


__all__ = [
    "AuthConfigValidator",
    "ConfigIssue",
    "ConfigValidator",
    "ConfigValidatorRegistry",
    "DatabaseConfigValidator",
    "EnvironmentVariablesValidator",
    "ProductionValidator",
    "RequiredFieldsValidator",
    "SecretValidationValidator",
    "ValidationIssue",
    "ValidationSeverity",
    "has_errors",
    "validate_config",
]
