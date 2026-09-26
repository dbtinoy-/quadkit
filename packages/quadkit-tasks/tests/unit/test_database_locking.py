"""Unit tests for the database-backed lock (concurrency.database_locking).

The lock exists because ``LockManager`` is process-local: two instances of an
application pointed at the same database must not both run the same scheduled
work. These tests pin the three properties that make that true — a claim is
atomic (one statement, winner decided by the database), a claim expires so a
crashed holder cannot block a key forever, and a non-owner can never renew,
release or overwrite a live claim.

The providers here are fakes over a real ``sqlite3`` connection: they exercise
the statement translation and the upsert semantics for real, and let a test
observe the SQL that reaches the driver, without pulling a database driver into
the package's dependencies.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from quadkit.tasks.concurrency.database_locking import (
    DatabaseLockManager,
    default_holder_id,
)
from quadkit.tasks.exceptions import TaskLockHeldError

# ---------------------------------------------------------------------------
# Fake providers — one per supported surface, all over the same sqlite3 file
# ---------------------------------------------------------------------------


@dataclass
class _Result:
    """The slice of a SQLAlchemy ``CursorResult`` the runner reads."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    rowcount: int = 0

    @property
    def returns_rows(self) -> bool:
        return bool(self.rows)

    def __iter__(self) -> Any:
        """``CursorResult`` is iterable; the runner iterates it for reads."""
        return iter(self.rows)


class _SessionProvider:
    """Provider shaped like ``gatewai``/SQLAlchemy: ``session().exec_driver_sql``."""

    surface = "session"

    def __init__(self, path: Path, dialect_name: str = "sqlite") -> None:
        self._path = path
        self.name = dialect_name
        self.statements: list[str] = []

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[Any, None]:
        provider = self
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:

            class _Connection:
                async def exec_driver_sql(
                    self, sql: str, params: tuple[Any, ...]
                ) -> _Result:
                    provider.statements.append(sql)
                    cursor = conn.execute(sql, params)
                    if cursor.description is not None:
                        rows = [dict(row) for row in cursor.fetchall()]
                        return _Result(rows=rows, rowcount=len(rows))
                    conn.commit()
                    return _Result(rowcount=cursor.rowcount)

            class _Session:
                """Mirrors ``AsyncSession.connection()``."""

                async def connection(self) -> _Connection:
                    return _Connection()

            yield _Session()
            conn.commit()
        finally:
            conn.close()

    def record(self, sql: str) -> None:
        self.statements.append(sql)


class _QuadkitSqlProvider:
    """Provider shaped like ``quadkit-sql``: ``execute_modify`` / ``execute_query``."""

    surface = "quadkit_sql"

    def __init__(self, path: Path, dialect_name: str = "sqlite") -> None:
        self._path = path
        self.name = dialect_name
        self.statements: list[str] = []

    async def execute_query(self, sql: str, params: list[Any] | None = None) -> Any:
        self.statements.append(sql)
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            rows = [
                dict(row) for row in conn.execute(sql, tuple(params or [])).fetchall()
            ]
        finally:
            conn.close()

        class _QueryResult:
            def __init__(self, rows: list[dict[str, Any]]) -> None:
                self.rows = rows

        return _QueryResult(rows)

    async def execute_modify(self, sql: str, params: list[Any] | None = None) -> Any:
        self.statements.append(sql)
        conn = sqlite3.connect(self._path)
        try:
            cursor = conn.execute(sql, tuple(params or []))
            conn.commit()
            affected = cursor.rowcount
        finally:
            conn.close()

        class _ModifyResult:
            def __init__(self, affected_rows: int) -> None:
                self.affected_rows = affected_rows

        return _ModifyResult(affected)


class _ExecuteProvider:
    """Provider with a single raw entry point: ``execute(sql, params)``."""

    surface = "execute"

    def __init__(self, path: Path, dialect_name: str = "sqlite") -> None:
        self._path = path
        self.name = dialect_name
        self.statements: list[str] = []

    async def execute(self, sql: str, params: list[Any] | None = None) -> Any:
        self.statements.append(sql)
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql, tuple(params or []))
            if cursor.description is not None:
                rows = [dict(row) for row in cursor.fetchall()]
            else:
                rows = []
                conn.commit()
            affected = cursor.rowcount
        finally:
            conn.close()

        class _Result:
            def __init__(self, rows: list[dict[str, Any]], affected_rows: int) -> None:
                self.rows = rows
                self.affected_rows = affected_rows

        return _Result(rows, affected)


