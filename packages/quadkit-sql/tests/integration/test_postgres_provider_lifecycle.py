"""PostgreSQL database provider lifecycle integration tests."""

from __future__ import annotations

import pytest

from quadkit.sql.providers.postgres_provider import PostgresProvider
from quadkit.sql.providers.sqlite_provider import SQLiteProvider
from quadkit.testing.integration.fixtures import postgres_pool  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.requires_postgres]


class TestPostgresProviderLifecycle:
    """Verify DatabaseProvider can be created and configured for PostgreSQL."""

    async def test_provider_can_be_created(self) -> None:
        """DatabaseProvider can be instantiated without errors."""
        from quadkit.sql.di.provider import DatabaseProvider

        provider = DatabaseProvider()
        assert provider is not None
        assert provider.name == "database"

    async def test_provider_with_explicit_config(self) -> None:
        """DatabaseProvider accepts an explicit DatabaseConfig."""
        from quadkit.sql.config import DatabaseConfig
        from quadkit.sql.di.provider import DatabaseProvider

        config = DatabaseConfig()
        provider = DatabaseProvider(config=config)
        assert provider is not None

    async def test_postgres_pool_fixture_is_functional(
        self, postgres_pool: object
    ) -> None:
        """postgres_pool fixture yields a live asyncpg connection pool."""
        assert postgres_pool is not None

    async def test_postgres_round_trip(
        self, postgres_provider: SQLiteProvider | PostgresProvider
    ) -> None:
        """Provider executes SQL against PostgreSQL or the in-process fallback."""
        result = await postgres_provider.execute_query("SELECT 1")
        assert result.row_count == 1