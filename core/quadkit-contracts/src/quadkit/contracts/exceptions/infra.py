"""Infrastructure-related exception classes."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError


class InfrastructureError(QuadkitError):
    """System-level failures (DB down, network timeouts)."""

    _code = "QK_ERR_INFRA_001"

    def __init__(self, message: str = "Infrastructure error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class CollidingFileError(InfrastructureError):
    """A generated file collides with an existing file under a FAIL policy."""

    _code = "QK_ERR_CODEGEN_001"

    def __init__(
        self, message: str = "Generated file collision", **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)


class DatabaseError(InfrastructureError):
    """Database-related error (infrastructure-level)."""

    _code = "QK_ERR_DB_001"

    def __init__(self, message: str = "Database error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class MigrationError(InfrastructureError):
    """Database migration error."""

    _code = "QK_ERR_DB_002"

    def __init__(self, message: str = "Migration error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class LockError(InfrastructureError):
    """Distributed lock error."""

    _code = "QK_ERR_INFRA_002"

    def __init__(self, message: str = "Lock error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class LockConflictError(LockError):
    """Raised when a lock conflict occurs (resource already locked)."""

    _code = "QK_ERR_INFRA_003"

    def __init__(
        self,
        resource: str,
        owner: str | None = None,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        if message is None:
            message = f"Lock conflict on '{resource}'"
            if owner:
                message += f" (held by: {owner})"

        super().__init__(
            message,
            details={"resource": resource, "owner": owner},
            **kwargs,
        )
        self.resource = resource
        self.owner = owner


class RegistryError(QuadkitError):
    """Base exception for registry errors."""

    _code = "QK_ERR_REG_001"

    def __init__(self, message: str = "Registry error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class RegistryKeyError(RegistryError, KeyError):
    """Raised when a key is not found in a registry."""

    _code = "QK_ERR_REG_002"

    def __init__(self, message: str = "Key not found", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class RegistryAlreadyExistsError(RegistryError):
    """Raised when attempting to register a duplicate key in a registry."""

    _code = "QK_ERR_REG_003"

    def __init__(self, message: str = "Key already exists", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class IntegrityError(DatabaseError):
    """Raised when a database integrity constraint is violated."""

    _code = "QK_ERR_DB_003"

    def __init__(
        self, message: str = "Integrity constraint violated", **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)


class ConstraintError(IntegrityError):
    """Raised when a generic database constraint is violated."""

    _code = "QK_ERR_DB_004"

    def __init__(self, message: str = "Constraint violated", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class DuplicateKeyError(ConstraintError):
    """Raised when a unique-key constraint is violated (duplicate record)."""

    _code = "QK_ERR_DB_005"

    def __init__(self, message: str = "Duplicate key", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class NoPrimaryBackendError(DatabaseError):
    """Raised when a multi-backend setup has no backend marked as primary.

    For multi-backend SQL configurations, exactly one backend must be marked
    with primary: true. This error is raised when no backend is marked primary.
    """

    _code = "QK_ERR_DB_011"


__all__ = [
    "ConstraintError",
    "DatabaseError",
    "DuplicateKeyError",
    "InfrastructureError",
    "IntegrityError",
    "LockConflictError",
    "LockError",
    "MigrationError",
    "NoPrimaryBackendError",
    "RegistryAlreadyExistsError",
    "RegistryError",
    "RegistryKeyError",
]
