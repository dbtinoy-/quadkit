"""Tests for contracts/exceptions/infra.py — infrastructure exceptions."""

from __future__ import annotations

from quadkit.contracts.exceptions.infra import (
    DatabaseError,
    InfrastructureError,
    LockConflictError,
    LockError,
    MigrationError,
    RegistryError,
)


class TestInfrastructureError:
    """Tests for InfrastructureError base class."""

    def test_infrastructure_error_creation(self) -> None:
        """InfrastructureError creates correctly."""
        error = InfrastructureError("DB down")
        assert error.message == "DB down"
        assert error.code == "QK_ERR_INFRA_001"

    def test_infrastructure_error_default_message(self) -> None:
        """InfrastructureError has default message."""
        error = InfrastructureError()
        assert error.message == "Infrastructure error"

    def test_infrastructure_error_with_details(self) -> None:
        """InfrastructureError accepts details."""
        error = InfrastructureError("Connection failed", details={"host": "localhost"})
        assert error.details["host"] == "localhost"


class TestDatabaseError:
    """Tests for DatabaseError."""

    def test_database_error_creation(self) -> None:
        """DatabaseError creates correctly."""
        error = DatabaseError("Query failed")
        assert error.message == "Query failed"
        assert error.code == "QK_ERR_DB_001"

    def test_database_error_inherits_from_infrastructure(self) -> None:
        """DatabaseError inherits from InfrastructureError."""
        error = DatabaseError("test")
        assert isinstance(error, InfrastructureError)


class TestMigrationError:
    """Tests for MigrationError."""

    def test_migration_error_creation(self) -> None:
        """MigrationError creates correctly."""
        error = MigrationError("Schema mismatch")
        assert error.message == "Schema mismatch"
        assert error.code == "QK_ERR_DB_002"


class TestLockError:
    """Tests for LockError."""

    def test_lock_error_creation(self) -> None:
        """LockError creates correctly."""
        error = LockError("Could not acquire lock")
        assert error.message == "Could not acquire lock"
        assert error.code == "QK_ERR_INFRA_002"


class TestLockConflictError:
    """Tests for LockConflictError."""

    def test_lock_conflict_basic(self) -> None:
        """LockConflictError creates with resource."""
        error = LockConflictError(resource="user:123")
        assert error.resource == "user:123"
        assert error.owner is None
        assert error.code == "QK_ERR_INFRA_003"

    def test_lock_conflict_with_owner(self) -> None:
        """LockConflictError includes owner info."""
        error = LockConflictError(resource="order:456", owner="process-1")
        assert error.resource == "order:456"
        assert error.owner == "process-1"

    def test_lock_conflict_message_contains_resource(self) -> None:
        """LockConflictError message includes resource."""
        error = LockConflictError(resource="payment:789")
        assert "payment:789" in error.message

    def test_lock_conflict_message_contains_owner(self) -> None:
        """LockConflictError message includes owner when present."""
        error = LockConflictError(resource="order:1", owner="worker-2")
        assert "worker-2" in error.message

    def test_lock_conflict_details_include_info(self) -> None:
        """LockConflictError stores resource and owner in details."""
        error = LockConflictError(resource="item:100", owner="task-5")
        assert error.details["resource"] == "item:100"
        assert error.details["owner"] == "task-5"

    def test_lock_conflict_inherits_from_lock_error(self) -> None:
        """LockConflictError inherits from LockError."""
        error = LockConflictError(resource="test")
        assert isinstance(error, LockError)


class TestRegistryError:
    """Tests for RegistryError."""

    def test_registry_error_creation(self) -> None:
        """RegistryError creates correctly."""
        error = RegistryError("Service not found")
        assert error.message == "Service not found"
        assert error.code == "QK_ERR_REG_001"

    def test_registry_error_inherits_from_quadkit_error(self) -> None:
        """RegistryError inherits from QuadkitError."""
        error = RegistryError("test")
        from quadkit.contracts.exceptions.base import QuadkitError

        assert isinstance(error, QuadkitError)
