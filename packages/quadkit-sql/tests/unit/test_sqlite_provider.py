"""Unit tests for SQLiteProvider"""

from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


class TestSQLiteProvider:
    """Test SQLiteProvider functionality"""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock SQLite connection"""
        conn = Mock()
        conn.execute = AsyncMock()
        conn.commit = AsyncMock()
        conn.rollback = AsyncMock()
        conn.close = AsyncMock()
        conn.row_factory = None
        return conn

    @pytest.fixture
    def mock_cursor(self):
        """Create a mock cursor"""
        cursor = Mock()
        cursor.execute = AsyncMock()
        cursor.fetchall = AsyncMock()
        cursor.fetchone = AsyncMock()
        cursor.close = AsyncMock()
        cursor.rowcount = 1
        return cursor

    @pytest.fixture
    def mock_row(self):
        """Create a mock row"""
        row = Mock()
        row.keys = Mock(return_value=["id", "name"])
        row.__getitem__ = Mock(side_effect=lambda key: {"id": 1, "name": "test"}[key])
        return row

    def test_init_memory_database(self):
        """Test initialization with in-memory database"""
        provider = SQLiteProvider(":memory:")

        assert provider.connection_string == "sqlite:///:memory:"
        assert provider.database_type == "sqlite"
        assert provider.database == ":memory:"

    @patch("pathlib.Path.mkdir")
    def test_init_file_database(self, mock_mkdir):
        """Test initialization with file database"""
        provider = SQLiteProvider("/path/to/db.sqlite")

        assert provider.connection_string == "sqlite:////path/to/db.sqlite"
        assert provider.database_type == "sqlite"
        assert provider.database == "path/to/db.sqlite"

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("pathlib.Path.mkdir")
    def test_init_default_memory(self, mock_mkdir):
        """Test initialization with default (memory) database"""
        provider = SQLiteProvider()

        assert provider.connection_string == "sqlite:///:memory:"
        assert provider.database == ":memory:"

        # Should not create directories for memory database
        mock_mkdir.assert_not_called()

    @patch("pathlib.Path.mkdir")
    def test_init_creates_directory(self, mock_mkdir):
        """Test that directory is created for file database"""
        SQLiteProvider("/new/path/db.sqlite")

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @pytest.mark.asyncio
    @patch("aiosqlite.connect", new_callable=AsyncMock)
    async def test_create_connection_memory(self, mock_connect):
        """Test creating connection for memory database"""
        mock_connection = Mock()
        mock_connect.return_value = mock_connection
        mock_connection.execute = AsyncMock()

        provider = SQLiteProvider(":memory:")
        connection = await provider._create_connection()

        mock_connect.assert_called_once_with(":memory:")
        assert connection.row_factory.__name__ == "Row"
        assert connection == mock_connection
        # WAL is not applicable to in-memory databases; only busy_timeout set.
        mock_connection.execute.assert_awaited_once_with("PRAGMA busy_timeout=5000")

    @pytest.mark.asyncio
    @patch("aiosqlite.connect", new_callable=AsyncMock)
    @patch("pathlib.Path.mkdir")
    async def test_create_connection_file(self, mock_mkdir, mock_connect):
        """Test creating connection for file database"""
        mock_connection = Mock()
        mock_connect.return_value = mock_connection
        mock_connection.execute = AsyncMock()

        provider = SQLiteProvider("/path/to/db.sqlite")
        connection = await provider._create_connection()

        mock_mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_connect.assert_called_once_with("/path/to/db.sqlite")
        assert connection == mock_connection
        # WAL journaling and a busy timeout prevent SQLITE_BUSY failures
        # when concurrent writers contend on the same file.
        mock_connection.execute.assert_has_awaits(
            [
                call("PRAGMA journal_mode=WAL"),
                call("PRAGMA busy_timeout=5000"),
            ]
        )

    @pytest.mark.asyncio
    async def test_close_connection(self, mock_connection):
        """Test closing connection"""
        provider = SQLiteProvider()

        await provider._close_connection(mock_connection)

        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_raw(self, mock_connection, mock_cursor, mock_row):
        """Test raw query execution"""
        mock_connection.execute.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [mock_row]

        provider = SQLiteProvider()
        result = await provider._execute_query_raw(
            mock_connection,
            "SELECT * FROM test",
            ["param"],
        )

        mock_connection.execute.assert_called_once_with("SELECT * FROM test", ["param"])
        mock_cursor.fetchall.assert_called_once()
        mock_cursor.close.assert_called_once()

        assert len(result) == 1
        assert result[0] == {"id": 1, "name": "test"}

    @pytest.mark.asyncio
    async def test_execute_query_raw_no_params(self, mock_connection, mock_cursor):
        """Test raw query execution without parameters"""
        mock_connection.execute.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        provider = SQLiteProvider()
        result = await provider._execute_query_raw(
            mock_connection,
            "SELECT * FROM test",
        )

        mock_connection.execute.assert_called_once_with("SELECT * FROM test", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_execute_modify_raw(self, mock_connection, mock_cursor):
        """Test raw modify execution"""
        mock_connection.execute.return_value = mock_cursor
        mock_cursor.rowcount = 5

        provider = SQLiteProvider()
        result = await provider._execute_modify_raw(
            mock_connection,
            "INSERT INTO test VALUES (?)",
            ["value"],
        )

        mock_connection.execute.assert_called_once_with(
            "INSERT INTO test VALUES (?)",
            ["value"],
        )
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

        assert result == 5

    @pytest.mark.asyncio
    async def test_execute_modify_raw_no_params(self, mock_connection, mock_cursor):
        """Test raw modify execution without parameters"""
        mock_connection.execute.return_value = mock_cursor

        provider = SQLiteProvider()
        result = await provider._execute_modify_raw(mock_connection, "DELETE FROM test")

        mock_connection.execute.assert_called_once_with("DELETE FROM test", [])
        assert result == 1  # mock_cursor.rowcount default

    @pytest.mark.asyncio
    async def test_begin_transaction_raw(self, mock_connection):
        """Test beginning transaction"""
        provider = SQLiteProvider()

        await provider._begin_transaction_raw(mock_connection)

        mock_connection.execute.assert_called_once_with("BEGIN")

    @pytest.mark.asyncio
    async def test_commit_transaction_raw(self, mock_connection):
        """Test committing transaction"""
        provider = SQLiteProvider()

        await provider._commit_transaction_raw(mock_connection)

        mock_connection.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_transaction_raw(self, mock_connection):
        """Test rolling back transaction"""
        provider = SQLiteProvider()

        await provider._rollback_transaction_raw(mock_connection)

        mock_connection.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_last_insert_id(self, mock_connection, mock_cursor):
        """Test getting last insert ID"""
        mock_connection.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (42,)

        provider = SQLiteProvider()
        result = await provider._get_last_insert_id(mock_connection, "test_table")

        mock_connection.execute.assert_called_once_with("SELECT last_insert_rowid()")
        mock_cursor.fetchone.assert_called_once()
        mock_cursor.close.assert_called_once()

        assert result == 42

    @pytest.mark.asyncio
    async def test_get_last_insert_id_no_result(self, mock_connection, mock_cursor):
        """Test getting last insert ID when no result"""
        mock_connection.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        provider = SQLiteProvider()
        result = await provider._get_last_insert_id(mock_connection, "test_table")

        assert result is None

    @pytest.mark.asyncio
    @patch.object(SQLiteProvider, "execute_query")
    async def test_table_exists_true(self, mock_execute_query):
        """Test checking if table exists (table found)"""
        mock_result = Mock()
        mock_result.rows = [{"name": "test_table"}]
        mock_execute_query.return_value = mock_result

        provider = SQLiteProvider()
        result = await provider.table_exists("test_table")

        mock_execute_query.assert_called_once_with(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            ["test_table"],
        )
        assert result is True

    @pytest.mark.asyncio
    @patch.object(SQLiteProvider, "execute_query")
    async def test_table_exists_false(self, mock_execute_query):
        """Test checking if table exists (table not found)"""
        mock_result = Mock()
        mock_result.rows = []
        mock_execute_query.return_value = mock_result

        provider = SQLiteProvider()
        result = await provider.table_exists("test_table")

        assert result is False

    @pytest.mark.asyncio
    @patch.object(SQLiteProvider, "execute_query")
    async def test_get_table_columns(self, mock_execute_query):
        """Test getting table column information"""
        mock_result = Mock()
        mock_result.rows = [
            {
                "name": "id",
                "type": "INTEGER",
                "notnull": 1,
                "dflt_value": None,
                "pk": 1,
            },
            {
                "name": "name",
                "type": "TEXT",
                "notnull": 0,
                "dflt_value": "'default'",
                "pk": 0,
            },
        ]
        mock_execute_query.return_value = mock_result

        provider = SQLiteProvider()
        result = await provider.get_table_columns("test_table")

        mock_execute_query.assert_called_once_with("PRAGMA table_info(test_table)")

        assert len(result) == 2
        assert result[0] == {
            "name": "id",
            "type": "INTEGER",
            "nullable": False,
            "default": None,
            "primary_key": True,
        }
        assert result[1] == {
            "name": "name",
            "type": "TEXT",
            "nullable": True,
            "default": "'default'",
            "primary_key": False,
        }

    @pytest.mark.asyncio
    @patch.object(SQLiteProvider, "execute_query")
    async def test_get_table_columns_empty(self, mock_execute_query):
        """Test getting table columns for empty table"""
        mock_result = Mock()
        mock_result.rows = []
        mock_execute_query.return_value = mock_result

        provider = SQLiteProvider()
        result = await provider.get_table_columns("empty_table")

        assert result == []

    @pytest.mark.asyncio
    @patch.object(SQLiteProvider, "execute_query")
    async def test_create_table(self, mock_execute_query):
        """Test creating a table"""
        provider = SQLiteProvider()

        columns = {
            "id": "INTEGER PRIMARY KEY",
            "name": "TEXT NOT NULL",
            "email": "TEXT",
        }

        await provider.create_table("users", columns)

        expected_sql = 'CREATE TABLE "users" ("id" INTEGER PRIMARY KEY, "name" TEXT NOT NULL, "email" TEXT)'
        mock_execute_query.assert_called_once_with(expected_sql)

    @pytest.mark.asyncio
    @patch.object(SQLiteProvider, "execute_query")
    async def test_drop_table(self, mock_execute_query):
        """Test dropping a table"""
        provider = SQLiteProvider()

        await provider.drop_table("users")

        mock_execute_query.assert_called_once_with('DROP TABLE IF EXISTS "users"')

    @pytest.mark.asyncio
    @patch.object(SQLiteProvider, "execute_query")
    async def test_health_check_success(self, mock_execute_query):
        """Test successful health check"""
        mock_result = Mock()
        mock_result.rows = [{"health_check": 1}]
        mock_execute_query.return_value = mock_result

        provider = SQLiteProvider()
        result = await provider.health_check()

        mock_execute_query.assert_called_once_with("SELECT 1 as health_check")

        assert result.status == HealthStatus.HEALTHY
        assert "Database connection successful" in result.details["message"]
        assert result.details["database_type"] == "sqlite"
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    @patch.object(SQLiteProvider, "execute_query")
    async def test_health_check_failure(self, mock_execute_query):
        """Test failed health check"""
        mock_execute_query.side_effect = RuntimeError("Connection failed")

        provider = SQLiteProvider()
        result = await provider.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "Database connection failed: Connection failed" in result.error
        assert result.details["database_type"] == "sqlite"
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting database statistics"""
        provider = SQLiteProvider()

        stats = await provider.get_stats()

        assert stats["database_type"] == "sqlite"
        assert not stats["connected"]
        assert not stats["connection_pool"]
        assert not stats["query_logger"]

    @pytest.mark.asyncio
    async def test_get_stats_with_components(self):
        """Test getting database statistics with components"""
        mock_pool = Mock()
        mock_logger = Mock()

        provider = SQLiteProvider()
        provider.connection_pool = mock_pool
        provider.query_executor.query_logger = mock_logger
        provider.connection_manager._connected = True

        stats = await provider.get_stats()

        assert stats["database_type"] == "sqlite"
        assert stats["connected"]
        assert stats["connection_pool"]
        assert stats["query_logger"]


