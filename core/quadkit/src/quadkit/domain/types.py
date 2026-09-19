"""Domain-level type aliases.

Provides shared type aliases used across the domain layer. Keeping them
here avoids reaching into ``core.typing`` from domain code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from quadkit.contracts.domain import DomainEvent

DomainEventType: TypeAlias = "type[DomainEvent]"
"""Type alias for any concrete DomainEvent class."""

__all__ = ["DomainEventType"]
