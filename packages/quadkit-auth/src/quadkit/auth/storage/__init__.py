"""Storage — user, token, session and MFA persistence backends."""

from __future__ import annotations

from quadkit.auth.storage.apikey_sql import APIKeySqlRepository
from quadkit.auth.storage.db_stores import (
    MongoDBUserStore,
    RedisUserStore,
    SQLUserStore,
)
from quadkit.auth.storage.in_memory_stores import (
    InMemoryMFAStore,
    InMemorySessionStore,
)
from quadkit.auth.storage.session_store import (
    MFAStore,
    SessionStore,
)
from quadkit.auth.storage.token_store import (
    CachedUserStore,
    InMemoryUserStore,
    UserStoreProtocol,
)

__all__ = [
    "APIKeySqlRepository",
    "CachedUserStore",
    "InMemoryMFAStore",
    "InMemorySessionStore",
    "InMemoryUserStore",
    "MFAStore",
    "MongoDBUserStore",
    "RedisUserStore",
    "SQLUserStore",
    "SessionStore",
    "UserStoreProtocol",
]
