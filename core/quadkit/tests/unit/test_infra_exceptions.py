"""Tests for infrastructure exceptions from contracts."""

from quadkit.contracts.exceptions import (
    ConstraintError,
    DatabaseError,
    DuplicateKeyError,
    InfrastructureError,
    IntegrityError,
    QuadkitError,
    LockConflictError,
    LockError,
    MigrationError,
    RegistryAlreadyExistsError,
    RegistryError,
    RegistryKeyError,
)


class TestInfraExceptionHierarchy:
    """Tests for infrastructure exception inheritance."""

    def test_infrastructure_error_inherits_from_quadkit(self) -> None:
        """InfrastructureError inherits from QuadkitError."""
        assert issubclass(InfrastructureError, QuadkitError)

    def test_database_error_inherits_from_infrastructure(self) -> None:
        """DatabaseError inherits from InfrastructureError."""
        assert issubclass(DatabaseError, InfrastructureError)

    def test_lock_error_inherits_from_infrastructure(self) -> None:
        """LockError inherits from InfrastructureError."""
        assert issubclass(LockError, InfrastructureError)

    def test_integrity_error_inherits_from_database(self) -> None:
        """IntegrityError inherits from DatabaseError."""
        assert issubclass(IntegrityError, DatabaseError)

    def test_constraint_error_inherits_from_integrity(self) -> None:
        """ConstraintError inherits from IntegrityError."""
        assert issubclass(ConstraintError, IntegrityError)

    def test_duplicate_key_error_inherits_from_constraint(self) -> None:
        """DuplicateKeyError inherits from ConstraintError."""
        assert issubclass(DuplicateKeyError, ConstraintError)

    def test_lock_conflict_inherits_from_lock(self) -> None:
        """LockConflictError inherits from LockError."""
        assert issubclass(LockConflictError, LockError)


class TestInfraErrorCodes:
    """Tests for infrastructure exception error codes."""

    def test_infrastructure_error_has_code(self) -> None:
        """InfrastructureError has _code attribute."""
        exc = InfrastructureError()
        assert exc._code == "QK_ERR_INFRA_001"

    def test_database_error_has_code(self) -> None:
        """DatabaseError has _code."""
        exc = DatabaseError()
        assert exc._code == "QK_ERR_DB_001"

    def test_migration_error_has_code(self) -> None:
        """MigrationError has _code."""
        exc = MigrationError()
        assert exc._code == "QK_ERR_DB_002"

    def test_lock_error_has_code(self) -> None:
        """LockError has _code."""
        exc = LockError()
        assert exc._code == "QK_ERR_INFRA_002"

    def test_registry_error_has_code(self) -> None:
        """RegistryError has _code."""
        exc = RegistryError()
        assert exc._code == "QK_ERR_REG_001"

    def test_integrity_error_has_code(self) -> None:
        """IntegrityError has _code."""
        exc = IntegrityError()
        assert exc._code == "QK_ERR_DB_003"

    def test_constraint_error_has_code(self) -> None:
        """ConstraintError has _code."""
        exc = ConstraintError()
        assert exc._code == "QK_ERR_DB_004"


class TestLockConflictError:
    """Tests for LockConflictError."""

    def test_requires_resource(self) -> None:
        """LockConflictError requires resource parameter."""
        exc = LockConflictError(resource="user_123")
        assert exc.resource == "user_123"

    def test_can_specify_owner(self) -> None:
        """LockConflictError can specify owner."""
        exc = LockConflictError(resource="user_123", owner="process_456")
        assert exc.resource == "user_123"
        assert exc.owner == "process_456"

    def test_default_message_includes_resource(self) -> None:
        """LockConflictError default message includes resource."""
        exc = LockConflictError(resource="order_789")
        assert "order_789" in str(exc)

    def test_message_includes_owner_when_present(self) -> None:
        """LockConflictError message includes owner."""
        exc = LockConflictError(resource="item", owner="worker1")
        assert "worker1" in str(exc)

    def test_stores_in_details(self) -> None:
        """LockConflictError stores resource and owner in details."""
        exc = LockConflictError(resource="lock1", owner="owner1")
        assert "resource" in exc.details
        assert exc.details["resource"] == "lock1"
        assert exc.details["owner"] == "owner1"


class TestRegistryKeyError:
    """Tests for RegistryKeyError."""

    def test_inherits_from_key_error(self) -> None:
        """RegistryKeyError inherits from KeyError."""
        assert issubclass(RegistryKeyError, KeyError)

    def test_has_code(self) -> None:
        """RegistryKeyError has _code."""
        exc = RegistryKeyError()
        assert exc._code == "QK_ERR_REG_002"


class TestRegistryAlreadyExistsError:
    """Tests for RegistryAlreadyExistsError."""

    def test_has_code(self) -> None:
        """RegistryAlreadyExistsError has _code."""
        exc = RegistryAlreadyExistsError()
        assert exc._code == "QK_ERR_REG_003"


class TestDuplicateKeyError:
    """Tests for DuplicateKeyError."""

    def test_has_code(self) -> None:
        """DuplicateKeyError has _code."""
        exc = DuplicateKeyError()
        assert exc._code == "QK_ERR_DB_005"
