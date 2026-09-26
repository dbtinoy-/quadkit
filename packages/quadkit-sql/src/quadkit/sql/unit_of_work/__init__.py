"""Unit of Work pattern for SQL transaction management.

This is the **canonical** Unit of Work implementation for ``quadkit-sql``.

Choose the right class for your use-case
-----------------------------------------
:class:`SimpleUnitOfWork`
    Accumulates entity operations (insert / update / delete) in memory and
    flushes them inside a single database transaction on ``commit()``.  Use
    this when you need explicit, deferred flushing semantics — for example
    when building domain-driven aggregates or when the set of operations is
    determined incrementally.

:func:`transaction` / :class:`SimpleTransactionManager`
    Thin helpers that demarcate a database transaction without the
    full UoW bookkeeping.  Prefer these for simple, co-located query blocks
    where you just need ``BEGIN`` / ``COMMIT`` / ``ROLLBACK`` semantics.

:class:`IdentityMap`
    First-level cache keyed by ``(type, pk)``.  Used internally by
    :class:`SimpleUnitOfWork` and :class:`~quadkit.sql.managers.ScopedUnitOfWork`
    to avoid duplicate loads within the same transaction scope.

.. seealso::
    :mod:`quadkit.sql.managers` — scoped connection + UoW integration built
    on top of :class:`DatabaseManager`.
"""

from __future__ import annotations

from quadkit.sql.unit_of_work.decorators import transactional
from quadkit.sql.unit_of_work.identity_map import (
    EntityChange,
    EntitySnapshot,
    IdentityMap,
)
from quadkit.sql.unit_of_work.manager import (
    SimpleTransactionManager,
    transaction,
)
from quadkit.sql.unit_of_work.simple import SimpleUnitOfWork, unit_of_work

__all__ = [
    "EntityChange",
    "EntitySnapshot",
    "IdentityMap",
    "SimpleTransactionManager",
    "SimpleUnitOfWork",
    "transaction",
    "transactional",
    "unit_of_work",
]
