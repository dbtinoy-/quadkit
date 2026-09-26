"""Integration tests for database provider and SQLAlchemy integration."""

import pytest

# Skip integration tests that require a DB driver if the driver isn't installed
pytest.importorskip("aiosqlite")

# Integration tests should rely on the canonical packages. Skip the entire
# module if the optional `quadkit.sql` package is not installed so CI can run
# without DB provider present.
import importlib

try:
    importlib.import_module("quadkit.sql.provider")
except ImportError:
    pytest.skip(
        "Integration DB tests require 'quadkit.sql' package",
        allow_module_level=True,
    )

# Skip database module tests if the database DI module is not present in the workspace
import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.exceptions import DatabaseError

pytest.importorskip("quadkit.di.modules.database")
from quadkit.config import DatabaseConfig
from quadkit.di.modules.database import DatabaseModule
from quadkit.di.providers.database import DatabaseService

# Optional imports: state store implementations live in specialized packages
try:
    from quadkit.cache.backends.memory_state import MemoryStateStore
except ImportError:
    MemoryStateStore = None

# Import Postgres state store safely to avoid executing module code at collection time
# (some optional driver modules may contain syntax that causes SyntaxError on import)
try:
    import importlib.util

    spec = importlib.util.find_spec("quadkit.sql.backends.postgres")
    if spec is None:
        PostgresStateStore = None
    else:
        try:
            mod = importlib.import_module("quadkit.sql.backends.postgres")
            PostgresStateStore = getattr(mod, "PostgresStateStore", None)
        except ImportError:
            PostgresStateStore = None
except ImportError:
    PostgresStateStore = None

# Migration manager comes from `quadkit.sql`
try:
    from quadkit.sql.migrations.api import AlembicManager as MigrationManager
except ImportError:
    MigrationManager = None

# Database health check helper (optional)
try:
    from quadkit.di.providers.database import DatabaseHealthCheck
except ImportError:
    DatabaseHealthCheck = None


class TestDatabaseProviderIntegration:
    """Integration tests for database provider functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_provider_initialization(self):
        """Test database provider initialization."""
        config = DatabaseConfig(url="sqlite+aiosqlite:///:memory:")

        provider = DatabaseService(config)

        # Should not be initialized yet
        assert provider.engine is None
        assert provider.session_factory is None

        # Start the provider
        await provider.start()

        # Should be initialized now
        assert provider.engine is not None
        assert provider.session_factory is not None

        # Clean up
        await provider.stop()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_provider_health_check(self):
        """Test database provider health check."""
        config = DatabaseConfig(url="sqlite+aiosqlite:///:memory:")

        provider = DatabaseService(config)
        await provider.start()

        # Health check should pass
        status = await provider.health_check()
        assert status["status"] == HealthStatus.HEALTHY.value
        assert status["healthy"] is True

        await provider.stop()

    @pytest.mark.asyncio
    async def test_provider_session_context(self):
        """Test database session context manager."""
        config = DatabaseConfig(url="sqlite+aiosqlite:///:memory:")

        provider = DatabaseService(config)
        await provider.start()

        # Test session context
        async with provider.session() as session:
            # Execute a simple query
            result = await session.execute("SELECT 1 as test")
            row = result.fetchone()
            assert row.test == 1

        await provider.stop()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_initialization(self):
        """Test migration manager initialization."""
        config = DatabaseConfig(url="sqlite+aiosqlite:///:memory:")
        provider = DatabaseService(config)
        await provider.start()

        manager = MigrationManager(provider)
        await manager.initialize()

        # Apply a migration
        await manager.apply_migration(
            "001",
            "create_users_table",
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)",
        )

        # Check that migration was recorded
        migrations = await manager.get_applied_migrations()
        assert len(migrations) == 1
        assert migrations[0]["version"] == "001"
        assert migrations[0]["name"] == "create_users_table"

        # Check that table was created
        async with provider.session() as session:
            result = await session.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'",
            )
            assert result.fetchone() is not None

        # Try to apply the same migration again (should not fail)
        await manager.apply_migration(
            "001",
            "create_users_table",
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)",
        )

        # Should still only have one migration record
        migrations = await manager.get_applied_migrations()
        assert len(migrations) == 1

        await provider.stop()


class TestDatabaseModuleIntegration:
    """Integration tests for database module for dependency injection."""

    @pytest.mark.asyncio
    async def test_database_module_configuration(self):
        """Test database module configuration."""
        from quadkit.di.container import Container

        config = DatabaseConfig(url="sqlite+aiosqlite:///:memory:")
        module = DatabaseModule(config)

        container = Container()
        await module.configure(container)

        # Check that services are registered
        db_provider = await container.resolve(DatabaseService)
        assert db_provider is not None
        assert isinstance(db_provider, DatabaseService)

        migration_manager = await container.resolve(MigrationManager)
        assert migration_manager is not None

        session_factory = await container.resolve("db_session_factory")
        assert session_factory is not None

    @pytest.mark.asyncio
    async def test_database_module_lifecycle(self):
        """Test database module lifecycle."""
        from quadkit.di.container import Container

        config = DatabaseConfig(url="sqlite+aiosqlite:///:memory:")
        module = DatabaseModule(config)

        container = Container()
        await module.configure(container)

        # Start module
        await module.start(container)

        health = await module.health_check(container)
        assert health["database"]["healthy"] is True
        assert health["database"]["status"] == "healthy"

        # Stop module
        await module.stop(container)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_database_module_with_invalid_config(self):
        """Test database module with invalid configuration."""
        from quadkit.di.container import Container

        config = DatabaseConfig(url="invalid://url")
        module = DatabaseModule(config)

        container = Container()
        await module.configure(container)

        # Starting should fail
        with pytest.raises(DatabaseError):
            await module.start(container)


class TestDatabaseHealthCheckIntegration:
    """Integration tests for database health check functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check when database is healthy."""
        if DatabaseHealthCheck is None:
            pytest.skip(
                "DatabaseHealthCheck not available in this workspace",
                allow_module_level=False,
            )

        config = DatabaseConfig(url="sqlite+aiosqlite:///:memory:")
        provider = DatabaseService(config)
        await provider.start()

        health_check = DatabaseHealthCheck(provider.engine)

        status = await health_check.check_health()
        assert status == HealthStatus.HEALTHY

        await provider.stop()
