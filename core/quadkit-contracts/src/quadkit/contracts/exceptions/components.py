"""Consolidated component exceptions.

These exceptions inherit from the canonical Quadkit hierarchy but provide
component-specific context where needed.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions import (
    ConflictError,
    InfrastructureError,
    LockError,
    NotFoundError,
    QuadkitError,
)


class ComponentError(QuadkitError):
    """Base exception for all component-related errors."""

    _code = "QK_ERR_INFRA_004"

    def __init__(
        self,
        message: str,
        component_type: str | None = None,
        driver_type: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        details = details or {}
        if component_type:
            details["component_type"] = component_type
        if driver_type:
            details["driver_type"] = driver_type

        super().__init__(message, details=details, **kwargs)
        self.component_type = component_type
        self.driver_type = driver_type


class ComponentConnectionError(InfrastructureError, ComponentError):
    """Raised when a connection to an external service fails."""

    _code = "QK_ERR_INFRA_005"

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class KeyNotFoundError(NotFoundError, ComponentError):
    """Raised when a requested key does not exist."""

    _code = "QK_ERR_INFRA_006"

    def __init__(self, key: str, **kwargs: Any) -> None:
        super().__init__(f"Key not found: {key}", **kwargs)
        self.key = key


class KeyExistsError(ConflictError, ComponentError):
    """Raised when trying to create a key that already exists."""

    _code = "QK_ERR_INFRA_007"

    def __init__(self, key: str, **kwargs: Any) -> None:
        super().__init__(f"Key already exists: {key}", **kwargs)
        self.key = key


class PubSubError(InfrastructureError, ComponentError):
    """Base exception for pub/sub operations."""

    _code = "QK_ERR_INFRA_008"

    def __init__(self, message: str, topic: str | None = None, **kwargs: Any) -> None:
        details = kwargs.get("details", {})
        if topic:
            details["topic"] = topic
        super().__init__(message, details=details, **kwargs)
        self.topic = topic


class SecretNotFoundError(NotFoundError, ComponentError):
    """Raised when a requested secret does not exist."""

    _code = "QK_ERR_INFRA_009"

    def __init__(self, secret_name: str, **kwargs: Any) -> None:
        super().__init__(
            f"Secret not found: {secret_name}",
            **kwargs,
        )
        self.secret_name = secret_name


class LockAcquisitionError(LockError, ComponentError):
    """Raised when acquiring a lock fails."""

    _code = "QK_ERR_LOCK_001"

    def __init__(self, resource: str, message: str = "", **kwargs: Any) -> None:
        super().__init__(
            f"Failed to acquire lock on '{resource}': {message}",
            **kwargs,
        )
        self.resource = resource


class LockNotHeldError(LockError, ComponentError):
    """Raised when trying to operate on a lock that is not held."""

    _code = "QK_ERR_LOCK_002"

    def __init__(self, resource: str, **kwargs: Any) -> None:
        super().__init__(f"Lock not held: {resource}", **kwargs)
        self.resource = resource


class LockOwnershipError(LockError, ComponentError):
    """Raised when trying to release or extend a lock held by another owner."""

    _code = "QK_ERR_LOCK_003"

    def __init__(self, resource: str, **kwargs: Any) -> None:
        super().__init__(f"Lock held by another owner: {resource}", **kwargs)
        self.resource = resource


class DriverNotAvailableError(ComponentError):
    """Raised when a driver is not available (dependency not installed)."""

    _code = "QK_ERR_INFRA_010"

    def __init__(self, driver_type: str, install_hint: str = "", **kwargs: Any) -> None:
        super().__init__(
            f"Driver not available: {driver_type}. Install with: {install_hint}",
            **kwargs,
        )
        self.driver_type = driver_type
        self.install_hint = install_hint


__all__ = [
    "ComponentConnectionError",
    "ComponentError",
    "DriverNotAvailableError",
    "KeyExistsError",
    "KeyNotFoundError",
    "LockAcquisitionError",
    "LockNotHeldError",
    "LockOwnershipError",
    "PubSubError",
    "SecretNotFoundError",
]
