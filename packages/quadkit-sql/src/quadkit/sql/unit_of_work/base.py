"""Backwards-compatible re-export of :class:`AbstractUnitOfWork`.

``AbstractUnitOfWork`` is storage-agnostic -- it tracks entities and domain
events and delegates persistence to a subclass-provided ``_flush()``. It
never imported a SQL driver, so it now lives in ``quadkit.domain`` where
non-SQL implementations (such as the in-memory one in ``quadkit-testing``)
can use it without depending on ``quadkit-sql``.

This module is retained so existing
``from quadkit.sql.unit_of_work.base import AbstractUnitOfWork`` imports
keep working.
"""

from __future__ import annotations

from quadkit.domain.unit_of_work import AbstractUnitOfWork, run_lifecycle_hooks

__all__ = ["AbstractUnitOfWork", "run_lifecycle_hooks"]
