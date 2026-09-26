"""Migration managers (Alembic and minimal-SQL implementations)."""

from __future__ import annotations

from quadkit.sql.migrations.manager._alembic import (
    ALEMBIC_AVAILABLE,  # noqa: F401 — re-exported availability flag
    AlembicManager,
)
from quadkit.sql.migrations.manager._simple import SimpleMigrationManager

__all__ = [
    "AlembicManager",
    "SimpleMigrationManager",
]
