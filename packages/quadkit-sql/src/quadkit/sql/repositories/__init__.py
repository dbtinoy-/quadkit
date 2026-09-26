"""RepositoryProtocol pattern implementations.

**Database error strategy (D13.1)**

Repositories follow a layered error policy:

+-------------------------------+-------------------------------------------+
| Situation                     | Return                                    |
+===============================+===========================================+
| Record not found (expected)   | ``None`` (``find_*`` methods)             |
+-------------------------------+-------------------------------------------+
| Record must exist (required)  | ``Result[T, NotFoundError]``              |
|                               | (``get_*`` methods)                       |
+-------------------------------+-------------------------------------------+
| Infrastructure failure        | Raise infrastructure exception            |
| (connection down, timeout …)  | — never wrap in ``Result``                |
+-------------------------------+-------------------------------------------+

The same convention applies to all repository implementations and their
callers.  This ensures that:

* ``find_by_id(id)`` returns ``T | None`` — the caller handles absence.
* ``get_by_id(id)`` returns ``Result[T, NotFoundError]`` — the caller handles
  "must exist" semantics without exception handling.
* :class:`~quadkit.sql.exceptions.DatabaseConnectionError` and friends bubble
  up unchanged, so the framework-level error handler can log them.

**Vocabulary convention (D2.2)**

RepositoryProtocol method naming follows a strict two-prefix convention that
signals the return contract at a glance:

``find_*`` methods
    Return ``T | None``.  A missing record is *not* an error — the caller
    is expected to handle the ``None`` case.  No ``Result`` wrapper is used.

    Example::

        user: User | None = await repo.find_by_id(user_id)
        if user is None:
            return Response(status=404)

``get_*`` methods
    Return ``Result[T, E]``.  The record is expected to exist; its
    absence is an explicit domain error captured in the ``Err`` branch.
    The caller never needs a ``try/except`` for the "not found" case.

    Example::

        result = await repo.get_by_id(user_id)
        if result.is_err():
            raise result.unwrap_err()   # NotFoundError
        user = result.unwrap()

New repository methods MUST follow this convention.  Mixed semantics
(e.g. a ``find_*`` that raises, or a ``get_*`` that returns ``None``)
are prohibited.
"""

from __future__ import annotations

from quadkit.primitives.data import AbstractReadOnlyRepository, AbstractRepository
from quadkit.sql.repositories._rls_mixin import _RLSMixin
from quadkit.sql.repositories.base import SQLRepository
from quadkit.sql.repositories.cursor import CursorPage
from quadkit.sql.repositories.decorators import cacheable, timed
from quadkit.sql.repositories.filter_objects import F, Filter, field
from quadkit.sql.repositories.filters import FilterOperatorRegistry
from quadkit.sql.repositories.generic_repository import GenericRepository
from quadkit.sql.specification import SqlSpecification

__all__ = [
    "AbstractReadOnlyRepository",
    "AbstractRepository",
    "CursorPage",
    "F",
    "Filter",
    "FilterOperatorRegistry",
    "GenericRepository",
    "SQLRepository",
    "SqlSpecification",
    "_RLSMixin",
    "cacheable",
    "field",
    "timed",
]
