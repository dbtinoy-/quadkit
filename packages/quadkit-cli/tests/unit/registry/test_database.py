from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from quadkit.cli.registry.database import (
    DatabaseBackend,
    DatabaseConnection,
    DatabaseRegistry,
    MySQLBackend,
    PostgreSQLBackend,
    QueryResult,
    SQLiteBackend,
    create_database_connection,
)


class TestQueryResult:
    def test_creation(self) -> None:
        r = QueryResult(rows=[{"a": 1}], rowcount=1)
        assert len(r.rows) == 1
        assert r.rowcount == 1


class TestDatabaseBackend:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            DatabaseBackend()

    def test_supports_backup_no_binary(self) -> None:
        class TestBackend(DatabaseBackend):
            name = "test"
            def parse_url(self, url): return {}
            def get_client_binary(self): return None
            def build_shell_command(self, p): return []
            async def get_tables(self, p): return []
            async def get_columns(self, p, t): return []
            def build_backup_command(self, p, o): return []
            def build_restore_command(self, p, i): return []

        b = TestBackend()
        assert b.supports_backup() is False


class TestSQLiteBackend:
    def test_parse_url(self) -> None:
        b = SQLiteBackend()
        result = b.parse_url("sqlite:///./dev.db")
        assert result["backend"] == "sqlite"
        assert result["path"] == "./dev.db"

    def test_get_client_binary_found(self) -> None:
        with patch("quadkit.cli.registry.database_backends.shutil.which", return_value="/usr/bin/sqlite3"):
            b = SQLiteBackend()
            assert b.get_client_binary() == "/usr/bin/sqlite3"

    def test_get_client_binary_not_found(self) -> None:
        with patch("quadkit.cli.registry.database_backends.shutil.which", return_value=None):
            b = SQLiteBackend()
            assert b.get_client_binary() is None

    def test_build_shell_command(self) -> None:
        with patch.object(SQLiteBackend, "get_client_binary", return_value="/usr/bin/sqlite3"):
            b = SQLiteBackend()
            cmd = b.build_shell_command({"path": "test.db"})
            assert cmd == ["/usr/bin/sqlite3", "test.db"]

    def test_build_shell_command_no_binary(self) -> None:
        with patch.object(SQLiteBackend, "get_client_binary", return_value=None):
            b = SQLiteBackend()
            with pytest.raises(RuntimeError):
                b.build_shell_command({})

    @pytest.mark.asyncio
    async def test_get_tables(self) -> None:
        b = SQLiteBackend()
        mock_provider = AsyncMock()
        mock_provider.execute_query.return_value = QueryResult(
            rows=[{"name": "users"}, {"name": "posts"}], rowcount=2
        )
        tables = await b.get_tables(mock_provider)
        assert "users" in tables
        assert "posts" in tables

    @pytest.mark.asyncio
    async def test_get_columns(self) -> None:
        b = SQLiteBackend()
        mock_provider = AsyncMock()
        mock_provider.execute_query.return_value = QueryResult(
            rows=[
                {"name": "id", "type": "INTEGER", "notnull": 1, "dflt_value": None, "pk": 1},
            ],
            rowcount=1,
        )
        columns = await b.get_columns(mock_provider, "users")
        assert columns[0]["name"] == "id"
        assert columns[0]["nullable"] is False
        assert columns[0]["primary_key"] is True

    def test_build_backup_command(self) -> None:
        with patch.object(SQLiteBackend, "get_client_binary", return_value="/usr/bin/sqlite3"):
            b = SQLiteBackend()
            cmd = b.build_backup_command({"path": "dev.db"}, "backup.sql")
            assert "sqlite3" in cmd[0]

    def test_build_restore_command(self) -> None:
        with patch.object(SQLiteBackend, "get_client_binary", return_value="/usr/bin/sqlite3"):
            b = SQLiteBackend()
            cmd = b.build_restore_command({"path": "dev.db"}, "backup.sql")
            assert "sqlite3" in cmd[0]


