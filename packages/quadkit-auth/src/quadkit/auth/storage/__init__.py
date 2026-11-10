"""Storage — user, token, session and MFA persistence backends.

Persistence classification (what survives an application restart):

==============================  =========================================
Surface                         Classification
==============================  =========================================
Identity/credentials            **Persistent** when the user store is
(``UserStoreProtocol``)         ``SQLUserStore``/``MongoDBUserStore``;
                                **ephemeral** with ``InMemoryUserStore``
                                (the dev/test default). ``RedisUserStore``
                                is a read-through cache, never the primary.
JWT access tokens               **Stateless** (signed, self-contained);
                                revocation rides the token blacklist,
                                durable only when a cache backend is bound.
Server-side sessions            **Ephemeral by default**
(``SessionStore``)              (``InMemorySessionStore``); persistent
                                only when the application binds its own
                                ``SessionStore`` implementation.
MFA challenges/secrets          **Ephemeral** default
(``MFAStore``)                  (``InMemoryMFAStore``).
OAuth identities                **Persistent**
(``oauth_identity_store``)      (``SQLAlchemyOAuthIdentityStore`` owns
                                its table; it references the default
                                ``users`` table name).
API keys                        **Persistent** (``APIKeySqlRepository``).
==============================  =========================================

The framework's persistence claim is for identity/credentials through
the selected user store. Do not market server-side session persistence
unless the composition actually binds a persistent ``SessionStore``.
"""

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
from quadkit.auth.storage.sql_sessions import SQLSessionStore
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
    "SQLSessionStore",
    "SQLUserStore",
    "SessionStore",
    "UserStoreProtocol",
]
