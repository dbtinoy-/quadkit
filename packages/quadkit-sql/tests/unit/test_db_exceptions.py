"""Unit tests for quadkit-sql exceptions.

This module contains tests for the exception hierarchy in quadkit.sql.exceptions.
ConnectionRefusedError is intentionally named to shadow the Python builtin.
"""

from quadkit.sql.exceptions import (
    CheckConstraintError,
    ColumnNotFoundError,
    ConnectionPoolError,
    ConnectionRefusedError,
    ConnectionTimeoutError,
    CursorError,
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    DataError,
    DataQueryError,
    DataRepositoryError,
    DeadlockError,
    DriverError,
    DuplicateKeyError,
    EntityNotFoundError,
    ForeignKeyError,
    IntegrityError,
    LockError,
    NotNullViolationError,
    PaginationError,
    ParameterBindingError,
    QueryError,
    QuerySyntaxError,
    RepositoryError,
    SchemaError,
    SerializationError,
    TableNotFoundError,
    TransactionError,
    TransactionRollbackError,
    UnitOfWorkError,
)


class TestDatabaseExceptionHierarchy:
    """Tests for database exception hierarchy."""

    def test_database_error_inherits_from_quadkit_error(self) -> None:
        from quadkit.contracts.exceptions import QuadkitError

        assert issubclass(DatabaseError, QuadkitError)


class TestConnectionErrors:
    """Tests for connection-related exceptions."""

    def test_database_connection_error_inherits(self) -> None:
        assert issubclass(DatabaseConnectionError, DatabaseError)

    def test_connection_refused_error_inherits(self) -> None:
        assert issubclass(ConnectionRefusedError, DatabaseConnectionError)

    def test_connection_timeout_error_inherits(self) -> None:
        assert issubclass(ConnectionTimeoutError, DatabaseConnectionError)

    def test_connection_pool_error_inherits(self) -> None:
        assert issubclass(ConnectionPoolError, DatabaseConnectionError)


class TestQueryErrors:
    """Tests for query-related exceptions."""

    def test_query_error_inherits(self) -> None:
        assert issubclass(QueryError, DatabaseError)

    def test_query_syntax_error_inherits(self) -> None:
        assert issubclass(QuerySyntaxError, QueryError)

    def test_parameter_binding_error_inherits(self) -> None:
        assert issubclass(ParameterBindingError, QueryError)


class TestIntegrityErrors:
    """Tests for integrity-related exceptions."""

    def test_integrity_error_inherits(self) -> None:
        assert issubclass(IntegrityError, DatabaseError)

    def test_duplicate_key_error_inherits(self) -> None:
        assert issubclass(DuplicateKeyError, IntegrityError)

    def test_foreign_key_error_inherits(self) -> None:
        assert issubclass(ForeignKeyError, IntegrityError)

    def test_not_null_violation_error_inherits(self) -> None:
        assert issubclass(NotNullViolationError, IntegrityError)

    def test_check_constraint_error_inherits(self) -> None:
        assert issubclass(CheckConstraintError, IntegrityError)


class TestTransactionErrors:
    """Tests for transaction-related exceptions."""

    def test_transaction_error_inherits(self) -> None:
        assert issubclass(TransactionError, DatabaseError)

    def test_serialization_error_inherits(self) -> None:
        assert issubclass(SerializationError, TransactionError)

    def test_transaction_rollback_error_inherits(self) -> None:
        assert issubclass(TransactionRollbackError, TransactionError)

    def test_deadlock_error_inherits(self) -> None:
        assert issubclass(DeadlockError, TransactionError)


class TestSchemaErrors:
    """Tests for schema-related exceptions."""

    def test_schema_error_inherits(self) -> None:
        assert issubclass(SchemaError, DatabaseError)

    def test_table_not_found_error_inherits(self) -> None:
        assert issubclass(TableNotFoundError, SchemaError)

    def test_column_not_found_error_inherits(self) -> None:
        assert issubclass(ColumnNotFoundError, SchemaError)


class TestLockAndTimeoutErrors:
    """Tests for lock and timeout exceptions."""

    def test_lock_error_inherits(self) -> None:
        assert issubclass(LockError, DatabaseError)

    def test_database_timeout_error_inherits(self) -> None:
        assert issubclass(DatabaseTimeoutError, DatabaseError)


class TestRepositoryAndUnitOfWork:
    """Tests for repository and unit of work exceptions."""

    def test_repository_error_inherits(self) -> None:
        assert issubclass(RepositoryError, DatabaseError)

    def test_unit_of_work_error_inherits(self) -> None:
        assert issubclass(UnitOfWorkError, DatabaseError)


class TestDriverError:
    """Tests for driver error."""

    def test_driver_error_inherits(self) -> None:
        assert issubclass(DriverError, DatabaseError)


class TestDataLayerExceptions:
    """Tests for data layer exceptions."""

    def test_data_error_inherits_from_quadkit_error(self) -> None:
        from quadkit.contracts.exceptions import QuadkitError

        assert issubclass(DataError, QuadkitError)

    def test_data_query_error_inherits(self) -> None:
        assert issubclass(DataQueryError, DataError)

    def test_pagination_error_inherits(self) -> None:
        assert issubclass(PaginationError, DataError)

    def test_entity_not_found_error_inherits(self) -> None:
        assert issubclass(EntityNotFoundError, DataError)

    def test_data_repository_error_inherits(self) -> None:
        assert issubclass(DataRepositoryError, DataError)

    def test_cursor_error_inherits(self) -> None:
        assert issubclass(CursorError, DataError)


class TestExceptionAllExports:
    """Tests to verify __all__ exports."""

    def test_all_contains_all_exceptions(self) -> None:
        from quadkit.sql import exceptions as exc_module

        expected = [
            "CheckConstraintError",
            "ColumnNotFoundError",
            "ConnectionPoolError",
            "ConnectionRefusedError",
            "ConnectionTimeoutError",
            "CursorError",
            "DataError",
            "DataQueryError",
            "DataRepositoryError",
            "DatabaseConnectionError",
            "DatabaseError",
            "DatabaseTimeoutError",
            "DeadlockError",
            "DriverError",
            "DuplicateKeyError",
            "EntityNotFoundError",
            "ForeignKeyError",
            "IntegrityError",
            "LockError",
            "MigrationError",
            "NotFoundError",
            "NotNullViolationError",
            "PaginationError",
            "ParameterBindingError",
            "QueryError",
            "QuerySyntaxError",
            "RepositoryError",
            "SchemaError",
            "SerializationError",
            "TableNotFoundError",
            "TransactionError",
            "TransactionRollbackError",
            "UnitOfWorkError",
        ]
        for item in expected:
            assert item in exc_module.__all__