class TestPostgreSQLBackend:
    def test_parse_url_valid(self) -> None:
        b = PostgreSQLBackend()
        result = b.parse_url("postgresql://user:pass@localhost:5432/mydb")
        assert result["user"] == "user"
        assert result["password"] == "pass"
        assert result["host"] == "localhost"
        assert result["port"] == "5432"
        assert result["database"] == "mydb"

    def test_parse_url_no_port(self) -> None:
        b = PostgreSQLBackend()
        result = b.parse_url("postgresql://user@localhost/mydb")
        assert result["port"] == "5432"

    def test_parse_url_invalid(self) -> None:
        b = PostgreSQLBackend()
        result = b.parse_url("invalid")
        assert "error" in result

    def test_build_shell_command(self) -> None:
        with patch.object(PostgreSQLBackend, "get_client_binary", return_value="/usr/bin/psql"):
            b = PostgreSQLBackend()
            cmd = b.build_shell_command({"user": "admin", "host": "localhost", "port": "5432", "database": "mydb"})
            assert "-U" in cmd
            assert "admin" in cmd

    @pytest.mark.asyncio
    async def test_get_tables(self) -> None:
        b = PostgreSQLBackend()
        mock_provider = AsyncMock()
        mock_provider.execute_query.return_value = QueryResult(
            rows=[{"table_name": "users"}], rowcount=1
        )
        tables = await b.get_tables(mock_provider)
        assert "users" in tables

    @pytest.mark.asyncio
    async def test_get_columns(self) -> None:
        b = PostgreSQLBackend()
        mock_provider = AsyncMock()
        mock_provider.execute_query.return_value = QueryResult(
            rows=[
                {"column_name": "id", "data_type": "integer", "is_nullable": "NO", "column_default": None},
            ],
            rowcount=1,
        )
        columns = await b.get_columns(mock_provider, "users")
        assert columns[0]["name"] == "id"

    def test_build_backup_command(self) -> None:
        with patch("quadkit.cli.registry.database_backends.shutil.which", return_value="/usr/bin/pg_dump"):
            b = PostgreSQLBackend()
            cmd = b.build_backup_command({"user": "admin", "host": "localhost", "database": "mydb"}, "backup.sql")
            assert "pg_dump" in cmd[0]

    def test_build_restore_command(self) -> None:
        with patch.object(PostgreSQLBackend, "get_client_binary", return_value="/usr/bin/psql"):
            with patch("shutil.which", return_value="/usr/bin/psql"):
                b = PostgreSQLBackend()
                cmd = b.build_restore_command({"user": "admin", "database": "mydb"}, "backup.sql")
                assert "psql" in cmd[0]


class TestMySQLBackend:
    def test_parse_url_valid(self) -> None:
        b = MySQLBackend()
        result = b.parse_url("mysql://user:pass@localhost:3306/mydb")
        assert result["user"] == "user"
        assert result["host"] == "localhost"
        assert result["port"] == "3306"

    def test_parse_url_invalid(self) -> None:
        b = MySQLBackend()
        result = b.parse_url("invalid")
        assert "error" in result

    def test_build_shell_command(self) -> None:
        with patch.object(MySQLBackend, "get_client_binary", return_value="/usr/bin/mysql"):
            b = MySQLBackend()
            cmd = b.build_shell_command({"user": "root", "password": "pass", "host": "localhost", "database": "mydb"})
            assert "-u" in cmd
            assert "root" in cmd

    def test_password_never_in_argv(self) -> None:
        """Secrets must not leak into the child argv (readable via ps)."""
        with patch.object(MySQLBackend, "get_client_binary", return_value="/usr/bin/mysql"):
            with patch("quadkit.cli.registry.database_backends.shutil.which", return_value="/usr/bin/mysqldump"):
                b = MySQLBackend()
                params = {"user": "root", "password": "s3cret!", "host": "localhost", "database": "mydb"}
                for cmd in (
                    b.build_shell_command(params),
                    b.build_backup_command(params, "backup.sql"),
                    b.build_restore_command(params, "backup.sql"),
                ):
                    assert "s3cret!" not in cmd
                    assert not any(arg.startswith("-p") for arg in cmd)

    def test_password_via_mysql_pwd_env(self) -> None:
        b = MySQLBackend()
        env = b.subprocess_env({"user": "root", "password": "s3cret!", "host": "localhost"})
        assert env.get("MYSQL_PWD") == "s3cret!"

    def test_no_password_keeps_env_clean(self) -> None:
        b = MySQLBackend()
        env = b.subprocess_env({"user": "root"})
        assert "MYSQL_PWD" not in env

    @pytest.mark.asyncio
    async def test_get_tables(self) -> None:
        b = MySQLBackend()
        mock_provider = AsyncMock()
        mock_provider.execute_query.return_value = QueryResult(
            rows=[{"Tables_in_test": "users"}], rowcount=1
        )
        tables = await b.get_tables(mock_provider)
        assert "users" in tables

    def test_build_backup_command(self) -> None:
        with patch("quadkit.cli.registry.database_backends.shutil.which", return_value="/usr/bin/mysqldump"):
            b = MySQLBackend()
            cmd = b.build_backup_command({"user": "root", "password": "pass", "host": "localhost", "database": "mydb"}, "backup.sql")
            assert cmd[0] == "mysqldump"
            assert "--result-file=backup.sql" in cmd
            assert ">" not in cmd
            assert "<" not in cmd

    def test_build_restore_command_uses_stdin(self) -> None:
        with patch.object(MySQLBackend, "get_client_binary", return_value="/usr/bin/mysql"):
            with patch("shutil.which", return_value="/usr/bin/mysql"):
                b = MySQLBackend()
                cmd = b.build_restore_command({"user": "root", "database": "mydb"}, "backup.sql")
                assert cmd[0] == "mysql"
                assert "<" not in cmd
                assert "backup.sql" not in cmd


