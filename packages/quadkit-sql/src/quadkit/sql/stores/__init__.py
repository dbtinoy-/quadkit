"""Database-backed store implementations for state, secrets, and locks.

These classes were previously housed in ``quadkit-cache`` as
``DatabaseBridge*`` classes but have been relocated here because they
depend on :class:`~quadkit.contracts.DatabaseProviderProtocol` — a purely
database concern — and sharing the connection pool with the rest of the
application is their defining feature.

They implement the protocols defined in
:mod:`quadkit.contracts.stores`:

- :class:`DatabaseStateStore` → :class:`~quadkit.contracts.stores.StateStoreProtocol`
- :class:`DatabaseSecretStore` → :class:`~quadkit.contracts.stores.AsyncSecretStoreProtocol`
- :class:`DatabaseLockStore`  → :class:`~quadkit.contracts.stores.LockStoreProtocol`
"""

from __future__ import annotations

from quadkit.sql.stores.locks import DatabaseLockStore
from quadkit.sql.stores.secrets import DatabaseSecretStore
from quadkit.sql.stores.state import DatabaseStateStore

__all__ = [
    "DatabaseLockStore",
    "DatabaseSecretStore",
    "DatabaseStateStore",
]
