"""SQL-based implementation of AbstractCheckpointStore (MF-03)."""

from __future__ import annotations

from typing import Any

from quadkit.events.stores.base import AbstractCheckpointStore
from quadkit.events.stores.identifiers import validate_table_name
from quadkit.primitives import clock as ambient_clock


class SqlCheckpointStore(AbstractCheckpointStore):
    """SQL implementation of AbstractCheckpointStore for Postgres and SQLite."""

    def __init__(self, connection: Any, table_name: str = "event_checkpoints") -> None:
        validate_table_name(table_name)
        validate_table_name(f"{table_name}_locks")
        self.connection = connection
        self.table_name = table_name

    async def get_checkpoint(self, name: str) -> int:
        """Get checkpoint from database."""
        # Detect if it's asyncpg or aiosqlite
        is_asyncpg = hasattr(self.connection, "fetchval")

        if is_asyncpg:
            query = f"""
                SELECT position FROM {self.table_name}
                WHERE name = $1
            """  # noqa: S608 — table name validated at init
            val = await self.connection.fetchval(query, name)
        else:
            query = f"""
                SELECT position FROM {self.table_name}
                WHERE name = ?
            """  # noqa: S608 — table name validated at init
            cursor = await self.connection.execute(query, (name,))
            row = await cursor.fetchone()
            val = row[0] if row else None

        return int(val) if val is not None else 0

    async def save_checkpoint(self, name: str, position: int) -> None:
        """Save checkpoint to database."""
        is_asyncpg = hasattr(self.connection, "execute") and hasattr(
            self.connection, "fetchval"
        )
        now = ambient_clock.now()

        if is_asyncpg:
            query = f"""
                INSERT INTO {self.table_name} (name, position, updated_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (name) DO UPDATE
                SET position = $2, updated_at = $3
            """  # noqa: S608 — table name validated at init
            await self.connection.execute(query, name, position, now)
        else:
            query = f"""
                INSERT INTO {self.table_name} (name, position, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                position=excluded.position,
                updated_at=excluded.updated_at
            """  # noqa: S608 — table name validated at init
            await self.connection.execute(query, (name, position, now.isoformat()))
            await self.connection.commit()

    async def list_checkpoints(self) -> dict[str, int]:
        """List all checkpoints."""
        is_asyncpg = hasattr(self.connection, "fetch")

        if is_asyncpg:
            rows = await self.connection.fetch(
                f"SELECT name, position FROM {self.table_name}"  # noqa: S608 — table name validated at init
            )
        else:
            cursor = await self.connection.execute(
                f"SELECT name, position FROM {self.table_name}"  # noqa: S608 — table name validated at init
            )
            rows = await cursor.fetchall()

        return {row["name"]: int(row["position"]) for row in rows}

    async def delete_checkpoint(self, name: str) -> None:
        """Delete a checkpoint."""
        is_asyncpg = hasattr(self.connection, "execute")

        if is_asyncpg:
            await self.connection.execute(
                f"DELETE FROM {self.table_name} WHERE name = $1",  # noqa: S608
                name,
            )
        else:
            await self.connection.execute(
                f"DELETE FROM {self.table_name} WHERE name = ?",  # noqa: S608
                (name,),
            )
            await self.connection.commit()

    async def acquire_lock(self, name: str, owner: str, timeout: float = 30.0) -> bool:
        """Acquire a distributed lock using a lease pattern."""
        is_asyncpg = hasattr(self.connection, "fetchval")
        now = ambient_clock.now()
        expires_at = now.timestamp() + timeout

        if is_asyncpg:
            # Postgres: upsert lease
            query = f"""
                INSERT INTO {self.table_name}_locks (name, owner, expires_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (name) DO UPDATE
                SET owner = $2, expires_at = $3
                WHERE {self.table_name}_locks.expires_at < $4 OR {self.table_name}_locks.owner = $2
                RETURNING name
            """  # noqa: S608 — table name validated at init
            val = await self.connection.fetchval(
                query, name, owner, expires_at, now.timestamp()
            )
            return val is not None
        # SQLite: manual check and update
        # Note: This is simplified and depends on external transaction handling
        check_query = (
            f"SELECT owner, expires_at FROM {self.table_name}_locks WHERE name = ?"  # noqa: S608 — table name validated at init
        )
        cursor = await self.connection.execute(check_query, (name,))
        row = await cursor.fetchone()

        if not row or row[1] < now.timestamp() or row[0] == owner:
            query = f"""
                    INSERT INTO {self.table_name}_locks (name, owner, expires_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                    owner=excluded.owner,
                    expires_at=excluded.expires_at
                """  # noqa: S608 — table name validated at init
            await self.connection.execute(query, (name, owner, expires_at))
            await self.connection.commit()
            return True
        return False

    async def release_lock(self, name: str, owner: str) -> None:
        """Release a distributed lock if owned by the caller."""
        is_asyncpg = hasattr(self.connection, "execute")

        if is_asyncpg:
            await self.connection.execute(
                f"DELETE FROM {self.table_name}_locks WHERE name = $1 AND owner = $2",  # noqa: S608 — table name validated at init
                name,
                owner,
            )
        else:
            await self.connection.execute(
                f"DELETE FROM {self.table_name}_locks WHERE name = ? AND owner = ?",  # noqa: S608 — table name validated at init
                (name, owner),
            )
            await self.connection.commit()


class InMemoryCheckpointStore(AbstractCheckpointStore):
    """In-memory implementation of AbstractCheckpointStore."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, int] = {}
        self._locks: dict[str, tuple[str, float]] = {}

    async def get_checkpoint(self, name: str) -> int:
        return self._checkpoints.get(name, 0)

    async def save_checkpoint(self, name: str, position: int) -> None:
        self._checkpoints[name] = position

    async def list_checkpoints(self) -> dict[str, int]:
        return dict(self._checkpoints)

    async def delete_checkpoint(self, name: str) -> None:
        self._checkpoints.pop(name, None)

    async def acquire_lock(self, name: str, owner: str, timeout: float = 30.0) -> bool:
        now = ambient_clock.now().timestamp()
        if name in self._locks:
            curr_owner, expires_at = self._locks[name]
            if curr_owner != owner and expires_at > now:
                return False

        self._locks[name] = (owner, now + timeout)
        return True

    async def release_lock(self, name: str, owner: str) -> None:
        if name in self._locks and self._locks[name][0] == owner:
            del self._locks[name]