class TestDatabaseRegistry:
    def test_register_and_get(self) -> None:
        registry = DatabaseRegistry()
        registry.register(SQLiteBackend)
        backend = registry.get("sqlite")
        assert backend is not None

    def test_get_by_alias(self) -> None:
        registry = DatabaseRegistry()
        registry.register(PostgreSQLBackend)
        backend = registry.get("postgres")
        assert backend is not None

    def test_detect_from_url_sqlite(self) -> None:
        registry = DatabaseRegistry()
        registry.register(SQLiteBackend)
        backend = registry.detect_from_url("sqlite:///./dev.db")
        assert backend.name == "sqlite"

    def test_detect_from_url_unknown_fallback(self) -> None:
        registry = DatabaseRegistry()
        registry.register(SQLiteBackend)
        backend = registry.detect_from_url("unknown://localhost/db")
        assert backend.name == "sqlite"

    def test_with_defaults_populates_all_backends(self) -> None:
        registry = DatabaseRegistry.with_defaults()
        assert registry.get("sqlite") is not None
        assert registry.get("postgresql") is not None
        assert registry.get("mysql") is not None

    def test_get_all(self) -> None:
        registry = DatabaseRegistry()
        registry.register(SQLiteBackend)
        all_backends = registry.get_all()
        assert "sqlite" in all_backends

class TestDatabaseConnection:
    def test_get_url_from_env(self) -> None:
        with patch("os.environ.get", return_value="postgres://localhost/db"):
            url = DatabaseConnection._get_url_from_env_or_config()
            assert url == "postgres://localhost/db"

    def test_get_url_default(self) -> None:
        with patch("os.environ.get", return_value=None):
            url = DatabaseConnection._get_url_from_env_or_config()
            assert "sqlite" in url

    def test_get_url_from_config(self) -> None:
        from unittest.mock import mock_open as mock_open_factory
        with patch("os.environ.get", return_value=None):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("builtins.open", mock_open_factory(read_data="database:\n  url: postgres://config/db")):
                    url = DatabaseConnection._get_url_from_env_or_config(Path("config.yaml"))
                    assert "postgres://config/db" in url

    @pytest.mark.asyncio
    async def test_connect_import_error(self) -> None:
        with patch("importlib.import_module", side_effect=ImportError):
            conn = DatabaseConnection(url="sqlite:///./test.db")
            with pytest.raises(RuntimeError):
                await conn.connect()

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        conn = DatabaseConnection(url="sqlite:///./test.db")
        with patch.object(conn, "connect", AsyncMock()):
            with patch.object(conn, "disconnect", AsyncMock()):
                async with conn:
                    pass

    def test_open_shell(self) -> None:
        conn = DatabaseConnection(url="sqlite:///./dev.db")
        with patch.object(conn.backend, "build_shell_command", return_value=["sqlite3", "dev.db"]):
            with patch("quadkit.cli.registry.database.subprocess.run"):
                conn.open_shell()

    def test_open_shell_os_error(self) -> None:
        conn = DatabaseConnection(url="sqlite:///./dev.db")
        with patch.object(conn.backend, "build_shell_command", return_value=["sqlite3", "dev.db"]):
            with patch("quadkit.cli.registry.database.subprocess.run", side_effect=OSError):
                with pytest.raises(RuntimeError):
                    conn.open_shell()


class TestCreateDatabaseConnection:
    def test_factory(self) -> None:
        conn = create_database_connection(url="sqlite:///./test.db")
        assert isinstance(conn, DatabaseConnection)
        assert "sqlite" in conn.url
