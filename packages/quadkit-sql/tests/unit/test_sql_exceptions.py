"""Unit tests for quadkit.sql.exceptions module."""

import pytest

from quadkit.contracts.exceptions import QuadkitError
from quadkit.sql import exceptions as exc


class TestExceptionHierarchy:
    """Tests for exception hierarchy."""

    def test_database_error_inherits_from_quadkit_error(self):
        assert issubclass(exc.DatabaseError, QuadkitError)

    def test_base_exceptions_all_inherit_from_database_error(self):
        for exc_class in [
            exc.DatabaseConnectionError,
            exc.QueryError,
            exc.IntegrityError,
            exc.TransactionError,
            exc.SchemaError,
            exc.LockError,
            exc.DatabaseTimeoutError,
            exc.RepositoryError,
            exc.UnitOfWorkError,
            exc.DriverError,
        ]:
            assert issubclass(exc_class, exc.DatabaseError)


class TestConnectionErrors:
    """Tests for connection-related exceptions."""

    def test_database_connection_error_inherits(self):
        assert issubclass(exc.DatabaseConnectionError, exc.DatabaseError)

    def test_connection_refused_error_inherits(self):
        assert issubclass(exc.ConnectionRefusedError, exc.DatabaseConnectionError)

    def test_connection_timeout_error_inherits(self):
        assert issubclass(exc.ConnectionTimeoutError, exc.DatabaseConnectionError)

    def test_connection_pool_error_inherits(self):
        assert issubclass(exc.ConnectionPoolError, exc.DatabaseConnectionError)

    def test_connection_refused_error_attributes(self):
        error = exc.ConnectionRefusedError(
            "Connection refused",
            host="localhost",
            port=5432,
        )
        assert error.host == "localhost"
        assert error.port == 5432

    def test_connection_timeout_error_attributes(self):
        error = exc.ConnectionTimeoutError(
            "Connection timed out",
            host="localhost",
            port=5432,
        )
        assert error.host == "localhost"
        assert error.port == 5432

    def test_connection_pool_error_attributes(self):
        error = exc.ConnectionPoolError("Pool exhausted", host="localhost", port=5432)
        assert error.host == "localhost"
        assert error.port == 5432


class TestQueryErrors:
    """Tests for query-related exceptions."""

    def test_query_error_inherits(self):
        assert issubclass(exc.QueryError, exc.DatabaseError)

    def test_query_syntax_error_inherits(self):
        assert issubclass(exc.QuerySyntaxError, exc.QueryError)

    def test_parameter_binding_error_inherits(self):
        assert issubclass(exc.ParameterBindingError, exc.QueryError)

    def test_query_error_attributes(self):
        error = exc.QueryError("Query failed", sql="SELECT * FROM users", params={"id": 1})
        assert error.sql == "SELECT * FROM users"
        assert error.params == {"id": 1}

    def test_query_syntax_error_attributes(self):
        error = exc.QuerySyntaxError("Syntax error", sql="SELEC * FROM users")
        assert error.sql == "SELEC * FROM users"


class TestIntegrityErrors:
    """Tests for integrity-related exceptions."""

    def test_integrity_error_inherits(self):
        assert issubclass(exc.IntegrityError, exc.DatabaseError)

    def test_duplicate_key_error_inherits(self):
        assert issubclass(exc.DuplicateKeyError, exc.IntegrityError)

    def test_foreign_key_error_inherits(self):
        assert issubclass(exc.ForeignKeyError, exc.IntegrityError)

    def test_not_null_violation_error_inherits(self):
        assert issubclass(exc.NotNullViolationError, exc.IntegrityError)

    def test_check_constraint_error_inherits(self):
        assert issubclass(exc.CheckConstraintError, exc.IntegrityError)

    def test_integrity_error_attributes(self):
        error = exc.IntegrityError(
            "Constraint violated",
            constraint="unique_email",
            table="users",
        )
        assert error.constraint == "unique_email"
        assert error.table == "users"

    def test_not_null_violation_error_attributes(self):
        error = exc.NotNullViolationError(
            "Column cannot be null",
            column="email",
            table="users",
        )
        assert error.column == "email"


