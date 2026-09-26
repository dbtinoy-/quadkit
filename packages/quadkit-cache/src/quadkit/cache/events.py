"""Domain events for cache subsystem."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent


@dataclass(frozen=True)
class CacheHitEvent(DomainEvent):
    """Cache lookup resulted in a hit."""

    key: str
    backend: str


@dataclass(frozen=True)
class CacheMissEvent(DomainEvent):
    """Cache lookup resulted in a miss."""

    key: str
    backend: str


@dataclass(frozen=True)
class CacheEvictedEvent(DomainEvent):
    """Cache entry was evicted."""

    key: str
    backend: str
    reason: str


@dataclass(frozen=True)
class CacheConnectedEvent(DomainEvent):
    """Cache backend connection established."""

    backend: str
    host: str
