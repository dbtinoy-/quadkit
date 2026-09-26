"""Unit tests for the seed subsystem (seeds/manager.py).

Covers SQL/Python seed handlers, the extension registry, and the full
``SeedManager`` lifecycle against a real in-memory SQLite file database
(a temp file, so every pooled connection sees the same data).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.sql.seeds.manager import (
    PythonSeedHandler,
    SeedFileRegistry,
    SeedManager,
    SQLSeedHandler,
)


class _FakeConn:
    def __init__(self) -> None:
        self.executed: list[str] = []

    async def execute(self, statement: Any, *args: Any) -> None:
        self.executed.append(str(statement))


class _FakeEngine:
    """Engine whose begin() yields a recording connection."""

    def __init__(self) -> None:
        self.conn = _FakeConn()
        self._cm = _FakeEngineContext(self.conn)

    def begin(self) -> _FakeEngineContext:
        return self._cm


class _FakeEngineContext:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *exc: Any) -> None:
        return None


class TestSQLSeedHandler:
    @pytest.mark.asyncio
    async def test_executes_multiple_statements(self, tmp_path: Path) -> None:
        seed = tmp_path / "s.sql"
        seed.write_text(
            "INSERT INTO t (a) VALUES (1);\n"
            "-- a comment line\n"
            "\n"
            "INSERT INTO t (a) VALUES (2);\n"
        )
        engine = _FakeEngine()
        await SQLSeedHandler().execute(seed, engine)
        assert len(engine.conn.executed) == 2
        assert "VALUES (1)" in engine.conn.executed[0]
        assert "VALUES (2)" in engine.conn.executed[1]
        assert not any("--" in s for s in engine.conn.executed)

    @pytest.mark.asyncio
    async def test_trailing_statement_without_semicolon(self, tmp_path: Path) -> None:
        seed = tmp_path / "s.sql"
        seed.write_text("UPDATE t SET a = 1")
        engine = _FakeEngine()
        await SQLSeedHandler().execute(seed, engine)
        assert engine.conn.executed == ["UPDATE t SET a = 1"]

    @pytest.mark.asyncio
    async def test_dollar_quoted_block_kept_as_one_statement(
        self, tmp_path: Path
    ) -> None:
        seed = tmp_path / "s.sql"
        seed.write_text(
            "INSERT INTO fn (body) VALUES ($$\nBEGIN\n  SELECT 1;\nEND;\n$$);\n"
        )
        engine = _FakeEngine()
        await SQLSeedHandler().execute(seed, engine)
        assert len(engine.conn.executed) == 1
        assert "BEGIN" in engine.conn.executed[0]

    @pytest.mark.asyncio
    async def test_colon_containing_values_survive_rendering(
        self, tmp_path: Path
    ) -> None:
        seed = tmp_path / "s.sql"
        seed.write_text("INSERT INTO t (j) VALUES ('{\"k\": 1}');\n")
        engine = _FakeEngine()
        await SQLSeedHandler().execute(seed, engine)
        # Colon-bearing content round-trips through SQLAlchemy text()
        # verbatim (the handler escapes colons so nothing is bound).
        assert '{"k": 1}' in engine.conn.executed[0]


class TestPythonSeedHandler:
    @pytest.mark.asyncio
    async def test_async_seed_function_is_called(self, tmp_path: Path) -> None:
        seed = tmp_path / "s.py"
        seed.write_text(
            'async def seed(conn):\n    await conn.execute("CREATE TABLE p (x)")\n'
        )
        engine = _FakeEngine()
        await PythonSeedHandler().execute(seed, engine)
        assert engine.conn.executed == ["CREATE TABLE p (x)"]

    @pytest.mark.asyncio
    async def test_missing_seed_function_warns(self, tmp_path: Path) -> None:
        seed = tmp_path / "s.py"
        seed.write_text("VALUE = 1\n")
        engine = _FakeEngine()
        import quadkit.sql.seeds.manager as mgr  # noqa: PLC0415

        fake_logger = AsyncMock()
        original = mgr.logger
        mgr.logger = fake_logger
        try:
            await PythonSeedHandler().execute(seed, engine)
        finally:
            mgr.logger = original
        fake_logger.warning.assert_called_once()
        assert engine.conn.executed == []


class TestSeedFileRegistry:
    def test_defaults_cover_sql_and_python(self) -> None:
        registry = SeedFileRegistry.with_defaults()
        assert isinstance(registry._handlers[".sql"], SQLSeedHandler)
        assert isinstance(registry._handlers[".py"], PythonSeedHandler)

    def test_register_handler_overrides(self) -> None:
        registry = SeedFileRegistry.with_defaults()
        custom = object.__new__(SQLSeedHandler)
        registry.register_handler(".sql", custom)
        assert registry._handlers[".sql"] is custom

    @pytest.mark.asyncio
    async def test_unknown_extension_raises(self, tmp_path: Path) -> None:
        registry = SeedFileRegistry.with_defaults()
        file = tmp_path / "s.txt"
        file.write_text("x")
        with pytest.raises(ValueError, match="Unsupported seed file type"):
            await registry.execute_seed_file(file, _FakeEngine())


@pytest.fixture
def sqlite_manager(tmp_path: Path) -> SeedManager:
    db = tmp_path / "seeds.db"
    manager = SeedManager(f"sqlite+aiosqlite:///{db}", seeds_dir=tmp_path / "seeds")
    return manager


class TestSeedManagerLifecycle:
    @pytest.mark.asyncio
    async def test_run_applies_pending_seeds_in_order(self, sqlite_manager) -> None:
        seeds_dir = sqlite_manager.seeds_dir
        seeds_dir.mkdir()
        (seeds_dir / "02_second.sql").write_text(
            "CREATE TABLE IF NOT EXISTS t (a INTEGER);\nINSERT INTO t (a) VALUES (2);"
        )
        (seeds_dir / "01_first.sql").write_text(
            "CREATE TABLE IF NOT EXISTS t (a INTEGER);\nINSERT INTO t (a) VALUES (1);"
        )
        (seeds_dir / "notes.txt").write_text("ignored")

        await sqlite_manager.run()
        assert await sqlite_manager.get_applied_seeds() == {
            "01_first.sql",
            "02_second.sql",
        }

    @pytest.mark.asyncio
    async def test_run_skips_already_applied_seeds(self, sqlite_manager) -> None:
        seeds_dir = sqlite_manager.seeds_dir
        seeds_dir.mkdir()
        (seeds_dir / "01_first.sql").write_text(
            "CREATE TABLE IF NOT EXISTS t (a INTEGER);\nINSERT INTO t (a) VALUES (1);"
        )
        await sqlite_manager.run()

        # Rewrite the seed content; a correct skip leaves it unexecuted.
        (seeds_dir / "01_first.sql").write_text(
            "CREATE TABLE IF NOT EXISTS t (a INTEGER);\nINSERT INTO t (a) VALUES (999);"
        )
        await sqlite_manager.run()

        async with sqlite_manager.engine.connect() as conn:
            from sqlalchemy import text  # noqa: PLC0415

            result = await conn.execute(text("SELECT a FROM t"))
            rows = [r[0] for r in result.fetchall()]
        assert rows == [1]

    @pytest.mark.asyncio
    async def test_missing_seeds_dir_is_a_warning(self, sqlite_manager) -> None:
        # seeds_dir points at a non-existent path — run() must not raise.
        await sqlite_manager.run()

    @pytest.mark.asyncio
    async def test_reset_clears_history(self, sqlite_manager) -> None:
        seeds_dir = sqlite_manager.seeds_dir
        seeds_dir.mkdir()
        (seeds_dir / "01.sql").write_text(
            "CREATE TABLE IF NOT EXISTS t (a INTEGER);\nINSERT INTO t (a) VALUES (1);"
        )
        await sqlite_manager.run()
        assert await sqlite_manager.get_applied_seeds() == {"01.sql"}

        await sqlite_manager.reset()
        assert await sqlite_manager.get_applied_seeds() == set()

    @pytest.mark.asyncio
    async def test_failed_seed_aborts_and_is_not_recorded(
        self, sqlite_manager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quadkit.sql.seeds.manager as mgr  # noqa: PLC0415

        seeds_dir = sqlite_manager.seeds_dir
        seeds_dir.mkdir()
        (seeds_dir / "01_bad.sql").write_text("INSERT INTO missing_table VALUES (1);")

        with pytest.raises(Exception):
            await sqlite_manager.run()
        assert await sqlite_manager.get_applied_seeds() == set()


class TestSeedManagerClose:
    @pytest.mark.asyncio
    async def test_close_disposes_engine(self, sqlite_manager) -> None:
        engine = sqlite_manager.engine
        await sqlite_manager.initialize()
        pool_before = engine.pool
        await sqlite_manager.close()
        # dispose() tears down the pool and the engine serves a fresh one.
        assert engine.pool is not pool_before

    @pytest.mark.asyncio
    async def test_async_context_manager_closes_on_exit(self, tmp_path: Path) -> None:
        db = tmp_path / "ctx.db"
        manager: SeedManager
        async with SeedManager(f"sqlite+aiosqlite:///{db}", tmp_path / "seeds") as manager:
            await manager.initialize()
            pool_before = manager.engine.pool
        assert manager.engine.pool is not pool_before

    @pytest.mark.asyncio
    async def test_context_manager_exit_closes_even_on_error(
        self, tmp_path: Path
    ) -> None:
        db = tmp_path / "err.db"
        pool_before: object | None = None
        with pytest.raises(RuntimeError, match="boom"):
            async with SeedManager(f"sqlite+aiosqlite:///{db}", tmp_path / "seeds") as mgr:
                pool_before = mgr.engine.pool
                raise RuntimeError("boom")
        assert mgr.engine.pool is not pool_before