class TestTransactionErrors:
    """Tests for transaction-related exceptions."""

    def test_transaction_error_inherits(self):
        assert issubclass(exc.TransactionError, exc.DatabaseError)

    def test_serialization_error_inherits(self):
        assert issubclass(exc.SerializationError, exc.TransactionError)

    def test_transaction_rollback_error_inherits(self):
        assert issubclass(exc.TransactionRollbackError, exc.TransactionError)

    def test_deadlock_error_inherits(self):
        assert issubclass(exc.DeadlockError, exc.TransactionError)


class TestOptimisticLockError:
    """Tests for OptimisticLockError."""

    def test_inherits_from_database_error(self):
        assert issubclass(exc.OptimisticLockError, exc.DatabaseError)

    def test_attributes(self):
        error = exc.OptimisticLockError(
            entity_type="User",
            entity_id=123,
            expected_version=2,
        )
        assert error.entity_type == "User"
        assert error.entity_id == 123
        assert error.expected_version == 2


class TestSchemaErrors:
    """Tests for schema-related exceptions."""

    def test_schema_error_inherits(self):
        assert issubclass(exc.SchemaError, exc.DatabaseError)

    def test_table_not_found_error_inherits(self):
        assert issubclass(exc.TableNotFoundError, exc.SchemaError)

    def test_column_not_found_error_inherits(self):
        assert issubclass(exc.ColumnNotFoundError, exc.SchemaError)


class TestMiscErrors:
    """Tests for miscellaneous exceptions."""

    def test_lock_error_inherits(self):
        assert issubclass(exc.LockError, exc.DatabaseError)

    def test_database_timeout_error_inherits(self):
        assert issubclass(exc.DatabaseTimeoutError, exc.DatabaseError)

    def test_repository_error_inherits(self):
        assert issubclass(exc.RepositoryError, exc.DatabaseError)

    def test_unit_of_work_error_inherits(self):
        assert issubclass(exc.UnitOfWorkError, exc.DatabaseError)

    def test_driver_error_inherits(self):
        assert issubclass(exc.DriverError, exc.DatabaseError)

    def test_driver_error_attributes(self):
        error = exc.DriverError(
            "Driver error",
            driver="asyncpg",
            operation="connect",
        )
        assert error.driver == "asyncpg"
        assert error.operation == "connect"


class TestDataLayerExceptions:
    """Tests for data layer exceptions."""

    def test_data_error_inherits_from_quadkit_error(self):
        assert issubclass(exc.DataError, QuadkitError)

    def test_data_query_error_inherits(self):
        assert issubclass(exc.DataQueryError, exc.DataError)

    def test_pagination_error_inherits(self):
        assert issubclass(exc.PaginationError, exc.DataError)

    def test_entity_not_found_error_inherits(self):
        assert issubclass(exc.EntityNotFoundError, exc.DataError)

    def test_data_repository_error_inherits(self):
        assert issubclass(exc.DataRepositoryError, exc.DataError)

    def test_cursor_error_inherits(self):
        assert issubclass(exc.CursorError, exc.DataError)

    def test_entity_not_found_error_attributes(self):
        error = exc.EntityNotFoundError("User", 123)
        assert error.entity_type == "User"
        assert error.entity_id == 123


class TestMigrationErrorReExport:
    """Tests for MigrationError re-export."""

    def test_migration_error_exported(self):
        assert exc.MigrationError is not None

    def test_migration_error_in_all(self):
        assert "MigrationError" in exc.__all__

    def test_not_found_error_exported(self):
        assert exc.NotFoundError is not None


