"""Event and Snapshot stores for CQRS event sourcing.

This module provides various store implementations:
- InMemoryEventStore: For testing and development
- InMemorySnapshotStore: For testing and development
- SqliteEventStore: Lightweight file-based or in-memory storage (optional)
- PostgresEventStore: Production-grade PostgreSQL store (optional)
- MongoDBEventStore: Production-grade MongoDB store (optional)

Key classes:
- AbstractEventStore: Abstract base for event storage
- AbstractSnapshotStore: Abstract base for snapshot storage
- SnapshotManager: Manages snapshot creation with policies
"""

from __future__ import annotations

from quadkit.events.stores.base import (
    AbstractEventStore,
    AbstractSnapshotStore,
    StoredEvent,
)
from quadkit.events.stores.memory import InMemoryEventStore, InMemorySnapshotStore
from quadkit.events.stores.outbox import (
    OutboxEntry,
    OutboxEntryStatus,
    OutboxEventStore,
    OutboxPublisher,
)
from quadkit.events.stores.snapshot import (
    CompositePolicy,
    EventCountPolicy,
    SnapshotManager,
    SnapshotPolicy,
    TimeBasedPolicy,
)

# Optional imports for database-backed stores
try:
    from quadkit.events.stores.sqlite import (
        SqliteConfig,
        SqliteEventStore,
        SqliteSnapshotStore,
    )

    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False

try:
    from quadkit.events.stores.postgres import (
        PostgresEventStore,
        PostgresEventStoreConfig,
        PostgresSnapshotStore,
    )

    HAS_POSTGRES = True
except ImportError:
    PostgresEventStoreConfig = None  # type: ignore[misc,assignment]
    PostgresEventStore = None  # type: ignore[misc,assignment]
    PostgresSnapshotStore = None  # type: ignore[misc,assignment]
    HAS_POSTGRES = False

try:
    from quadkit.events.stores.mongodb import (
        MongoDBConfig,
        MongoDBEventStore,
        MongoDBSnapshotStore,
    )

    HAS_MONGODB = True
except ImportError:
    HAS_MONGODB = False

try:
    from quadkit.events.stores.redis import RedisEventStore

    HAS_REDIS = True
except ImportError:
    RedisEventStore = None  # type: ignore[assignment,misc]
    HAS_REDIS = False


__all__ = [
    "HAS_MONGODB",
    "HAS_POSTGRES",
    "HAS_REDIS",
    "HAS_SQLITE",
    "AbstractEventStore",
    "AbstractSnapshotStore",
    "CompositePolicy",
    "EventCountPolicy",
    "InMemoryEventStore",
    "InMemorySnapshotStore",
    "OutboxEntry",
    "OutboxEntryStatus",
    "OutboxEventStore",
    "OutboxPublisher",
    "SnapshotManager",
    "SnapshotPolicy",
    "TimeBasedPolicy",
]

# Conditionally add optional exports
if HAS_SQLITE:
    __all__.extend(["SqliteConfig", "SqliteEventStore", "SqliteSnapshotStore"])

if HAS_POSTGRES:
    __all__.extend(
        ["PostgresEventStore", "PostgresEventStoreConfig", "PostgresSnapshotStore"]
    )

if HAS_MONGODB:
    __all__.extend(["MongoDBConfig", "MongoDBEventStore", "MongoDBSnapshotStore"])

if HAS_REDIS:
    __all__.extend(["RedisEventStore"])
