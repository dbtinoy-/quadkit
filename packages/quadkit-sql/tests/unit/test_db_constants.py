"""Unit tests for quadkit-sql constants.

These tests verify the constants defined in quadkit.sql.constants.
"""

from quadkit.sql import constants as const


class TestVersion:
    """Tests for version constant."""

    def test_version_exists(self) -> None:
        assert const.__version__ is not None
        assert isinstance(const.__version__, str)


class TestEnvironmentPrefix:
    """Tests for environment variable prefix."""

    def test_env_prefix(self) -> None:
        assert const.ENV_PREFIX == "QK_SQL__"


class TestConnectionPoolDefaults:
    """Tests for connection pool default constants."""

    def test_default_pool_min_size(self) -> None:
        assert const.DEFAULT_POOL_MIN_SIZE == 1

    def test_default_pool_max_size(self) -> None:
        assert const.DEFAULT_POOL_MAX_SIZE == 10

    def test_default_pool_timeout(self) -> None:
        assert const.DEFAULT_POOL_TIMEOUT == 30.0

    def test_default_connect_timeout(self) -> None:
        assert const.DEFAULT_CONNECT_TIMEOUT == 10.0

    def test_default_command_timeout(self) -> None:
        assert const.DEFAULT_COMMAND_TIMEOUT == 60.0


class TestMigrationDefaults:
    """Tests for migration default constants."""

    def test_default_migrations_dir(self) -> None:
        assert const.DEFAULT_MIGRATIONS_DIR == "migrations"

    def test_default_migrations_table(self) -> None:
        assert const.DEFAULT_MIGRATIONS_TABLE == "schema_migrations"


class TestQueryDefaults:
    """Tests for query default constants."""

    def test_default_query_timeout(self) -> None:
        assert const.DEFAULT_QUERY_TIMEOUT == 30.0

    def test_default_max_retries(self) -> None:
        assert const.DEFAULT_MAX_RETRIES == 3

    def test_default_retry_delay(self) -> None:
        assert const.DEFAULT_RETRY_DELAY == 0.5


class TestBackendIdentifiers:
    """Tests for backend identifier constants."""

    def test_backend_sqlite(self) -> None:
        assert const.BACKEND_SQLITE == "sqlite"

    def test_backend_postgres(self) -> None:
        assert const.BACKEND_POSTGRES == "postgres"

    def test_backend_mysql(self) -> None:
        assert const.BACKEND_MYSQL == "mysql"


class TestPaginationDefaults:
    """Tests for pagination default constants."""

    def test_default_page_size(self) -> None:
        assert const.DEFAULT_PAGE_SIZE == 20

    def test_max_page_size(self) -> None:
        assert const.MAX_PAGE_SIZE == 1000

    def test_default_cursor_size(self) -> None:
        assert const.DEFAULT_CURSOR_SIZE == 20


class TestAllExports:
    """Tests to verify __all__ exports."""

    def test_all_contains_expected_items(self) -> None:
        expected = [
            "BACKEND_MYSQL",
            "BACKEND_POSTGRES",
            "BACKEND_SQLITE",
            "DEFAULT_COMMAND_TIMEOUT",
            "DEFAULT_CONNECT_TIMEOUT",
            "DEFAULT_CURSOR_SIZE",
            "DEFAULT_MAX_RETRIES",
            "DEFAULT_MIGRATIONS_DIR",
            "DEFAULT_MIGRATIONS_TABLE",
            "DEFAULT_PAGE_SIZE",
            "DEFAULT_POOL_MAX_SIZE",
            "DEFAULT_POOL_MIN_SIZE",
            "DEFAULT_POOL_TIMEOUT",
            "DEFAULT_QUERY_TIMEOUT",
            "DEFAULT_RETRY_DELAY",
            "ENV_PREFIX",
            "MAX_PAGE_SIZE",
        ]
        for item in expected:
            assert item in const.__all__
