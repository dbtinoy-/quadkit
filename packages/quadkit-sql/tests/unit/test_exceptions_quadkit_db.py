"""Tests for database exceptions"""

from quadkit.sql.exceptions import (
    CheckConstraintError,
    ConnectionPoolError,
    DatabaseError,
    DatabaseConnectionError,
    DeadlockError,
    DuplicateKeyError,
    ForeignKeyError,
    IntegrityError,
    LockError,
    MigrationError,
    NotFoundError,
    QueryError,
    RepositoryError,
    SchemaError,
    DatabaseTimeoutError,
    TransactionError,
    UnitOfWorkError,
)
from quadkit.contracts.exceptions import QuadkitError


class TestDatabaseExceptions:
    """Test database exception classes"""

    def test_database_error_inheritance(self):
        """Test DatabaseError inherits from QuadkitError"""
        error = DatabaseError("Test error")
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_DB_001] Test error")

    def test_connection_error_inheritance(self):
        """Test DatabaseConnectionError inherits from DatabaseError"""
        error = DatabaseConnectionError("Connection failed")
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_001] Connection failed")

    def test_connection_pool_error_inheritance(self):
        """Test ConnectionPoolError inherits from DatabaseError"""
        error = ConnectionPoolError("Pool exhausted")
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_004] Pool exhausted")

    def test_transaction_error_inheritance(self):
        """Test TransactionError inherits from DatabaseError"""
        error = TransactionError("Transaction failed")
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_013] Transaction failed")

    def test_query_error_inheritance(self):
        """Test QueryError inherits from DatabaseError"""
        error = QueryError("Query failed")
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_005] Query failed")

    def test_query_error_with_sql_and_params(self):
        """Test QueryError stores SQL and parameters"""
        sql = "SELECT * FROM users WHERE id = ?"
        params = [1]
        error = QueryError("Query failed", sql=sql, params=params)

        assert error.sql == sql
        assert error.params == params
        assert str(error).startswith("[QK_ERR_SQL_005] Query failed")

    def test_query_error_with_details(self):
        """Test QueryError with additional details"""
        details = {"table": "users", "operation": "select"}
        error = QueryError("Query failed", details=details)

        assert error.details == details
        assert str(error).startswith("[QK_ERR_SQL_005] Query failed")

    def test_migration_error_inheritance(self):
        """Test MigrationError inherits from InfrastructureError"""
        error = MigrationError("Migration failed")
        from quadkit.contracts.exceptions import InfrastructureError
        assert isinstance(error, InfrastructureError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_DB_002] Migration failed")

    def test_schema_error_inheritance(self):
        """Test SchemaError inherits from DatabaseError"""
        error = SchemaError("Schema error")
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_019] Schema error")

    def test_integrity_error_inheritance(self):
        """Test IntegrityError inherits from DatabaseError"""
        error = IntegrityError("Integrity violation")
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_008] Integrity violation")

    def test_timeout_error_inheritance(self):
        """Test TimeoutError inherits from DatabaseError"""
        error = DatabaseTimeoutError("Operation timed out", timeout=0.5)
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)

    def test_lock_error_inheritance(self):
        """Test LockError inherits from DatabaseError"""
        error = LockError("Lock error")
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_017] Lock error")

    def test_unit_of_work_error_inheritance(self):
        """Test UnitOfWorkError inherits from DatabaseError"""
        error = UnitOfWorkError("Unit of work error")
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_024] Unit of work error")

    def test_repository_error_inheritance(self):
        """Test RepositoryError inherits from DatabaseError"""
        error = RepositoryError("RepositoryProtocol error")
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_023] RepositoryProtocol error")

    def test_not_found_error_inheritance(self):
        """Test NotFoundError inherits from DomainError"""
        error = NotFoundError("Entity not found")
        from quadkit.contracts.exceptions import DomainError
        assert isinstance(error, DomainError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_DOM_002] Entity not found")

    def test_duplicate_key_error_inheritance(self):
        """Test DuplicateKeyError inherits from IntegrityError"""
        error = DuplicateKeyError("Duplicate key")
        assert isinstance(error, IntegrityError)
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_009] Duplicate key")

    def test_foreign_key_error_inheritance(self):
        """Test ForeignKeyError inherits from IntegrityError"""
        error = ForeignKeyError("Foreign key violation")
        assert isinstance(error, IntegrityError)
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_010] Foreign key violation")

    def test_check_constraint_error_inheritance(self):
        """Test CheckConstraintError inherits from IntegrityError"""
        error = CheckConstraintError("Check constraint violation")
        assert isinstance(error, IntegrityError)
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_012] Check constraint violation")

    def test_deadlock_error_inheritance(self):
        """Test DeadlockError inherits from TransactionError"""
        error = DeadlockError("Deadlock detected")
        assert isinstance(error, TransactionError)
        assert isinstance(error, DatabaseError)
        assert isinstance(error, QuadkitError)
        assert str(error).startswith("[QK_ERR_SQL_018] Deadlock detected")

    def test_all_exceptions_exported(self):
        """Test that all exception classes are properly exported"""
        import quadkit.sql.exceptions as db_exceptions
        from quadkit.sql.exceptions import __all__ as exported_exceptions

        assert "DatabaseError" in exported_exceptions
        assert "DatabaseConnectionError" in exported_exceptions
        assert "QueryError" in exported_exceptions
        assert "RepositoryError" in exported_exceptions

        # Verify all classes are actually available
        for exception_name in exported_exceptions:
            assert hasattr(db_exceptions, exception_name), f"{exception_name} not found in quadkit.sql.exceptions"
