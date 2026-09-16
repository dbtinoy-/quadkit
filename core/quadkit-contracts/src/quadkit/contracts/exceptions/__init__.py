"""Canonical exception classes for Quadkit Framework.

This module contains the single source of truth for all framework exceptions.
All exceptions inherit from QuadkitError, ensuring isinstance checks work
across core, events, web, and all subpackages.

Architecture:
- base.py: QuadkitError (root)
- domain.py: Domain-level errors (NotFoundError, ValidationError, etc.)
- infra.py: Infrastructure errors (DatabaseError, etc.)
- container.py: DI container errors
- resilience.py: Resilience pattern errors
- provider.py: Provider/module errors
- events.py: Event bus/messaging errors
"""

from __future__ import annotations

from quadkit.contracts.exceptions.base import QuadkitError
from quadkit.contracts.exceptions.config import ConfigurationError
from quadkit.contracts.exceptions.container import (
    CircularDependencyError,
    ContainerBuildError,
    ContainerError,
    ContainerValidationError,
    DependencyError,
    ProtocolValidationError,
    RegistrationError,
    ScopedResolutionError,
    UnresolvableDependencyError,
)
from quadkit.contracts.exceptions.domain import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    FieldError,
    MappingError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    SerializationError,
    ValidationError,
    WebError,
)
from quadkit.contracts.exceptions.events import (
    DuplicateHandlerError,
    EventError,
    HandlerNotFoundError,
)
from quadkit.contracts.exceptions.execution import (
    PipelineExecutionError,
    PipelineStepError,
)
from quadkit.contracts.exceptions.feature_flags import (
    FeatureFlagError,
)
from quadkit.contracts.exceptions.idempotency import (
    DuplicateRequestError,
    IdempotencyConflictError,
    IdempotencyError,
    IdempotencyStoreError,
)
from quadkit.contracts.exceptions.infra import (
    ConstraintError,
    DatabaseError,
    DuplicateKeyError,
    InfrastructureError,
    IntegrityError,
    LockConflictError,
    LockError,
    MigrationError,
    RegistryAlreadyExistsError,
    RegistryError,
    RegistryKeyError,
)
from quadkit.contracts.exceptions.middleware import MiddlewareGuardError
from quadkit.contracts.exceptions.provider import (
    ModuleError,
    ProviderError,
)
from quadkit.contracts.exceptions.resilience import (
    BulkheadError,
    CircuitBreakerError,
    CircuitOpenError,
    FallbackError,
    ResilienceError,
    RetryError,
    RetryExhaustedError,
)
from quadkit.contracts.exceptions.security import (
    CORSViolationError,
    GuardDeniedError,
    InputSanitizationError,
    SecretAccessError,
    SecurityError,
)

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "BulkheadError",
    "CORSViolationError",
    "CircuitBreakerError",
    "CircuitOpenError",
    "CircularDependencyError",
    "ConfigurationError",
    "ConflictError",
    "ConstraintError",
    "ContainerBuildError",
    "ContainerError",
    "ContainerValidationError",
    "DatabaseError",
    "DependencyError",
    "DomainError",
    "DuplicateHandlerError",
    "DuplicateKeyError",
    "DuplicateRequestError",
    "EventError",
    "FallbackError",
    "FeatureFlagError",
    "FieldError",
    "GuardDeniedError",
    "HandlerNotFoundError",
    "IdempotencyConflictError",
    "IdempotencyError",
    "IdempotencyStoreError",
    "InfrastructureError",
    "InputSanitizationError",
    "IntegrityError",
    "LockConflictError",
    "LockError",
    "MappingError",
    "MiddlewareGuardError",
    "MigrationError",
    "ModuleError",
    "NotFoundError",
    "PermissionDeniedError",
    "PipelineExecutionError",
    "PipelineStepError",
    "ProtocolValidationError",
    "ProviderError",
    "QuadkitError",
    "RateLimitError",
    "RegistrationError",
    "RegistryAlreadyExistsError",
    "RegistryError",
    "RegistryKeyError",
    "ResilienceError",
    "RetryError",
    "RetryExhaustedError",
    "ScopedResolutionError",
    "SecretAccessError",
    "SecurityError",
    "SerializationError",
    "UnresolvableDependencyError",
    "ValidationError",
    "WebError",
]