class _NotAProvider:
    """A provider with none of the recognised surfaces."""


@pytest.fixture(params=["session", "quadkit_sql", "execute"])
def provider(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    """One provider per supported surface, each over its own database file."""
    path = tmp_path / f"{request.param}.db"
    factories = {
        "session": _SessionProvider,
        "quadkit_sql": _QuadkitSqlProvider,
        "execute": _ExecuteProvider,
    }
    return factories[request.param](path)


@dataclass
class _Clock:
    """A clock a test can move."""

    now: float = 1_000_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _manager(
    provider: Any, clock: _Clock | None = None, **kwargs: Any
) -> DatabaseLockManager:
    return DatabaseLockManager(provider, clock=clock or _Clock(), **kwargs)


# ---------------------------------------------------------------------------
# Claiming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_claims_a_free_key(provider: Any) -> None:
    """A free key is claimed and visible to a reader."""
    lock = _manager(provider)

    assert await lock.acquire("log_cleanup", "worker-a", ttl_seconds=60) is True

    snapshot = await lock.snapshot("log_cleanup")
    assert snapshot.holder == "worker-a"
    assert snapshot.held is True
    assert snapshot.ttl_remaining > 0


@pytest.mark.asyncio
async def test_second_holder_cannot_take_a_live_key(provider: Any) -> None:
    """A live claim wins: the database decides, not a race between readers."""
    lock = _manager(provider)
    assert await lock.acquire("log_cleanup", "worker-a", ttl_seconds=60) is True

    assert await lock.acquire("log_cleanup", "worker-b", ttl_seconds=60) is False

    assert (await lock.snapshot("log_cleanup")).holder == "worker-a"


@pytest.mark.asyncio
async def test_expired_claim_is_taken_over(provider: Any) -> None:
    """A holder that died releases the key by expiring, not by never letting go."""
    clock = _Clock()
    lock = _manager(provider, clock)
    assert await lock.acquire("log_cleanup", "worker-a", ttl_seconds=30) is True

    clock.advance(31)

    assert (await lock.snapshot("log_cleanup")).held is False
    assert await lock.acquire("log_cleanup", "worker-b", ttl_seconds=30) is True
    assert (await lock.snapshot("log_cleanup")).holder == "worker-b"


@pytest.mark.asyncio
async def test_reacquire_by_same_holder_extends_the_claim(provider: Any) -> None:
    """A holder may refresh its own claim without waiting for expiry."""
    clock = _Clock()
    lock = _manager(provider, clock)
    assert await lock.acquire("job", "worker-a", ttl_seconds=30) is True
    first_expiry = (await lock.snapshot("job")).expires_at

    clock.advance(10)
    assert await lock.acquire("job", "worker-a", ttl_seconds=30) is True

    assert (await lock.snapshot("job")).expires_at == pytest.approx(
        first_expiry + 10 if first_expiry else 0, abs=1
    )


@pytest.mark.asyncio
async def test_unknown_extra_column_is_rejected(provider: Any) -> None:
    """Extra columns must be declared, so the statement stays static and safe."""
    lock = _manager(provider)

    with pytest.raises(ValueError, match="unknown lock columns"):
        await lock.acquire("job", "worker-a", ttl_seconds=5, task_id="tsk_1")


@pytest.mark.asyncio
async def test_extra_column_is_written(provider: Any) -> None:
    """A table that requires more than the lock columns can still be used."""
    lock = _manager(provider, extra_columns=("task_id",))

    assert await lock.acquire("job", "worker-a", ttl_seconds=5, task_id="tsk_1") is True

    rows = await lock._runner.run(
        "SELECT task_id FROM quadkit_task_locks WHERE lock_key = ?", ["job"]
    )
    assert rows == [{"task_id": "tsk_1"}]


@pytest.mark.asyncio
async def test_non_positive_ttl_is_rejected(provider: Any) -> None:
    """A zero TTL would be a lock that is never held."""
    lock = _manager(provider)

    with pytest.raises(ValueError, match="ttl_seconds must be positive"):
        await lock.acquire("job", "worker-a", ttl_seconds=0)


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_renew_only_works_for_the_owner(provider: Any) -> None:
    """A non-owner cannot extend somebody else's claim."""
    clock = _Clock()
    lock = _manager(provider, clock)
    assert await lock.acquire("job", "worker-a", ttl_seconds=30) is True

    assert await lock.renew("job", "worker-b", ttl_seconds=30) is False
    assert await lock.renew("job", "worker-a", ttl_seconds=30) is True
    assert (await lock.snapshot("job")).expires_at == pytest.approx(clock.now + 30)


@pytest.mark.asyncio
async def test_renew_after_takeover_fails(provider: Any) -> None:
    """The displaced holder is told its hold is gone instead of assuming it is not."""
    clock = _Clock()
    lock = _manager(provider, clock)
    await lock.acquire("job", "worker-a", ttl_seconds=30)
    clock.advance(31)
    await lock.acquire("job", "worker-b", ttl_seconds=30)

    assert await lock.renew("job", "worker-a", ttl_seconds=30) is False


@pytest.mark.asyncio
async def test_release_only_works_for_the_owner(provider: Any) -> None:
    """Releasing is scoped to the holder that owns the row."""
    lock = _manager(provider)
    await lock.acquire("job", "worker-a", ttl_seconds=30)

    assert await lock.release("job", "worker-b") is False
    assert (await lock.snapshot("job")).holder == "worker-a"

    assert await lock.release("job", "worker-a") is True
    assert (await lock.snapshot("job")).held is False


# ---------------------------------------------------------------------------
# Context managers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hold_raises_when_another_instance_holds_the_key(provider: Any) -> None:
    """Yield-nothing-would-run-unexclusively is a failure, not a silent pass."""
    lock = _manager(provider)
    await lock.acquire("job", "worker-a", ttl_seconds=30)

    with pytest.raises(TaskLockHeldError) as excinfo:
        async with lock.hold("job", holder="worker-b", ttl_seconds=30):
            pytest.fail("the block must not run while the key is held")

    assert excinfo.value.details["holder"] == "worker-a"


@pytest.mark.asyncio
async def test_hold_releases_on_exit(provider: Any) -> None:
    """The key is free after the block, not after the TTL."""
    lock = _manager(provider)

    async with lock.hold("job", holder="worker-a", ttl_seconds=30) as handle:
        assert handle.holder == "worker-a"
        assert (await lock.snapshot("job")).held is True

    assert (await lock.snapshot("job")).held is False


@pytest.mark.asyncio
async def test_handle_renew_extends_the_hold(provider: Any) -> None:
    """Long work can keep a claim alive from inside the block."""
    clock = _Clock()
    lock = _manager(provider, clock)

    async with lock.hold("job", holder="worker-a", ttl_seconds=30) as handle:
        clock.advance(20)
        assert await handle.renew() is True
        assert (await lock.snapshot("job")).expires_at == pytest.approx(clock.now + 30)


@pytest.mark.asyncio
async def test_guard_skips_when_held(provider: Any) -> None:
    """Scheduled work on a second instance is skipped, not queued."""
    lock = _manager(provider)
    await lock.acquire("cron:nightly", "worker-a", ttl_seconds=30)

    ran = False
    async with lock.guard("cron:nightly", holder="worker-b") as handle:
        ran = handle is not None

    assert ran is False
    assert (await lock.snapshot("cron:nightly")).holder == "worker-a"


@pytest.mark.asyncio
async def test_guard_raises_when_asked_to(provider: Any) -> None:
    """The strict mode surfaces contention as an error."""
    lock = _manager(provider)
    await lock.acquire("cron:nightly", "worker-a", ttl_seconds=30)

    with pytest.raises(TaskLockHeldError):
        async with lock.guard(
            "cron:nightly", holder="worker-b", skip_on_contention=False
        ):
            pytest.fail("the block must not run while the key is held")


@pytest.mark.asyncio
async def test_acquire_or_wait_succeeds_after_release(provider: Any) -> None:
    """A caller that may wait gets the lock once the holder finishes."""
    lock = _manager(provider)
    await lock.acquire("job", "worker-a", ttl_seconds=30)

    async def _release_soon() -> None:
        import asyncio

        await asyncio.sleep(0.05)
        await lock.release("job", "worker-a")

    import asyncio

    releaser = asyncio.create_task(_release_soon())
    handle = await lock.acquire_or_wait(
        "job", holder="worker-b", ttl_seconds=30, wait_seconds=2, poll_interval=0.01
    )
    await releaser
    assert handle.holder == "worker-b"
    await handle.release()


@pytest.mark.asyncio
async def test_acquire_or_wait_gives_up_with_details(provider: Any) -> None:
    """Waiting is bounded, and the error names who is in the way."""
    lock = _manager(provider)
    await lock.acquire("job", "worker-a", ttl_seconds=300)

    with pytest.raises(TaskLockHeldError) as excinfo:
        await lock.acquire_or_wait(
            "job",
            holder="worker-b",
            ttl_seconds=30,
            wait_seconds=0.05,
            poll_interval=0.01,
        )

    assert excinfo.value.details["holder"] == "worker-a"
    assert excinfo.value.details["ttl_remaining"] > 0


# ---------------------------------------------------------------------------
# Configuration and provider surfaces
# ---------------------------------------------------------------------------


def test_bad_identifiers_are_rejected_before_any_sql(tmp_path: Path) -> None:
    """Table and column names are interpolated, so they are validated."""
    provider = _SessionProvider(tmp_path / "x.db")

    with pytest.raises(ValueError, match="plain SQL identifier"):
        DatabaseLockManager(provider, table="locks; DROP TABLE users")
    with pytest.raises(ValueError, match="plain SQL identifier"):
        DatabaseLockManager(provider, key_column="key) --")


def test_provider_without_a_supported_surface_fails_loudly() -> None:
    """Silently locking nothing would be worse than refusing to construct."""
    with pytest.raises(TypeError, match="database provider"):
        DatabaseLockManager(_NotAProvider())


@pytest.mark.asyncio
async def test_every_supported_surface_locks(provider: Any) -> None:
    """All three provider shapes give the same exclusivity."""
    lock = _manager(provider)

    assert await lock.acquire("k", "a", ttl_seconds=10) is True
    assert await lock.acquire("k", "b", ttl_seconds=10) is False
    assert await lock.release("k", "a") is True
    assert await lock.acquire("k", "b", ttl_seconds=10) is True


@pytest.mark.asyncio
async def test_postgres_providers_get_numbered_placeholders(tmp_path: Path) -> None:
    """Placeholders are translated for the provider's dialect, not assumed."""
    provider = _SessionProvider(tmp_path / "pg.db", dialect_name="postgres")
    lock = _manager(provider)

    assert (await lock._runner.dialect()) == "postgres"
    translated = await lock._runner.dialect()
    from quadkit.tasks.dialect import translate_placeholders

    sql = translate_placeholders("UPDATE t SET a = ? WHERE b = ?", translated)
    assert sql == "UPDATE t SET a = $1 WHERE b = $2"


@pytest.mark.asyncio
async def test_app_owned_schema_can_skip_table_creation(provider: Any) -> None:
    """A migration-managed table is used as-is: no DDL is issued for it."""
    creating = _manager(provider)
    assert await creating.acquire("warmup", "setup", ttl_seconds=5) is True
    await creating.release("warmup", "setup")

    before = len(getattr(provider, "statements", []))
    lock = _manager(provider, ensure_table=False)

    assert await lock.acquire("job", "worker-a", ttl_seconds=5) is True
    statements = getattr(provider, "statements", [])[before:]
    assert statements, "the lock still talks to the database"
    assert not [s for s in statements if "CREATE TABLE" in s]


def test_row_objects_with_mapping_are_accepted() -> None:
    """SQLAlchemy hands back ``Row`` objects, not dicts; both shapes must work."""

    class _Row:
        """A stand-in for ``sqlalchemy.engine.Row``."""

        def __init__(self, data: dict[str, Any]) -> None:
            self._mapping = data

    from quadkit.tasks.concurrency.database_locking import _row_to_dict

    assert _row_to_dict(_Row({"holder": "a"})) == {"holder": "a"}
    assert _row_to_dict({"holder": "b"}) == {"holder": "b"}


def test_default_holder_id_is_unique_per_call() -> None:
    """Two processes (or one process twice) never share a holder id."""
    first, second = default_holder_id(), default_holder_id()

    assert first != second
    assert ":" in first


def test_describe_reports_the_configuration(provider: Any) -> None:
    """Diagnostics name the table and columns actually in use."""
    lock = _manager(
        provider,
        table="system_task_locks",
        key_column="type",
        extra_columns=("task_id",),
    )

    described = lock.describe()

    assert described["table"] == "system_task_locks"
    assert described["key_column"] == "type"
    assert described["extra_columns"] == ["task_id"]
    assert described["surface"] == provider.surface
