"""Convenience async API wrappers for AlembicManager"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from quadkit.sql.migrations.manager import AlembicManager


async def init_migrations(
    connection_string: str,
    migrations_path: str | Path = "migrations",
) -> AlembicManager:
    manager = AlembicManager(connection_string, migrations_path)
    await manager.initialize()
    return manager


async def create_migration(
    connection_string: str,
    migrations_path: str | Path,
    message: str,
    autogenerate: bool = False,
) -> str:
    manager = AlembicManager(connection_string, migrations_path)
    return await manager.create_revision(message, autogenerate=autogenerate)


async def migrate_up(
    connection_string: str,
    migrations_path: str | Path,
    revision: str = "head",
) -> None:
    manager = AlembicManager(connection_string, migrations_path)
    await manager.upgrade(revision)


async def migrate_down(
    connection_string: str,
    migrations_path: str | Path,
    revision: str = "-1",
) -> None:
    manager = AlembicManager(connection_string, migrations_path)
    await manager.downgrade(revision)


async def rollback_migrations(
    connection_string: str,
    migrations_path: str | Path,
    steps: int = 1,
) -> None:
    manager = AlembicManager(connection_string, migrations_path)
    await manager.rollback(steps)  # type: ignore[attr-defined]


async def rollback_to_revision(
    connection_string: str,
    migrations_path: str | Path,
    revision: str,
) -> None:
    manager = AlembicManager(connection_string, migrations_path)
    await manager.rollback_to(revision)  # type: ignore[attr-defined]


async def migrate_up_dry_run(
    connection_string: str,
    migrations_path: str | Path,
    revision: str = "head",
) -> list[str]:
    manager = AlembicManager(connection_string, migrations_path)
    return await manager.upgrade_dry_run(revision)


async def migrate_down_dry_run(
    connection_string: str,
    migrations_path: str | Path,
    revision: str = "-1",
) -> list[str]:
    manager = AlembicManager(connection_string, migrations_path)
    return await manager.downgrade_dry_run(revision)


async def rollback_dry_run(
    connection_string: str,
    migrations_path: str | Path,
    steps: int = 1,
) -> list[dict[str, Any]]:
    manager = AlembicManager(connection_string, migrations_path)
    return cast(
        "list[dict[str, Any]]",
        await manager.rollback_dry_run(steps),  # type: ignore[attr-defined]
    )


async def get_migration_branches(
    connection_string: str,
    migrations_path: str | Path,
) -> list[dict[str, Any]]:
    manager = AlembicManager(connection_string, migrations_path)
    return await manager.get_branches()


async def create_migration_branch(
    connection_string: str,
    migrations_path: str | Path,
    branch_name: str,
    parent_revision: str = "head",
) -> str:
    manager = AlembicManager(connection_string, migrations_path)
    return await manager.create_branch(branch_name, parent_revision)  # type: ignore[call-arg]


async def merge_migration_branches(
    connection_string: str,
    migrations_path: str | Path,
    source_branch: str,
    target_branch: str,
) -> None:
    manager = AlembicManager(connection_string, migrations_path)
    await manager.merge_branches(source_branch, target_branch)


async def validate_migrations(
    connection_string: str,
    migrations_path: str | Path,
) -> dict[str, Any]:
    manager = AlembicManager(connection_string, migrations_path)
    return await manager.validate_migrations()


async def get_pending_migrations(
    connection_string: str,
    migrations_path: str | Path,
) -> list[dict[str, Any]]:
    manager = AlembicManager(connection_string, migrations_path)
    return await manager.get_pending_operations()
