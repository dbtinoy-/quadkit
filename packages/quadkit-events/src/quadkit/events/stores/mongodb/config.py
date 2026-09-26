"""MongoDB store-level connection configuration.

This config is used by :class:`~quadkit.events.stores.mongodb.MongoDBSnapshotStore`
for direct motor connection management.

For the top-level user-facing event store config (used with :class:`~quadkit.events.config.EventsConfig`),
see :class:`quadkit.events.config.MongoDBEventStoreConfig`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.validation import ConfigDict, Field, SecretStr


@dataclass(init=False)
class MongoDBConfig(BaseConfig):
    """MongoDB connection configuration for store implementations.

    Used directly by :class:`~quadkit.events.stores.mongodb.MongoDBSnapshotStore`
    for motor connection lifecycle management.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    uri: SecretStr = Field(..., description="MongoDB connection URI")
    database: str = Field(default="events")
    events_collection: str = Field(default="events")
    snapshots_collection: str = Field(default="snapshots")
    counters_collection: str = Field(default="counters")
    max_pool_size: int = Field(default=100, ge=1)
    auto_create_indexes: bool = True


__all__ = ["MongoDBConfig"]