class TestSQLiteProviderUrlSchemes:
    """Any sqlite* scheme (sync or async driver) must normalize to a bare
    path — never leak scheme fragments into the filesystem."""

    def test_async_scheme_relative_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        provider = SQLiteProvider("sqlite+aiosqlite:///data/app.db")

        assert provider.connection_string == "sqlite:///data/app.db"
        assert provider.database == "data/app.db"
        assert not (tmp_path / "sqlite+aiosqlite:").exists()

    def test_async_scheme_absolute_path(self, tmp_path):
        db = tmp_path / "abs" / "db.sqlite"

        provider = SQLiteProvider(f"sqlite+aiosqlite:///{db}")

        assert provider.connection_string == f"sqlite:///{db}"
        assert provider.database == str(db).lstrip("/")
        assert (tmp_path / "abs").is_dir()

    def test_sync_scheme_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        provider = SQLiteProvider("sqlite:///data/app.db")

        assert provider.connection_string == "sqlite:///data/app.db"
        assert provider.database == "data/app.db"

    def test_async_scheme_memory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        provider = SQLiteProvider("sqlite+aiosqlite:///:memory:")

        assert provider.connection_string == "sqlite:///:memory:"
        assert provider.database == ":memory:"
        assert list(tmp_path.iterdir()) == []

    def test_other_driver_variant(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        provider = SQLiteProvider("sqlite+pysqlite:///data/app.db")

        assert provider.connection_string == "sqlite:///data/app.db"
        assert provider.database == "data/app.db"

    @pytest.mark.asyncio
    @patch("aiosqlite.connect", new_callable=AsyncMock)
    async def test_create_connection_bare_path(
        self, mock_connect, tmp_path, monkeypatch
    ):
        """The connection layer must receive the bare path, not the URL."""
        monkeypatch.chdir(tmp_path)
        mock_connection = Mock()
        mock_connect.return_value = mock_connection
        mock_connection.execute = AsyncMock()

        provider = SQLiteProvider("sqlite+aiosqlite:///data/app.db")
        await provider._create_connection()

        mock_connect.assert_called_once_with("data/app.db")
