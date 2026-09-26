"""Tests for engine pragma tuning (SQLite WAL/busy_timeout policy hook)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from quadkit.sql.performance.engine_pragmas import configure_sqlite_pragmas


def _file_engine(tmp_path, name: str = "t.db"):
    return create_engine(f"sqlite:///{tmp_path}/{name}")


def test_applies_wal_synchronous_and_busy_timeout(tmp_path) -> None:
    """New connections get WAL + NORMAL + busy_timeout (the documented policy)."""
    eng = _file_engine(tmp_path)
    applied = configure_sqlite_pragmas(eng)
    with eng.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA synchronous")).scalar() == 1  # NORMAL
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000
    assert applied == {"journal_mode": "WAL", "synchronous": "NORMAL", "busy_timeout": 5000}


def test_in_memory_engine_accepts_policy_without_wal() -> None:
    """:memory: DBs ignore journal_mode (report memory) but keep the rest."""
    eng = create_engine("sqlite://")
    configure_sqlite_pragmas(eng, journal_mode="WAL")
    with eng.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "memory"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_every_pooled_connection_is_tuned(tmp_path) -> None:
    """The listener fires per connection, not once — second connection too."""
    eng = _file_engine(tmp_path, "pool.db")
    configure_sqlite_pragmas(eng, busy_timeout_ms=2500)
    for _ in range(2):
        conn = eng.connect()
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 2500
        conn.close()


def test_extra_pragmas_pass_through(tmp_path) -> None:
    """extra entries are applied (temp_store=MEMORY → 2) and echoed back."""
    eng = _file_engine(tmp_path, "extra.db")
    applied = configure_sqlite_pragmas(eng, extra={"temp_store": "MEMORY"})
    assert applied["temp_store"] == "MEMORY"
    with eng.connect() as conn:
        assert conn.execute(text("PRAGMA temp_store")).scalar() == 2  # MEMORY


def test_rejects_non_sqlite_dialect() -> None:
    """Wiring SQLite pragmas onto another dialect is a loud config error."""
    fake = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    with pytest.raises(ValueError, match="postgresql"):
        configure_sqlite_pragmas(fake)


def test_rejects_invalid_modes_and_names(tmp_path) -> None:
    """Unknown journal/synchronous modes and bad pragma names are rejected."""
    eng = _file_engine(tmp_path, "bad.db")
    with pytest.raises(ValueError, match="journal_mode"):
        configure_sqlite_pragmas(eng, journal_mode="MAGICAL")
    with pytest.raises(ValueError, match="synchronous"):
        configure_sqlite_pragmas(eng, synchronous="SOMETIMES")
    with pytest.raises(ValueError, match="busy_timeout_ms"):
        configure_sqlite_pragmas(eng, busy_timeout_ms=-1)
    with pytest.raises(ValueError, match="pragma name"):
        configure_sqlite_pragmas(eng, extra={"DROP TABLE users": "1"})


def test_double_configure_is_harmless(tmp_path) -> None:
    """Re-invoking just layers a second listener — connections still work."""
    eng = _file_engine(tmp_path, "twice.db")
    configure_sqlite_pragmas(eng)
    configure_sqlite_pragmas(eng)
    with eng.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
