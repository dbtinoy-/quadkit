"""Scoped connection and Unit of Work manager for quadkit-sql.

This package provides higher-level transaction coordination built on top of
:class:`~quadkit.contracts.DatabaseProviderProtocol`.

Class overview
--------------
:class:`DatabaseManager`
    Owns the provider lifecycle, exposes ``scoped_session()`` context-manager,
    and creates :class:`ScopedUnitOfWork` instances bound to the active
    scoped connection.  This is the **entry point** for all database access
    in application code.

:class:`ScopedUnitOfWork`
    Implements :class:`~quadkit.contracts.UnitOfWorkProtocol` using the
    scoped connection managed by :class:`DatabaseManager`.  Provides
    ``register_new``, ``register_dirty``, and ``register_deleted`` for
    change-tracking, backed by an :class:`~quadkit.sql.unit_of_work.IdentityMap`.

Relationship to ``quadkit.sql.unit_of_work``
--------------------------------------------
:mod:`quadkit.sql.unit_of_work` contains the standalone
:class:`~quadkit.sql.unit_of_work.SimpleUnitOfWork` that does *not* use
a :class:`DatabaseManager`; it accepts a raw provider and is suited for
one-shot scripts and tests that manage connections themselves.

For application code that is wired via DI, prefer :class:`DatabaseManager`
from this package.
"""

from __future__ import annotations

from quadkit.sql.managers.manager import (
    DatabaseManager,
    ScopedUnitOfWork,
)

__all__ = [
    "DatabaseManager",
    "ScopedUnitOfWork",
]
