"""Quadkit Domain — DDD domain primitives for the Quadkit Framework.

Groups the core DDD primitives — entities, value objects, and aggregate
roots — under a single cohesive package.  All types are sourced from the
``models`` subpackage and re-exported here for convenient access.

Domain primitives are pure Python with no infrastructure dependencies.
They integrate with the IoC container via :class:`DomainModule` for
graph completeness but require no provider registration.

Basic Usage::

    from quadkit.domain import Entity, ValueObject, AggregateRoot, DomainModel

    class UserId(ValueObject):
        value: str

    class User(Entity):
        name: str
        email: str

Module Structure:
    - exceptions: Domain exception hierarchy (``DomainError``, ``DomainPolicyViolationError``)
    - models: Entity, ValueObject, AggregateRoot, DomainModel primitives
    - module: ``DomainModule`` IoC registration
    - types: Domain type aliases
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.domain.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.contracts.data.exceptions import UnitOfWorkError
    from quadkit.contracts.exceptions.domain import (
        DomainError,
        FieldError,
        ValidationError,
    )
    from quadkit.domain.exceptions import DomainPolicyViolationError
    from quadkit.domain.models.aggregate import AggregateRoot
    from quadkit.domain.models.base import DomainModel
    from quadkit.domain.models.entity import ID, Entity
    from quadkit.domain.models.factory import create_model
    from quadkit.domain.models.value_object import ValueObject
    from quadkit.domain.module import DomainModule
    from quadkit.domain.unit_of_work import AbstractUnitOfWork

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # --- Module ---
    "DomainModule": ("quadkit.domain.module", "DomainModule"),
    # --- Models ---
    "DomainModel": ("quadkit.domain.models.base", "DomainModel"),
    "Entity": ("quadkit.domain.models.entity", "Entity"),
    "ID": ("quadkit.domain.models.entity", "ID"),
    "ValueObject": ("quadkit.domain.models.value_object", "ValueObject"),
    "AggregateRoot": ("quadkit.domain.models.aggregate", "AggregateRoot"),
    "create_model": ("quadkit.domain.models.factory", "create_model"),
    # --- Exceptions (sourced from contracts) ---
    "DomainError": ("quadkit.contracts.exceptions.domain", "DomainError"),
    "DomainPolicyViolationError": (
        "quadkit.domain.exceptions",
        "DomainPolicyViolationError",
    ),
    "FieldError": ("quadkit.contracts.exceptions.domain", "FieldError"),
    "ValidationError": ("quadkit.contracts.exceptions.domain", "ValidationError"),
    "UnitOfWorkError": ("quadkit.contracts.data.exceptions", "UnitOfWorkError"),
    # --- Protocols (sourced from contracts) ---
    "DomainEvent": ("quadkit.contracts.domain", "DomainEvent"),
    "EventBusProtocol": ("quadkit.contracts.events.protocols", "EventBusProtocol"),
    "RepositoryProtocol": ("quadkit.contracts.data.repository", "RepositoryProtocol"),
    "SpecificationProtocol": ("quadkit.contracts.domain", "SpecificationProtocol"),
    "UnitOfWorkProtocol": (
        "quadkit.contracts.data.sql.unit_of_work",
        "UnitOfWorkProtocol",
    ),
    # --- Unit of Work base (storage-agnostic; subclasses provide _flush) ---
    "AbstractUnitOfWork": ("quadkit.domain.unit_of_work", "AbstractUnitOfWork"),
}


def __getattr__(name: str) -> Any:
    """Lazy-load symbols on first access."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__: list[str] = [
    "ID",
    "AbstractUnitOfWork",
    "AggregateRoot",
    "DomainError",
    "DomainEvent",
    "DomainModel",
    "DomainModule",
    "DomainPolicyViolationError",
    "Entity",
    "EventBusProtocol",
    "FieldError",
    "RepositoryProtocol",
    "SpecificationProtocol",
    "UnitOfWorkError",
    "UnitOfWorkProtocol",
    "ValidationError",
    "ValueObject",
    "create_model",
]
