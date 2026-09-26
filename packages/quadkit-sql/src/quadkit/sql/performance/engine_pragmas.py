"""SQLAlchemy engine pragma tuning — SQLite concurrency policy as a hook.

quadkit-sql's :class:`~quadkit.sql.providers.sqlite_provider.SQLiteProvider`
applies the WAL + busy_timeout policy to its own raw aiosqlite connections.
Applications built on SQLAlchemy engines (``create_engine`` /
``create_async_engine``) could not reuse that policy — this module ports it
as a ``connect``-event listener so every pooled DBAPI connection is tuned
the same way:

- ``journal_mode=WAL`` — readers no longer block the writer (and vice
  versa); safe for dashboards polling while requests are logged.
- ``synchronous=NORMAL`` — the standard WAL pairing (durable across app
  crashes; only a power loss may roll back the last transactions).
- ``busy_timeout`` — a writer waits instead of failing instantly with
  ``database is locked`` under momentary contention.

Example:
    ```python
    from sqlalchemy.ext.asyncio import create_async_engine
    from quadkit.sql.performance.engine_pragmas import configure_sqlite_pragmas

    engine = create_async_engine("sqlite+aiosqlite:///app.db")
    configure_sqlite_pragmas(engine.sync_engine)
    ```

Non-SQLite dialects are rejected loudly — wiring SQLite pragmas onto
PostgreSQL is a configuration bug, not a no-op.
"""

from __future__ import annotations

import re
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)

DEFAULT_JOURNAL_MODE = "WAL"
DEFAULT_SYNCHRONOUS = "NORMAL"
DEFAULT_BUSY_TIMEOUT_MS = 5000

_JOURNAL_MODES = {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}
_SYNCHRONOUS_MODES = {"OFF", "NORMAL", "FULL", "EXTRA"}
_PRAGMA_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def configure_sqlite_pragmas(
    sync_engine: Any,
    *,
    journal_mode: str = DEFAULT_JOURNAL_MODE,
    synchronous: str = DEFAULT_SYNCHRONOUS,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    extra: dict[str, str | int] | None = None,
) -> dict[str, str | int]:
    """Apply SQLite pragmas to every connection *sync_engine* opens.

    Registers a SQLAlchemy ``connect`` listener executing the pragma set on
    each new raw DBAPI connection (pooled connections created before the
    call are untouched — wire this immediately after engine creation).

    Args:
        sync_engine: A SQLAlchemy ``Engine`` (pass ``async_engine.sync_engine``
            for async engines).
        journal_mode: SQLite journal mode (default ``WAL``; ignored silently
            by in-memory databases, which always report ``memory``).
        synchronous: SQLite synchronous mode (default ``NORMAL`` — the
            standard WAL pairing).
        busy_timeout_ms: Milliseconds a writer waits for the lock before
            raising (default 5000).
        extra: Additional ``PRAGMA name=value`` entries (e.g.
            ``{"temp_store": "MEMORY"}``). Names must be lowercase
            identifiers — values are interpolated verbatim, so only pass
            trusted constants.

    Returns:
        The applied pragma map (pragma name → value) for logging/inspection.

    Raises:
        ValueError: The engine is not SQLite, or a pragma name/mode is invalid.
    """
    dialect = getattr(getattr(sync_engine, "dialect", None), "name", "")
    if dialect != "sqlite":
        raise ValueError(
            f"configure_sqlite_pragmas targets SQLite engines; got dialect '{dialect or 'unknown'}'"
        )

    journal = str(journal_mode).upper()
    if journal not in _JOURNAL_MODES:
        raise ValueError(
            f"invalid journal_mode {journal_mode!r} (expected one of {sorted(_JOURNAL_MODES)})"
        )
    sync_mode = str(synchronous).upper()
    if sync_mode not in _SYNCHRONOUS_MODES:
        raise ValueError(
            f"invalid synchronous {synchronous!r} (expected one of {sorted(_SYNCHRONOUS_MODES)})"
        )
    timeout = int(busy_timeout_ms)
    if timeout < 0:
        raise ValueError("busy_timeout_ms must be ≥ 0")

    statements = [
        f"PRAGMA journal_mode={journal}",
        f"PRAGMA synchronous={sync_mode}",
        f"PRAGMA busy_timeout={timeout}",
    ]
    extra = extra or {}
    for name, value in extra.items():
        if not _PRAGMA_NAME.match(name):
            raise ValueError(f"invalid pragma name {name!r}")
        statements.append(f"PRAGMA {name}={value}")

    def _on_connect(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            for statement in statements:
                cursor.execute(statement)
        finally:
            cursor.close()

    from sqlalchemy import event

    event.listen(sync_engine, "connect", _on_connect)

    applied: dict[str, str | int] = {
        "journal_mode": journal,
        "synchronous": sync_mode,
        "busy_timeout": timeout,
        **extra,
    }
    logger.info("sql.sqlite_pragmas_configured", **applied)
    return applied
