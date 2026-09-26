import pytest

from quadkit.contracts.data.sql.database import QueryResult
from quadkit.sql.api import DatabaseError, QueryEngine


class _Cursor:
    """Mimic the raw cursor returned by aiosqlite / asyncpg drivers."""

    def __init__(self, rows, columns=None, scalar_value=None):
        self._rows = rows if rows is not None else []
        self._columns = columns or []
        self._scalar = scalar_value
        self.description = [(c,) for c in self._columns] if self._columns else None

    async def fetchall(self):
        return self._rows

    def scalar(self):
        return self._scalar


class _StructuredConn:
    def __init__(self, result):
        self._result = result

    async def execute(self, sql, params=None):
        return self._result


class _StructuredProvider:
    """Provider exposing the canonical execute_query() -> QueryResult path."""

    def __init__(self, result):
        self._result = result

    async def execute_query(self, sql, params=None):
        result = self._result
        if hasattr(result, "_scalar") and result._scalar is not None:
            value = result._scalar
            return QueryResult(
                rows=[{"count": value}] if value is not None else [],
                row_count=1 if value is not None else 0,
                execution_time=0.0,
                success=True,
            )
        rows = result._rows
        return QueryResult(
            rows=rows,
            row_count=len(rows),
            execution_time=0.0,
            success=True,
        )


class _RawProvider:
    """Provider exposing only the raw get_connection()/execute() path."""

    def __init__(self, cursor):
        self._cursor = cursor

    def get_connection(self):
        class Ctx:
            def __init__(self, cursor):
                self.cursor = cursor

            async def __aenter__(inner_self):
                return _StructuredConn(inner_self.cursor)

            async def __aexit__(inner_self, exc_type, exc, tb):
                return False

        return Ctx(self._cursor)


class _LegacyResult:
    def __init__(self, rows=None, scalar_value=None):
        self._rows = rows or []
        self._scalar = scalar_value

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    def scalar(self):
        return self._scalar


@pytest.mark.asyncio
async def test_query_engine_fetchall_and_fetchone_via_structured_provider():
    rows = [{"id": 1, "name": "Alice"}]
    qe = QueryEngine(_StructuredProvider(_LegacyResult(rows=rows)))

    fetched = await qe.fetchall("SELECT * FROM users")
    assert fetched == rows

    row = await qe.fetchone("SELECT * FROM users LIMIT 1")
    assert row == {"id": 1, "name": "Alice"}


@pytest.mark.asyncio
async def test_query_engine_scalar_via_structured_provider():
    qe = QueryEngine(_StructuredProvider(_LegacyResult(scalar_value=42)))

    value = await qe.scalar("SELECT COUNT(*) FROM t")
    assert value == 42


@pytest.mark.asyncio
async def test_query_engine_raw_provider_normalises_tuple_rows():
    # aiosqlite / asyncpg cursors return tuple rows; the engine must still
    # expose dict rows to callers.
    cursor = _Cursor(rows=[(1, "Alice")], columns=["id", "name"])
    qe = QueryEngine(_RawProvider(cursor))

    rows = await qe.fetchall("SELECT id, name FROM users")
    assert rows == [{"id": 1, "name": "Alice"}]

    row = await qe.fetchone("SELECT id, name FROM users LIMIT 1")
    assert row == {"id": 1, "name": "Alice"}

    scalar_provider = _RawProvider(_Cursor(rows=[(42,)], columns=["count"]))
    value = await QueryEngine(scalar_provider).scalar("SELECT COUNT(*) FROM t")
    assert value == 42


@pytest.mark.asyncio
async def test_query_engine_execute_fetch_false_returns_raw_driver_result():
    rows = [{"id": 1}]
    qe = QueryEngine(_StructuredProvider(_LegacyResult(rows=rows)))

    result = await qe.execute("SELECT * FROM users", fetch=False)
    assert isinstance(result, QueryResult)
    assert list(result.rows) == rows


def _sqlite_provider(conn):
    class Provider:
        def get_connection(self):
            class Ctx:
                async def __aenter__(inner_self):
                    return conn

                async def __aexit__(inner_self, exc_type, exc, tb):
                    return False

            return Ctx()

    return Provider()


@pytest.mark.asyncio
async def test_query_engine_aiosqlite_tuple_rows_are_normalised_to_dicts():
    """Real aiosqlite cursors return tuples; QueryEngine must expose dicts."""
    aiosqlite = pytest.importorskip("aiosqlite")
    conn = await aiosqlite.connect(":memory:")
    try:
        await conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
        await conn.execute("INSERT INTO users VALUES (1, 'Alice')")
        qe = QueryEngine(_sqlite_provider(conn))

        rows = await qe.fetchall("SELECT id, name FROM users")
        assert rows == [{"id": 1, "name": "Alice"}]

        row = await qe.fetchone("SELECT id, name FROM users LIMIT 1")
        assert row == {"id": 1, "name": "Alice"}

        value = await qe.scalar("SELECT COUNT(*) FROM users")
        assert value == 1
    finally:
        await conn.close()


def test_database_error_hierarchy():
    with pytest.raises(DatabaseError):
        raise DatabaseError("test")
