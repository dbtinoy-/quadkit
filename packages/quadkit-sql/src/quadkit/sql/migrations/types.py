from __future__ import annotations
from dataclasses import dataclass


@dataclass
class MigrationInfo:
    """Information about a migration"""

    revision: str
    version: str
    description: str
    depends_on: str | None = None
    branch_labels: list[str] | None = None


@dataclass
class MigrationStatus:
    """Current migration status"""

    current_revision: str | None
    head_revision: str | None
    is_up_to_date: bool
    pending_migrations: list[MigrationInfo]
