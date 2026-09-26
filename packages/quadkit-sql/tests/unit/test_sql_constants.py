"""Unit tests for quadkit.sql.constants module"""

from __future__ import annotations

import pytest

from quadkit.sql import constants


class TestVersion:
    def test_version_is_string(self) -> None:
        assert isinstance(constants.__version__, str)

    def test_version_not_empty(self) -> None:
        assert len(constants.__version__) > 0


class TestEnvironmentConstants:
    def test_env_prefix(self) -> None:
        assert constants.ENV_PREFIX == "QK_SQL__"

    def test_env_nested_delimiter(self) -> None:
        assert constants.ENV_NESTED_DELIMITER == "__"


class TestConnectionPoolDefaults:
    def test_pool_min_size(self) -> None:
        assert constants.DEFAULT_POOL_MIN_SIZE == 1
        assert isinstance(constants.DEFAULT_POOL_MIN_SIZE, int)

    def test_pool_max_size(self) -> None:
        assert constants.DEFAULT_POOL_MAX_SIZE == 10
        assert isinstance(constants.DEFAULT_POOL_MAX_SIZE, int)

    def test_pool_timeout(self) -> None:
        assert constants.DEFAULT_POOL_TIMEOUT == 30.0
        assert isinstance(constants.DEFAULT_POOL_TIMEOUT, float)

    def test_connect_timeout(self) -> None:
        assert constants.DEFAULT_CONNECT_TIMEOUT == 10.0
        assert isinstance(constants.DEFAULT_CONNECT_TIMEOUT, float)

    def test_command_timeout(self) -> None:
        assert constants.DEFAULT_COMMAND_TIMEOUT == 60.0
        assert isinstance(constants.DEFAULT_COMMAND_TIMEOUT, float)


class TestMigrationDefaults:
    def test_migrations_dir(self) -> None:
        assert constants.DEFAULT_MIGRATIONS_DIR == "migrations"

    def test_migrations_table(self) -> None:
        assert constants.DEFAULT_MIGRATIONS_TABLE == "schema_migrations"


class TestQueryDefaults:
    def test_query_timeout(self) -> None:
        assert constants.DEFAULT_QUERY_TIMEOUT == 30.0

    def test_max_retries(self) -> None:
        assert constants.DEFAULT_MAX_RETRIES == 3

    def test_retry_delay(self) -> None:
        assert constants.DEFAULT_RETRY_DELAY == 0.5


class TestBackendIdentifiers:
    def test_backend_sqlite(self) -> None:
        assert constants.BACKEND_SQLITE == "sqlite"

    def test_backend_postgres(self) -> None:
        assert constants.BACKEND_POSTGRES == "postgres"

    def test_backend_mysql(self) -> None:
        assert constants.BACKEND_MYSQL == "mysql"


class TestPaginationDefaults:
    def test_default_page_size(self) -> None:
        assert constants.DEFAULT_PAGE_SIZE == 20
        assert isinstance(constants.DEFAULT_PAGE_SIZE, int)

    def test_max_page_size(self) -> None:
        assert constants.MAX_PAGE_SIZE == 1000
        assert isinstance(constants.MAX_PAGE_SIZE, int)

    def test_default_cursor_size(self) -> None:
        assert constants.DEFAULT_CURSOR_SIZE == 20
        assert isinstance(constants.DEFAULT_CURSOR_SIZE, int)


class TestAllExports:
    def test_all_exports_are_accessible(self) -> None:
        expected_exports = [
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
            "ENV_NESTED_DELIMITER",
            "ENV_PREFIX",
            "MAX_PAGE_SIZE",
        ]
        for name in expected_exports:
            assert hasattr(constants, name), f"Missing export: {name}"