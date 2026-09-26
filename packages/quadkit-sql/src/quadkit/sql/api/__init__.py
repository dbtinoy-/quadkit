"""Public API interfaces for quadkit-sql (stubs).

These are lightweight typed interface stubs and small helper classes used by
consumers and by tests. They are intentionally minimal and async-first.
"""

from __future__ import annotations

# QueryEngine
from quadkit.sql.api.engine import QueryEngine

# Protocols
from quadkit.sql.api.protocols import (
    ConnectionProtocol,
    DatabaseProviderProtocol,
    UnitOfWorkProtocol,
)

# Re-export exceptions from consolidated exceptions module
from quadkit.sql.exceptions import (
    DatabaseError,
    IntegrityError,
    TransactionError,
)

# Migration APIs re-export
from quadkit.sql.migrations.api import (
    create_migration,
    init_migrations,
    migrate_down,
    migrate_down_dry_run,
    migrate_up,
    migrate_up_dry_run,
    rollback_migrations,
    rollback_to_revision,
    validate_migrations,
)

__all__ = [
    # Protocols
    "ConnectionProtocol",
    # Exceptions
    "DatabaseError",
    "DatabaseProviderProtocol",
    "IntegrityError",
    # Classes
    "QueryEngine",
    "TransactionError",
    "UnitOfWorkProtocol",
    # Migration APIs
    "create_migration",
    "init_migrations",
    "migrate_down",
    "migrate_down_dry_run",
    "migrate_up",
    "migrate_up_dry_run",
    "rollback_migrations",
    "rollback_to_revision",
    "validate_migrations",
]