class TestExceptionCodes:
    """Tests for exception error codes."""

    def test_database_error_has_code(self):
        error = exc.DatabaseError("Test error")
        assert hasattr(error, "_code")

    def test_connection_refused_has_code(self):
        error = exc.ConnectionRefusedError("Test error")
        assert error._code == "QK_ERR_SQL_002"

    def test_connection_timeout_has_code(self):
        error = exc.ConnectionTimeoutError("Test error")
        assert error._code == "QK_ERR_SQL_003"

    def test_connection_pool_has_code(self):
        error = exc.ConnectionPoolError("Test error")
        assert error._code == "QK_ERR_SQL_004"

    def test_query_error_has_code(self):
        error = exc.QueryError("Test error")
        assert error._code == "QK_ERR_SQL_005"

    def test_query_syntax_error_has_code(self):
        error = exc.QuerySyntaxError("Test error")
        assert error._code == "QK_ERR_SQL_006"

    def test_parameter_binding_error_has_code(self):
        error = exc.ParameterBindingError("Test error")
        assert error._code == "QK_ERR_SQL_007"

    def test_integrity_error_has_code(self):
        error = exc.IntegrityError("Test error")
        assert error._code == "QK_ERR_SQL_008"

    def test_duplicate_key_error_has_code(self):
        error = exc.DuplicateKeyError("Test error")
        assert error._code == "QK_ERR_SQL_009"

    def test_foreign_key_error_has_code(self):
        error = exc.ForeignKeyError("Test error")
        assert error._code == "QK_ERR_SQL_010"

    def test_not_null_violation_error_has_code(self):
        error = exc.NotNullViolationError("Test error")
        assert error._code == "QK_ERR_SQL_011"

    def test_check_constraint_error_has_code(self):
        error = exc.CheckConstraintError("Test error")
        assert error._code == "QK_ERR_SQL_012"

    def test_transaction_error_has_code(self):
        error = exc.TransactionError("Test error")
        assert error._code == "QK_ERR_SQL_013"

    def test_serialization_error_has_code(self):
        error = exc.SerializationError("Test error")
        assert error._code == "QK_ERR_SQL_014"

    def test_optimistic_lock_error_has_code(self):
        error = exc.OptimisticLockError("User", 1, 1)
        assert error._code == "QK_ERR_SQL_015"

    def test_transaction_rollback_error_has_code(self):
        error = exc.TransactionRollbackError("Test error")
        assert error._code == "QK_ERR_SQL_016"

    def test_lock_error_has_code(self):
        error = exc.LockError("Test error")
        assert error._code == "QK_ERR_SQL_017"

    def test_deadlock_error_has_code(self):
        error = exc.DeadlockError("Test error")
        assert error._code == "QK_ERR_SQL_018"

    def test_schema_error_has_code(self):
        error = exc.SchemaError("Test error")
        assert error._code == "QK_ERR_SQL_019"

    def test_table_not_found_error_has_code(self):
        error = exc.TableNotFoundError("Test error")
        assert error._code == "QK_ERR_SQL_020"

    def test_column_not_found_error_has_code(self):
        error = exc.ColumnNotFoundError("Test error")
        assert error._code == "QK_ERR_SQL_021"

    def test_database_timeout_error_has_code(self):
        error = exc.DatabaseTimeoutError("Test error")
        assert error._code == "QK_ERR_SQL_022"

    def test_repository_error_has_code(self):
        error = exc.RepositoryError("Test error")
        assert error._code == "QK_ERR_SQL_023"

    def test_unit_of_work_error_has_code(self):
        error = exc.UnitOfWorkError("Test error")
        assert error._code == "QK_ERR_SQL_024"

    def test_driver_error_has_code(self):
        error = exc.DriverError("Test error")
        assert error._code == "QK_ERR_SQL_025"

    def test_data_error_has_code(self):
        error = exc.DataError("Test error")
        assert error._code == "QK_ERR_SQL_026"

    def test_data_query_error_has_code(self):
        error = exc.DataQueryError("Test error")
        assert error._code == "QK_ERR_SQL_027"

    def test_pagination_error_has_code(self):
        error = exc.PaginationError("Test error")
        assert error._code == "QK_ERR_SQL_028"

    def test_entity_not_found_error_has_code(self):
        error = exc.EntityNotFoundError("User", 1)
        assert error._code == "QK_ERR_SQL_029"

    def test_data_repository_error_has_code(self):
        error = exc.DataRepositoryError("Test error")
        assert error._code == "QK_ERR_SQL_030"

    def test_cursor_error_has_code(self):
        error = exc.CursorError("Test error")
        assert error._code == "QK_ERR_SQL_031"


class TestExceptionAllExports:
    """Tests for __all__ exports."""

    def test_all_contains_all_exceptions(self):
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
            "OptimisticLockError",
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
            assert item in exc.__all__