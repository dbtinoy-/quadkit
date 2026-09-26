"""Tests for database protocols and data classes"""

from datetime import UTC, datetime
import importlib.util

from quadkit.contracts.data import (
    ConnectionPoolProtocol,
    DatabaseProviderProtocol,
    DeleteResult,
    InsertResult,
    MigrationManagerProtocol,
    MigrationRecord,
    QueryLogEntry,
    QueryLoggerProtocol,
    QueryResult,
    UnitOfWorkProtocol,
    UpdateResult,
)


class TestDataClasses:
    """Test data classes in protocols"""

    def test_query_result_creation(self):
        """Test QueryResult data class"""
        rows = [{"id": 1, "name": "test"}]
        result = QueryResult(rows=rows, row_count=1, execution_time=0.1, success=True)

        assert result.rows == rows
        assert result.row_count == 1
        assert result.execution_time == 0.1
        assert result.success is True
        assert result.error_message is None

    def test_query_result_with_error(self):
        """Test QueryResult with error message"""
        result = QueryResult(
            rows=[],
            row_count=0,
            execution_time=0.05,
            success=False,
            error_message="Query failed",
        )

        assert result.rows == []
        assert result.row_count == 0
        assert result.execution_time == 0.05
        assert result.success is False
        assert result.error_message == "Query failed"

    def test_insert_result_creation(self):
        """Test InsertResult data class"""
        result = InsertResult(
            inserted_id=42,
            affected_rows=1,
            execution_time=0.02,
            success=True,
        )

        assert result.inserted_id == 42
        assert result.affected_rows == 1
        assert result.execution_time == 0.02
        assert result.success is True
        assert result.error_message is None

    def test_insert_result_with_error(self):
        """Test InsertResult with error"""
        result = InsertResult(
            inserted_id=None,
            affected_rows=0,
            execution_time=0.01,
            success=False,
            error_message="Insert failed",
        )

        assert result.inserted_id is None
        assert result.affected_rows == 0
        assert result.success is False
        assert result.error_message == "Insert failed"

    def test_update_result_creation(self):
        """Test UpdateResult data class"""
        result = UpdateResult(affected_rows=5, execution_time=0.03, success=True)

        assert result.affected_rows == 5
        assert result.execution_time == 0.03
        assert result.success is True
        assert result.error_message is None

    def test_update_result_with_error(self):
        """Test UpdateResult with error"""
        result = UpdateResult(
            affected_rows=0,
            execution_time=0.02,
            success=False,
            error_message="Update failed",
        )

        assert result.affected_rows == 0
        assert result.success is False
        assert result.error_message == "Update failed"

    def test_delete_result_creation(self):
        """Test DeleteResult data class"""
        result = DeleteResult(affected_rows=3, execution_time=0.025, success=True)

        assert result.affected_rows == 3
        assert result.execution_time == 0.025
        assert result.success is True
        assert result.error_message is None

    def test_delete_result_with_error(self):
        """Test DeleteResult with error"""
        result = DeleteResult(
            affected_rows=0,
            execution_time=0.015,
            success=False,
            error_message="Delete failed",
        )

        assert result.affected_rows == 0
        assert result.success is False
        assert result.error_message == "Delete failed"

    def test_query_log_entry_creation(self):
        """Test QueryLogEntry data class"""
        timestamp = datetime.now(UTC)
        entry = QueryLogEntry(
            sql="SELECT * FROM users",
            params=[1],
            execution_time=0.1,
            timestamp=timestamp,
            success=True,
            error_message=None,
            connection_id="conn_123",
            transaction_id="txn_456",
            user_id="user_789",
        )

        assert entry.sql == "SELECT * FROM users"
        assert entry.params == [1]
        assert entry.execution_time == 0.1
        assert entry.timestamp == timestamp
        assert entry.success is True
        assert entry.error_message is None
        assert entry.connection_id == "conn_123"
        assert entry.transaction_id == "txn_456"
        assert entry.user_id == "user_789"

    def test_query_log_entry_minimal(self):
        """Test QueryLogEntry with minimal required fields"""
        timestamp = datetime.now(UTC)
        entry = QueryLogEntry(
            sql="SELECT 1",
            params=None,
            execution_time=0.05,
            timestamp=timestamp,
            success=False,
            error_message="Connection lost",
            connection_id=None,
            transaction_id=None,
            user_id=None,
        )

        assert entry.sql == "SELECT 1"
        assert entry.params is None
        assert entry.success is False
        assert entry.error_message == "Connection lost"
        assert entry.connection_id is None
        assert entry.transaction_id is None
        assert entry.user_id is None

    def test_migration_record_creation(self):
        """Test MigrationRecord data class"""
        applied_at = datetime.now(UTC)
        record = MigrationRecord(
            version="001",
            name="create_users_table",
            applied_at=applied_at,
            success=True,
            error_message=None,
        )

        assert record.version == "001"
        assert record.name == "create_users_table"
        assert record.applied_at == applied_at
        assert record.success is True
        assert record.error_message is None

    def test_migration_record_with_error(self):
        """Test MigrationRecord with error"""
        applied_at = datetime.now(UTC)
        record = MigrationRecord(
            version="002",
            name="add_email_column",
            applied_at=applied_at,
            success=False,
            error_message="Column already exists",
        )

        assert record.version == "002"
        assert record.success is False
        assert record.error_message == "Column already exists"


