"""Aggregates module for Domain-Driven Design.

This module provides:
- AggregateRoot: Base class for event-sourced aggregates
- Entity: Base class for entities within aggregates
- ValueObject: Base class for immutable value objects
"""

from __future__ import annotations

from quadkit.events.aggregates.aggregate import AggregateRoot, VersionedAggregateRoot
from quadkit.events.aggregates.entity import Entity, VersionedEntity
from quadkit.events.aggregates.value_object import SingleValueObject, ValueObject

__all__ = [
    "AggregateRoot",
    "Entity",
    "SingleValueObject",
    "ValueObject",
    "VersionedAggregateRoot",
    "VersionedEntity",
]
