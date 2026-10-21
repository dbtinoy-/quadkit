"""SQLAlchemy ORM integration for quadkit-sql.

The raw providers (``DatabaseProviderProtocol``) cover connections and
SQL. This package covers the ORM: one engine, one pool, resolvable from
the DI container, so an application mapping declarative models does not
have to build a second engine against the same database.
"""

from __future__ import annotations

from quadkit.sql.orm.executor import SessionExecutor, SessionmakerExecutor
from quadkit.sql.orm.session import SessionFactory

__all__ = ["SessionExecutor", "SessionFactory", "SessionmakerExecutor"]