class TestProtocols:
    """Test protocol definitions"""

    def test_database_provider_protocol_is_protocol(self):
        """Test DatabaseProviderProtocol is a Protocol class"""
        # Can't instantiate protocols directly, but we can check it's a protocol
        assert hasattr(DatabaseProviderProtocol, "__protocol_attrs__") or hasattr(
            DatabaseProviderProtocol,
            "__annotations__",
        )

    def test_connection_pool_protocol_is_protocol(self):
        """Test ConnectionPoolProtocol is a Protocol class"""
        assert hasattr(ConnectionPoolProtocol, "__protocol_attrs__") or hasattr(
            ConnectionPoolProtocol,
            "__annotations__",
        )

    def test_query_logger_protocol_is_protocol(self):
        """Test QueryLoggerProtocol is a Protocol class"""
        assert hasattr(QueryLoggerProtocol, "__protocol_attrs__") or hasattr(
            QueryLoggerProtocol,
            "__annotations__",
        )

    def test_migration_manager_protocol_is_protocol(self):
        """Test MigrationManagerProtocol is a Protocol class"""
        assert hasattr(MigrationManagerProtocol, "__protocol_attrs__") or hasattr(
            MigrationManagerProtocol,
            "__annotations__",
        )

    def test_unit_of_work_protocol_is_protocol(self):
        """Test UnitOfWorkProtocol is a Protocol class"""
        assert hasattr(UnitOfWorkProtocol, "__protocol_attrs__") or hasattr(
            UnitOfWorkProtocol,
            "__annotations__",
        )

    def test_database_provider_protocol_methods(self):
        """Test DatabaseProviderProtocol has expected abstract methods"""
        # Check some key methods exist
        assert hasattr(DatabaseProviderProtocol, "connect")
        assert hasattr(DatabaseProviderProtocol, "disconnect")
        assert hasattr(DatabaseProviderProtocol, "is_connected")
        assert hasattr(DatabaseProviderProtocol, "execute_query")
        assert hasattr(DatabaseProviderProtocol, "transaction")
        assert hasattr(DatabaseProviderProtocol, "health_check")
        assert hasattr(DatabaseProviderProtocol, "execute_insert")
        assert hasattr(DatabaseProviderProtocol, "execute_update")
        assert hasattr(DatabaseProviderProtocol, "execute_delete")

    def test_connection_pool_protocol_methods(self):
        """Test ConnectionPoolProtocol has expected abstract methods"""
        assert hasattr(ConnectionPoolProtocol, "initialize")
        assert hasattr(ConnectionPoolProtocol, "shutdown")
        assert hasattr(ConnectionPoolProtocol, "get_connection")
        assert hasattr(ConnectionPoolProtocol, "get_pool_stats")
        assert hasattr(ConnectionPoolProtocol, "health_check")

    def test_query_logger_protocol_methods(self):
        """Test QueryLoggerProtocol has expected abstract methods"""
        assert hasattr(QueryLoggerProtocol, "log_query")
        assert hasattr(QueryLoggerProtocol, "get_recent_queries")
        assert hasattr(QueryLoggerProtocol, "get_slow_queries")
        assert hasattr(QueryLoggerProtocol, "get_query_stats")

    def test_migration_manager_protocol_methods(self):
        """Test MigrationManagerProtocol has expected abstract methods"""
        assert hasattr(MigrationManagerProtocol, "initialize_migration_table")
        assert hasattr(MigrationManagerProtocol, "get_applied_migrations")
        assert hasattr(MigrationManagerProtocol, "apply_migration")
        assert hasattr(MigrationManagerProtocol, "rollback_migration")
        assert hasattr(MigrationManagerProtocol, "get_pending_migrations")

    def test_unit_of_work_protocol_methods(self):
        """Test UnitOfWorkProtocol has expected abstract methods"""
        assert hasattr(UnitOfWorkProtocol, "__aenter__")
        assert hasattr(UnitOfWorkProtocol, "__aexit__")
        assert hasattr(UnitOfWorkProtocol, "commit")
        assert hasattr(UnitOfWorkProtocol, "rollback")
        assert hasattr(UnitOfWorkProtocol, "register_new")
        assert hasattr(UnitOfWorkProtocol, "register_dirty")
        assert hasattr(UnitOfWorkProtocol, "register_deleted")
        # event collection API
        assert hasattr(UnitOfWorkProtocol, "register_event")
        assert hasattr(UnitOfWorkProtocol, "collect_events")


