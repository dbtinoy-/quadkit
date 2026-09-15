"""Tenancy domain exception classes."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import DomainError


class TenantError(DomainError):
    """Base class for all tenancy-related domain errors."""

    _code = "QK_ERR_TENANT_001"

    def __init__(self, message: str = "Tenant error", **kwargs: Any) -> None:
        """Initialise a TenantError.

        Args:
            message: Human-readable description of the error.
            **kwargs: Additional context forwarded to the base class.
        """
        super().__init__(message, **kwargs)


class TenantNotFoundError(TenantError):
    """Raised when a requested tenant does not exist."""

    _code = "QK_ERR_TENANT_002"

    def __init__(self, tenant_id: str = "", **kwargs: Any) -> None:
        """Initialise a TenantNotFoundError.

        Args:
            tenant_id: The tenant identifier that was not found.
            **kwargs: Additional context forwarded to the base class.
        """
        msg = f"Tenant not found: {tenant_id}" if tenant_id else "Tenant not found"
        super().__init__(msg, **kwargs)


class TenantInactiveError(TenantError):
    """Raised when an operation is attempted on an inactive tenant."""

    _code = "QK_ERR_TENANT_003"

    def __init__(self, tenant_id: str = "", **kwargs: Any) -> None:
        """Initialise a TenantInactiveError.

        Args:
            tenant_id: The inactive tenant identifier.
            **kwargs: Additional context forwarded to the base class.
        """
        msg = f"Tenant is inactive: {tenant_id}" if tenant_id else "Tenant is inactive"
        super().__init__(msg, **kwargs)


class TenantProvisioningError(TenantError):
    """Raised when tenant provisioning (isolation setup) fails."""

    _code = "QK_ERR_TENANT_004"

    def __init__(
        self, message: str = "Tenant provisioning failed", **kwargs: Any
    ) -> None:
        """Initialise a TenantProvisioningError.

        Args:
            message: Human-readable description of the provisioning failure.
            **kwargs: Additional context forwarded to the base class.
        """
        super().__init__(message, **kwargs)


class TenantResolutionError(TenantError):
    """Raised when tenant resolution fails unexpectedly."""

    _code = "QK_ERR_TENANT_005"

    def __init__(
        self, message: str = "Tenant resolution failed", **kwargs: Any
    ) -> None:
        """Initialise a TenantResolutionError.

        Args:
            message: Human-readable description of the resolution failure.
            **kwargs: Additional context forwarded to the base class.
        """
        super().__init__(message, **kwargs)


class TenantConfigError(TenantError):
    """Raised when per-tenant configuration access or mutation fails."""

    _code = "QK_ERR_TENANT_006"

    def __init__(self, message: str = "Tenant config error", **kwargs: Any) -> None:
        """Initialise a TenantConfigError.

        Args:
            message: Human-readable description of the config error.
            **kwargs: Additional context forwarded to the base class.
        """
        super().__init__(message, **kwargs)


class TenantSlugConflictError(TenantError):
    """Raised when a tenant slug is already in use."""

    _code = "QK_ERR_TENANT_007"

    def __init__(self, slug: str = "", **kwargs: Any) -> None:
        """Initialise a TenantSlugConflictError.

        Args:
            slug: The conflicting tenant slug.
            **kwargs: Additional context forwarded to the base class.
        """
        msg = f"Tenant slug already in use: {slug}" if slug else "Tenant slug conflict"
        super().__init__(msg, **kwargs)


class TenantSuspendedError(TenantError):
    """Raised when an operation is attempted on a suspended tenant."""

    _code = "QK_ERR_TENANT_008"

    def __init__(self, tenant_id: str = "", **kwargs: Any) -> None:
        """Initialise a TenantSuspendedError.

        Args:
            tenant_id: The suspended tenant identifier.
            **kwargs: Additional context forwarded to the base class.
        """
        msg = (
            f"Tenant is suspended: {tenant_id}" if tenant_id else "Tenant is suspended"
        )
        super().__init__(msg, **kwargs)


class MigrationError(TenantError):
    """Raised when a tenant tier migration fails."""

    _code = "QK_ERR_TENANT_009"

    def __init__(self, message: str = "Tenant migration failed", **kwargs: Any) -> None:
        """Initialise a MigrationError.

        Args:
            message: Human-readable description of the migration failure.
            **kwargs: Additional context forwarded to the base class.
        """
        super().__init__(message, **kwargs)


__all__ = [
    "MigrationError",
    "TenantConfigError",
    "TenantError",
    "TenantInactiveError",
    "TenantNotFoundError",
    "TenantProvisioningError",
    "TenantResolutionError",
    "TenantSlugConflictError",
    "TenantSuspendedError",
]
