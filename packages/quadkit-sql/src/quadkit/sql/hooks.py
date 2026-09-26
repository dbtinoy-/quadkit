"""Root hook payload surface for quadkit-sql.

Defines canonical payload dataclasses for database connection and transaction
hook points. Actual hook registration and invocation use the framework's
string-keyed ``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "SQLConnectionReadyHook",
    "SQLTransactionBegunHook",
    "SQLTransactionEndedHook",
]


@dataclass(frozen=True, kw_only=True)
class SQLConnectionReadyHook:
    """Payload fired when the SQL connection pool is initialised and ready.

    Attributes:
        backend: Database backend identifier (e.g. ``"postgresql"``).
    """

    backend: str


@dataclass(frozen=True, kw_only=True)
class SQLTransactionBegunHook:
    """Payload fired when a database transaction begins."""


@dataclass(frozen=True, kw_only=True)
class SQLTransactionEndedHook:
    """Payload fired when a database transaction completes (commit or rollback).

    Attributes:
        committed: ``True`` if the transaction was committed; ``False`` if rolled back.
    """

    committed: bool