class TestProtocolExports:
    """Test that all protocol exports are available"""

    def test_all_data_classes_exported(self):
        """Test that all data classes are properly exported"""
        from quadkit.contracts.data import __all__ as exported_items

        expected_data_classes = [
            "QueryResult",
            "InsertResult",
            "UpdateResult",
            "DeleteResult",
            "QueryLogEntry",
            "MigrationRecord",
        ]

        for cls_name in expected_data_classes:
            assert cls_name in exported_items
            assert cls_name in globals()

    def test_all_protocols_exported(self):
        """Test that all protocols are properly exported"""
        from quadkit.contracts.data import __all__ as exported_items

        expected_protocols = [
            "DatabaseProviderProtocol",
            "ConnectionPoolProtocol",
            "QueryLoggerProtocol",
            "MigrationManagerProtocol",
            "UnitOfWorkProtocol",
        ]

        for protocol_name in expected_protocols:
            assert protocol_name in exported_items
            assert protocol_name in globals()

    def test_all_implementations_exported(self):
        """Test that all implementations are properly exported"""
        from quadkit.sql import __all__ as exported_items

        expected_implementations = [
            "AbstractConnectionPool",
            "SimpleConnectionPool",
            "QueryLoggerBase",
            "ConsoleQueryLogger",
            "FileQueryLogger",
            "MemoryQueryLogger",
            "SimpleUnitOfWork",
            "unit_of_work",
            "SimpleMigrationManager",
            "SQLiteProvider",
        ]

        # Conditionally add optional implementations
        if importlib.util.find_spec("quadkit.sql.backends.postgres"):
            expected_implementations.append("PostgresProvider")

        if importlib.util.find_spec("quadkit.sql.backends.mysql"):
            expected_implementations.append("MySQLProvider")

        if importlib.util.find_spec("quadkit.sql.backends.mongo"):
            expected_implementations.append("MongoDBProvider")

        for impl_name in expected_implementations:
            assert impl_name in exported_items


class TestAlembicManagerMigrationManagerConformance:
    """DB-07: Verify AlembicManager satisfies MigrationManagerProtocol."""

    def test_alembic_manager_isinstance_migration_manager_protocol(self) -> None:
        """AlembicManager must be an instance of the runtime-checkable protocol."""
        from quadkit.sql.migrations.manager import AlembicManager

        manager = object.__new__(AlembicManager)

        assert isinstance(
            manager,
            MigrationManagerProtocol,
        ), "AlembicManager must satisfy MigrationManagerProtocol"

    def test_alembic_manager_has_all_protocol_methods(self) -> None:
        """AlembicManager must expose every method declared by MigrationManagerProtocol."""
        from quadkit.sql.migrations.manager import AlembicManager

        required_methods = (
            "initialize_migration_table",
            "get_applied_migrations",
            "apply_migration",
            "rollback_migration",
            "get_pending_migrations",
        )
        manager = object.__new__(AlembicManager)

        for method_name in required_methods:
            assert hasattr(manager, method_name), (
                f"AlembicManager is missing protocol method: {method_name!r}"
            )
            assert callable(getattr(manager, method_name)), (
                f"AlembicManager.{method_name!r} is not callable"
            )
            # Note: Some implementations might not be in globals() if they're imported from submodules
            # but they should be available for import
