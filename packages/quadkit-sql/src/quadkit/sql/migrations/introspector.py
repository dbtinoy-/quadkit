"""Migration introspector for checking status and history."""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.sql.migrations.types import MigrationInfo, MigrationStatus
from quadkit.logging import get_logger

try:
    from alembic.script import ScriptDirectory

    ALEMBIC_AVAILABLE = True
except ImportError:
    ALEMBIC_AVAILABLE = False

logger = get_logger(__name__)


class SchemaIntrospector:
    """Introspector for Alembic migration status and history."""

    def __init__(self, config: Any, connection_string: str) -> None:
        self.config = config
        self.connection_string = connection_string

    async def get_status(self) -> MigrationStatus:
        """Get current migration status."""
        script = ScriptDirectory.from_config(self.config)
        head_rev = script.get_current_head()

        def _inspect_db() -> dict[str, Any]:
            try:
                from sqlalchemy import (
                    create_engine,
                    text,
                )
                from sqlalchemy.exc import SQLAlchemyError

                engine = create_engine(self.connection_string)
                with engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT version_num FROM alembic_version LIMIT 1"),
                    )
                    row = result.fetchone()
                    current = row[0] if row else None
            except (OSError, RuntimeError, SQLAlchemyError) as exc:
                # If table doesn't exist, or any DB error, treat as not yet migrated.
                return {"current_revision": None, "error": str(exc)}
            else:
                return {"current_revision": current}

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _inspect_db)

        current_revision = result.get("current_revision")
        is_up_to_date = bool(
            current_revision and head_rev and current_revision == head_rev,
        )

        pending_migrations: list[str] = []
        if current_revision and head_rev and current_revision != head_rev:

            def _pending() -> list[str]:
                try:
                    revisions = list(
                        script.iterate_revisions(current_revision, head_rev),
                    )
                    return [
                        rev.revision
                        for rev in revisions
                        if rev.revision != current_revision
                    ]
                except (AttributeError, TypeError, ValueError, KeyError):
                    return []

            pending_migrations = await loop.run_in_executor(None, _pending)

        pending_infos = [
            MigrationInfo(
                revision=rev,
                version=rev,
                description="",
                depends_on=None,
                branch_labels=None,
            )
            for rev in pending_migrations
        ]

        return MigrationStatus(
            current_revision=current_revision,
            head_revision=head_rev,
            is_up_to_date=is_up_to_date,
            pending_migrations=pending_infos,
        )

    async def get_history(self, limit: int | None = None) -> list[MigrationInfo]:
        """Get migration history."""
        script = ScriptDirectory.from_config(self.config)

        def _get_history() -> list[MigrationInfo]:
            revisions = list(script.walk_revisions())
            if limit:
                revisions = revisions[:limit]

            return [
                MigrationInfo(
                    revision=rev.revision,
                    version=rev.revision,
                    description=rev.doc,
                    depends_on=rev.down_revision,  # type: ignore[arg-type]
                    branch_labels=list(rev.branch_labels)
                    if rev.branch_labels
                    else None,
                )
                for rev in revisions
            ]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_history)

    async def get_branches(self) -> list[dict[str, Any]]:
        """Get migration branches."""
        script = ScriptDirectory.from_config(self.config)

        def _get_branches() -> list[dict[str, Any]]:
            return [
                {
                    "revision": rev.revision,
                    "branch_labels": list(rev.branch_labels),
                    "description": rev.doc,
                    "depends_on": rev.down_revision,
                }
                for rev in script.walk_revisions()
                if rev.branch_labels
            ]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_branches)

    async def validate_migrations(self) -> dict[str, Any]:
        """Validate migration integrity."""
        script = ScriptDirectory.from_config(self.config)

        def _validate() -> dict[str, Any]:
            issues: list[str] = []
            try:
                issues.extend(
                    f"Missing dependency: {rev.down_revision} for {rev.revision}"
                    for rev in script.walk_revisions()
                    if rev.down_revision and not script.get_revision(rev.down_revision)  # type: ignore[arg-type]
                )

                visited: set[str] = set()
                for rev in script.walk_revisions():
                    if rev.revision in visited:
                        continue
                    current = rev
                    path: list[str] = []
                    while current:
                        if current.revision in path:
                            issues.append(
                                f"Circular dependency detected: {' -> '.join([*path, current.revision])}",
                            )
                            break
                        path.append(current.revision)
                        if current.down_revision:
                            current = script.get_revision(current.down_revision)  # type: ignore[arg-type]
                        else:
                            break
                return {"valid": len(issues) == 0, "issues": issues}
            except (AttributeError, TypeError, ValueError, KeyError) as e:
                return {"valid": False, "issues": [f"Validation error: {e!s}"]}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _validate)

    async def get_pending_operations(
        self,
        target_revision: str = "head",
    ) -> list[dict[str, Any]]:
        """Get list of pending operations."""
        status = await self.get_status()
        if status.current_revision == target_revision:
            return []

        script = ScriptDirectory.from_config(self.config)

        def _get_operations() -> list[dict[str, Any]]:
            operations: list[dict[str, Any]] = []
            if status.current_revision and target_revision != status.current_revision:
                revisions = list(
                    script.iterate_revisions(status.current_revision, target_revision),
                )
                operations.extend(
                    {
                        "revision": rev.revision,
                        "description": rev.doc,
                        "operation": "upgrade"
                        if rev.revision != status.current_revision
                        else "current",
                    }
                    for rev in revisions
                )
            return operations

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_operations)
