"""Container and dependency injection exception classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError


class ContainerError(QuadkitError):
    """Base container error."""

    _code = "QK_ERR_DI_001"

    def __init__(self, message: str = "Container error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class DependencyError(ContainerError):
    """Dependency resolution error."""

    _code = "QK_ERR_DI_002"

    def __init__(self, message: str = "Dependency error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class CircularDependencyError(DependencyError):
    """Circular dependency detected."""

    _code = "QK_ERR_DI_003"

    def __init__(
        self,
        message: str = "Circular dependency detected",
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault(
            "hint",
            "Check constructor parameters of the classes in the cycle for mutual references.",
        )
        super().__init__(message, **kwargs)


class UnresolvableDependencyError(DependencyError):
    """Cannot resolve dependency."""

    _code = "QK_ERR_DI_004"

    def __init__(
        self,
        message: str = "Cannot resolve dependency",
        dependency: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if dependency:
            details["dependency"] = dependency
        kwargs["details"] = details
        kwargs.setdefault(
            "hint",
            "Verify the type is registered in a Provider and all its dependencies are resolvable.",
        )
        super().__init__(message, **kwargs)


class RegistrationError(ContainerError):
    """Service registration error."""

    _code = "QK_ERR_DI_005"

    def __init__(self, message: str = "Registration error", **kwargs: Any) -> None:
        kwargs.setdefault(
            "hint",
            "Ensure the service is registered in a Provider.register() before the container boots.",
        )
        super().__init__(message, **kwargs)


class ContainerBuildError(ContainerError):
    """Container build/configuration error."""

    _code = "QK_ERR_DI_006"

    def __init__(
        self,
        message: str = "Container build error",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


class ProtocolValidationError(ContainerError):
    """Protocol validation error."""

    _code = "QK_ERR_DI_007"

    def __init__(
        self,
        message: str = "Protocol validation failed",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


class ContainerValidationError(ContainerBuildError):
    """Container dependency graph validation failed before boot.

    Raised when ``Container.validate()`` discovers issues (missing
    dependencies, circular references, scope violations) during the
    pre-boot validation phase.  The ``issues`` attribute contains the
    full list of problem descriptions.
    """

    _code = "QK_ERR_DI_008"

    def __init__(
        self,
        issues: list[str],
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.issues = issues
        formatted = "; ".join(issues)
        msg = message or f"Container validation failed: {formatted}"
        kwargs.setdefault("details", {"issues": issues})
        super().__init__(msg, **kwargs)


class ScopedResolutionError(UnresolvableDependencyError):
    """Attempted to resolve a scoped service outside of an active scope.

    Raised when a service registered with ``container.scoped()`` is resolved
    directly on the root container instead of inside a
    ``container.create_scope()`` block.
    """

    _code = "QK_ERR_DI_009"

    def __init__(
        self,
        message: str = "Cannot resolve scoped service outside of an active scope",
        service: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if service:
            details["service"] = service
        kwargs["details"] = details
        super().__init__(message, dependency=service, **kwargs)


@dataclass(frozen=True)
class OrphanedRegistration:
    """Represents a potentially orphaned service registration.

    An orphaned registration is a service that is registered in the
    container but is never depended upon by any other registered service
    and is not in the container's exports list.
    """

    service_key: str
    """The service type name or key."""

    registered_at: str
    """The location/module where the service was registered."""

    suggestion: str
    """A suggestion for resolving the orphan."""


__all__ = [
    "CircularDependencyError",
    "ContainerBuildError",
    "ContainerError",
    "ContainerValidationError",
    "DependencyError",
    "OrphanedRegistration",
    "ProtocolValidationError",
    "RegistrationError",
    "ScopedResolutionError",
    "UnresolvableDependencyError",
]
