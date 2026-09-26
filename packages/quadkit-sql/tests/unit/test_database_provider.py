"""DatabaseService provider lifecycle and resolution tests."""

"""Unit tests for DatabaseService"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from quadkit.contracts.exceptions import ConfigurationError
from quadkit.contracts import (
    ConnectionPoolProtocol,
    DatabaseProviderProtocol,
    MigrationManagerProtocol,
    QueryLoggerProtocol,
    HealthStatus,
)
from quadkit.sql.config import DatabaseConfig
from quadkit.sql.managers import ScopedUnitOfWork
from quadkit.sql.providers import (
    DatabaseService,
)
from quadkit.di.provider import Provider

# Conditionally import optional providers
try:
    from quadkit.sql.providers.postgres_provider import PostgresProvider

    _postgres_available = True
except ImportError:
    PostgresProvider = None
    _postgres_available = False

try:
    from quadkit.sql.providers.mysql_provider import MySQLProvider

    _mysql_available = True
except ImportError:
    MySQLProvider = None
    _mysql_available = False



class TestDatabaseProvider:
    """Test DatabaseService functionality"""

    @pytest.fixture
    def mock_container(self):
        """Create a mock DI container"""
        container = Mock()
        container.singleton = Mock()
        container.scoped = Mock()
        return container

    @pytest.fixture
    def mock_db_provider(self):
        """Create a mock database provider protocol"""
        from quadkit.contracts.core import HealthCheckResult
        from quadkit.contracts.core import HealthStatus

        provider = Mock(spec=DatabaseProviderProtocol)
        provider.connect = AsyncMock()
        provider.disconnect = AsyncMock()
        provider.health_check = AsyncMock(
            return_value=HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
        )
        provider.begin_transaction = AsyncMock()
        provider.commit_transaction = AsyncMock()
        provider.rollback_transaction = AsyncMock()
        provider.execute_query = AsyncMock()
        provider.execute_insert = AsyncMock()
        provider.execute_update = AsyncMock()
        provider.execute_delete = AsyncMock()
        provider.transaction = MagicMock()
        provider.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
        provider.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
        return provider

    @pytest.fixture
    def mock_connection_pool(self):
        """Create a mock connection pool"""
        pool = Mock(spec=ConnectionPoolProtocol)
        pool.initialize = AsyncMock()
        pool.shutdown = AsyncMock()
        return pool

    @pytest.fixture
    def mock_query_logger(self):
        """Create a mock query logger"""
        logger = Mock(spec=QueryLoggerProtocol)
        return logger

    @pytest.fixture
    def mock_migration_manager(self):
        """Create a mock migration manager"""
        manager = Mock(spec=MigrationManagerProtocol)
        manager.initialize_migration_table = AsyncMock()
        return manager

    def test_init_basic_sqlite(self):
        """Test initialization with SQLite URL"""
        provider = DatabaseService(
            DatabaseConfig.from_url("sqlite:///test.db"),
        )

        assert provider.config.backend.url.get_secret_value() == "sqlite:///test.db"
        assert provider.db_provider is None
        assert provider.connection_pool is None
        assert provider.query_logger is not None
        assert provider.migration_manager is None

    def test_init_postgres_url(self):
        """Test initialization with PostgreSQL URL"""
        provider = DatabaseService(DatabaseConfig.from_url("postgresql://user:pass@localhost/db"))

        assert provider.config.backend.url.get_secret_value() == "postgresql://user:pass@localhost/db"

    def test_init_mysql_url(self):
        """Test initialization with MySQL URL"""
        provider = DatabaseService(DatabaseConfig.from_url("mysql://user:pass@localhost/db"))

        assert provider.config.backend.url.get_secret_value() == "mysql://user:pass@localhost/db"

    def test_init_explicit_provider_type(self):
        """Test initialization with explicit provider type"""
        provider = DatabaseService(
            DatabaseConfig.from_url("custom://localhost/db"),
            provider_type="postgres",
        )

        assert provider.config.backend.url.get_secret_value() == "custom://localhost/db"
        assert provider._explicit_provider_type == "postgres"

    def test_init_unknown_url_scheme(self):
        """Test initialization with unknown URL scheme"""
        with pytest.raises(ConfigurationError):
            DatabaseService(DatabaseConfig.from_url("unknown://url"))

    def test_init_with_components(
        self, mock_connection_pool, mock_query_logger, mock_migration_manager,
    ):
        """Test initialization with all components provided"""
        provider = DatabaseService(
            DatabaseConfig.from_url("sqlite:///test.db"),
            connection_pool=mock_connection_pool,
            query_logger=mock_query_logger,
            migration_manager=mock_migration_manager,
        )

        assert provider.connection_pool == mock_connection_pool
        assert provider.query_logger == mock_query_logger
        assert provider.migration_manager == mock_migration_manager

    @patch.object(DatabaseService, "get_driver_loader")
    def test_create_provider_sqlite(self, mock_get_loader):
        """Test creating SQLite provider"""
        mock_loader = Mock()
        mock_get_loader.return_value = mock_loader
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        created = provider._create_driver_provider()

        assert created is not None
        # Verify the loader was called
        mock_loader.assert_called_once()
        assert created == mock_loader.return_value

    @patch.object(DatabaseService, "get_driver_loader")
    def test_create_provider_postgres(self, mock_get_loader):
        """Test creating PostgreSQL provider"""
        if not _postgres_available:
            pytest.skip(
                "PostgresProvider not available - optional dependency asyncpg not installed",
            )

        mock_loader = Mock()
        mock_get_loader.return_value = mock_loader
        provider = DatabaseService(DatabaseConfig.from_url("postgresql://url"), provider_type="postgres")
        created = provider._create_driver_provider()

        assert created is not None
        mock_loader.assert_called_once()
        assert created == mock_loader.return_value

    @patch.object(DatabaseService, "get_driver_loader")
    def test_create_provider_mysql(self, mock_get_loader):
        """Test creating MySQL provider"""
        if not _mysql_available:
            pytest.skip(
                "MySQLProvider not available - optional dependency aiomysql not installed",
            )

        mock_loader = Mock()
        mock_get_loader.return_value = mock_loader
        provider = DatabaseService(DatabaseConfig.from_url("mysql://url"), provider_type="mysql")
        created = provider._create_driver_provider()

        assert created is not None
        mock_loader.assert_called_once()
        assert created == mock_loader.return_value

    def test_create_provider_unknown_type(self):
        """Test creating provider with unknown type"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider._explicit_provider_type = "unknown"

        with pytest.raises(ValueError, match="Unsupported provider type"):
            provider._create_driver_provider()

    @pytest.mark.asyncio
    async def test_register_with_container(
        self,
        mock_container,
        mock_db_provider,
        mock_connection_pool,
        mock_query_logger,
        mock_migration_manager,
    ):
        """Test registering services with DI container via DatabaseProvider."""
        from quadkit.sql.di.provider import DatabaseProvider

        di_provider = DatabaseProvider("sqlite:///test.db")
        await di_provider.register(mock_container)

        # Verify key services were registered:
        # DatabaseService + DatabaseProviderProtocol + ConnectionPoolProtocol
        # + QueryLoggerProtocol + UnitOfWorkProtocol (scoped)
        assert mock_container.singleton.call_count >= 4
        assert mock_container.scoped.call_count == 1  # UnitOfWorkProtocol

    def test_get_current_context(self):
        """Test getting current database context"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        context = provider.get_current_context()

        assert context is None

    @pytest.mark.asyncio
    async def test_scoped_context(self):
        """Test scoped context manager"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))

        async with provider.scoped_context() as context:
            assert context is not None
            assert "connection" in context
            assert "transaction_level" in context
            assert "created_at" in context
            assert context["transaction_level"] == 0

            # Verify context is set
            current = provider.get_current_context()
            assert current is context

        # Context should be cleared after exit
        current = provider.get_current_context()
        assert current is None

    @pytest.mark.asyncio
    async def test_get_scoped_connection_no_pool_no_context(self, mock_db_provider):
        """Test getting scoped connection without pool and context"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider.db_provider = mock_db_provider
        mock_db_provider._create_connection = AsyncMock(return_value=Mock())

        # No context set
        connection = await provider.get_scoped_connection()

        mock_db_provider._create_connection.assert_called_once()
        assert connection is not None

    @pytest.mark.asyncio
    async def test_get_scoped_connection_with_existing_connection(
        self, mock_db_provider,
    ):
        """Test getting scoped connection when one already exists"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider.db_provider = mock_db_provider
        mock_db_provider._create_connection = AsyncMock()

        existing_conn = Mock()
        async with provider.scoped_context() as ctx:
            ctx["connection"] = existing_conn
            connection = await provider.get_scoped_connection()

        # Should have returned existing connection
        assert connection == existing_conn
        mock_db_provider._create_connection.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_scoped_connection_with_pool(self, mock_connection_pool):
        """Test acquiring a scoped connection from a connection pool and proper cleanup"""
        provider = DatabaseService(
            DatabaseConfig.from_url("sqlite:///test.db"), connection_pool=mock_connection_pool,
        )

        class DummyCM:
            def __init__(self):
                self.entered = False
                self.exited = False
                self.connection = object()

            async def __aenter__(self):
                self.entered = True
                return self.connection

            async def __aexit__(self, exc_type, exc, tb):
                self.exited = True

        cm = DummyCM()
        mock_connection_pool.get_connection.return_value = cm

        # Prevent boot() from being called (it would run a health check using
        # the mock pool's object() connection which has no .execute method).
        # This test is about scoped context + pool connection behaviour, not boot.
        provider.db_provider = MagicMock()

        async with provider.scoped_context() as context:
            conn = await provider.get_scoped_connection()
            assert conn is context["connection"]
            assert context.get("_connection_cm") is cm
            assert cm.entered is True

        # After exiting scoped_context the context manager should have been exited
        assert cm.exited is True

    @pytest.mark.asyncio
    async def test_boot_success(
        self, mock_db_provider, mock_connection_pool, mock_migration_manager,
    ):
        """Test successful boot"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider._create_driver_provider = Mock(return_value=mock_db_provider)
        mock_connection_pool._initialized = True
        provider.connection_pool = mock_connection_pool
        mock_migration_manager._initialized = True
        provider.migration_manager = mock_migration_manager

        await provider.boot()

        assert provider.db_provider == mock_db_provider
        mock_db_provider.connect.assert_called_once()
        # Connection pool is provided, so initialize should not be called
        mock_connection_pool.initialize.assert_not_called()
        # Migration manager is provided, so initialize_migration_table should not be called
        mock_migration_manager.initialize_migration_table.assert_not_called()
        mock_db_provider.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_boot_health_check_failure(self, mock_db_provider):
        """Test boot with health check failure"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider._create_driver_provider = Mock(return_value=mock_db_provider)
        from quadkit.contracts.core import HealthCheckResult
        from quadkit.contracts.core import HealthStatus

        mock_db_provider.health_check.return_value = HealthCheckResult(
            component="db",
            status=HealthStatus.UNHEALTHY,
            error="Failed",
        )

        with pytest.raises(RuntimeError, match="Database health check failed"):
            await provider.boot()

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_db_provider, mock_connection_pool):
        """Test shutdown"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider.db_provider = mock_db_provider
        provider.connection_pool = mock_connection_pool
        provider._started = True

        await provider.shutdown()

        mock_connection_pool.shutdown.assert_called_once()
        mock_db_provider.disconnect.assert_called_once()
        assert provider._started is False

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_db_provider):
        """Test health check when provider is available"""
        from quadkit.contracts.core import HealthCheckResult

        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider.db_provider = mock_db_provider
        mock_db_provider.health_check.return_value = HealthCheckResult(
            component="db",
            status=HealthStatus.HEALTHY,
            details={"message": "OK"},
        )

        result = await provider.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.details.get("message") == "OK"

    @pytest.mark.asyncio
    async def test_health_check_no_provider(self):
        """Test health check when provider is not initialized"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))

        result = await provider.health_check()

        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_exception(self, mock_db_provider):
        """Test health check when exception occurs"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider.db_provider = mock_db_provider
        mock_db_provider.health_check.side_effect = ConnectionError("Connection failed")

        result = await provider.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection failed" in (result.error or "")

    @pytest.mark.asyncio
    async def test_execute_query(self, mock_db_provider):
        """Test query execution delegation"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider.db_provider = mock_db_provider

        result = await provider.execute_query("SELECT * FROM test", ["param"])

        mock_db_provider.execute_query.assert_called_once_with(
            "SELECT * FROM test", ["param"],
        )
        # execute_query now normalises the result into a QueryResult
        from quadkit.contracts.data.sql.database import QueryResult
        assert isinstance(result, QueryResult)

    @pytest.mark.asyncio
    async def test_execute_insert(self, mock_db_provider):
        """Test insert execution delegation"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider.db_provider = mock_db_provider
        data = {"name": "test", "value": 42}

        result = await provider.execute_insert("test_table", data)

        mock_db_provider.execute_insert.assert_called_once_with("test_table", data)
        assert result == mock_db_provider.execute_insert.return_value

    @pytest.mark.asyncio
    async def test_execute_update(self, mock_db_provider):
        """Test update execution delegation"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider.db_provider = mock_db_provider
        data = {"name": "updated"}

        result = await provider.execute_update("test_table", data, "id = ?", [1])

        mock_db_provider.execute_update.assert_called_once_with(
            "test_table", data, "id = ?", [1],
        )
        assert result == mock_db_provider.execute_update.return_value

    @pytest.mark.asyncio
    async def test_execute_delete(self, mock_db_provider):
        """Test delete execution delegation"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider.db_provider = mock_db_provider

        result = await provider.execute_delete("test_table", "id = ?", [1])

        mock_db_provider.execute_delete.assert_called_once_with(
            "test_table", "id = ?", [1],
        )
        assert result == mock_db_provider.execute_delete.return_value

    @pytest.mark.asyncio
    async def test_transaction_context_manager(self, mock_db_provider):
        """Test transaction context manager delegation"""
        provider = DatabaseService(DatabaseConfig.from_url("sqlite:///test.db"))
        provider.db_provider = mock_db_provider

        async with provider.transaction():
            pass

        # Verify the context manager was used
        mock_db_provider.transaction.assert_called_once()
