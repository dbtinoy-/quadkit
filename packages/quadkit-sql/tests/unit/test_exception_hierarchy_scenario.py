"""Scenario coverage for the SQL exception hierarchy.

Full matrix of the ``quadkit.sql.exceptions`` taxonomy: error codes,
inheritance edges, constructor attributes, message formatting, and the
QuadkitError base API (``to_dict`` / ``with_details`` / ``with_hint`` /
``docs_url``).
"""

from __future__ import annotations

import pytest

from quadkit.contracts.exceptions import DatabaseError, NotFoundError
from quadkit.sql import exceptions as exc

# ── code matrix ─────────────────────────────────────────────────────


def test_error_code_matrix() -> None:
    expected = {
        exc.DatabaseConnectionError: "QK_ERR_SQL_001",
        exc.ConnectionRefusedError: "QK_ERR_SQL_002",
        exc.ConnectionTimeoutError: "QK_ERR_SQL_003",
        exc.ConnectionPoolError: "QK_ERR_SQL_004",
        exc.QueryError: "QK_ERR_SQL_005",
        exc.QuerySyntaxError: "QK_ERR_SQL_006",
        exc.ParameterBindingError: "QK_ERR_SQL_007",
        exc.IntegrityError: "QK_ERR_SQL_008",
        exc.DuplicateKeyError: "QK_ERR_SQL_009",
        exc.ForeignKeyError: "QK_ERR_SQL_010",
        exc.NotNullViolationError: "QK_ERR_SQL_011",
        exc.CheckConstraintError: "QK_ERR_SQL_012",
        exc.TransactionError: "QK_ERR_SQL_013",
        exc.SerializationError: "QK_ERR_SQL_014",
        exc.OptimisticLockError: "QK_ERR_SQL_015",
        exc.TransactionRollbackError: "QK_ERR_SQL_016",
        exc.LockError: "QK_ERR_SQL_017",
        exc.DeadlockError: "QK_ERR_SQL_018",
        exc.SchemaError: "QK_ERR_SQL_019",
        exc.TableNotFoundError: "QK_ERR_SQL_020",
        exc.ColumnNotFoundError: "QK_ERR_SQL_021",
        exc.DatabaseTimeoutError: "QK_ERR_SQL_022",
        exc.RepositoryError: "QK_ERR_SQL_023",
        exc.UnitOfWorkError: "QK_ERR_SQL_024",
        exc.DriverError: "QK_ERR_SQL_025",
        exc.DataError: "QK_ERR_SQL_026",
        exc.DataQueryError: "QK_ERR_SQL_027",
        exc.PaginationError: "QK_ERR_SQL_028",
        exc.EntityNotFoundError: "QK_ERR_SQL_029",
        exc.DataRepositoryError: "QK_ERR_SQL_030",
        exc.CursorError: "QK_ERR_SQL_031",
        exc.TenantScopingError: "QK_ERR_SQL_038",
    }
    for cls, code in expected.items():
        assert cls._code == code


# ── inheritance matrix ──────────────────────────────────────────────


def test_inheritance_edges() -> None:
    # every SQL database error is a contracts DatabaseError
    for cls in (
        exc.DatabaseConnectionError,
        exc.ConnectionRefusedError,
        exc.ConnectionTimeoutError,
        exc.ConnectionPoolError,
        exc.QueryError,
        exc.QuerySyntaxError,
        exc.ParameterBindingError,
        exc.IntegrityError,
        exc.DuplicateKeyError,
        exc.ForeignKeyError,
        exc.NotNullViolationError,
        exc.CheckConstraintError,
        exc.TransactionError,
        exc.SerializationError,
        exc.OptimisticLockError,
        exc.TransactionRollbackError,
        exc.LockError,
        exc.DeadlockError,
        exc.SchemaError,
        exc.TableNotFoundError,
        exc.ColumnNotFoundError,
        exc.DatabaseTimeoutError,
        exc.RepositoryError,
        exc.UnitOfWorkError,
        exc.DriverError,
        exc.TenantScopingError,
    ):
        assert issubclass(cls, DatabaseError)

    # data-layer errors are NOT DatabaseError
    for cls in (
        exc.DataError,
        exc.DataQueryError,
        exc.PaginationError,
        exc.EntityNotFoundError,
        exc.DataRepositoryError,
        exc.CursorError,
    ):
        assert not issubclass(cls, DatabaseError)

    # subtle edges that are easy to get wrong
    assert issubclass(exc.DeadlockError, exc.TransactionError)
    assert not issubclass(exc.DeadlockError, exc.LockError)
    assert issubclass(exc.OptimisticLockError, DatabaseError)
    assert not issubclass(exc.OptimisticLockError, exc.TransactionError)
    assert issubclass(exc.DuplicateKeyError, exc.IntegrityError)
    assert issubclass(exc.TableNotFoundError, exc.SchemaError)
    assert issubclass(exc.ConnectionRefusedError, exc.DatabaseConnectionError)
    assert issubclass(exc.QuerySyntaxError, exc.QueryError)


def test_reexported_contract_exceptions() -> None:
    # re-exports keep the public surface stable
    assert exc.DatabaseError is DatabaseError
    assert exc.NotFoundError is NotFoundError
    assert exc.MigrationError.__name__ == "MigrationError"


# ── constructor attributes ──────────────────────────────────────────


def test_connection_error_attributes() -> None:
    err = exc.DatabaseConnectionError("down", host="db1", port=3306, details={"x": 1})
    assert err.host == "db1"
    assert err.port == 3306
    assert err.details["x"] == 1
    assert exc.ConnectionRefusedError("r").host is None


def test_query_error_attributes() -> None:
    err = exc.QueryError("bad", sql="SELECT 1", params=(1,))
    assert err.sql == "SELECT 1"
    assert err.params == (1,)
    assert exc.QuerySyntaxError("bad").sql is None


def test_integrity_error_attributes() -> None:
    err = exc.IntegrityError("v", constraint="uq_email", table="users")
    assert err.constraint == "uq_email"
    assert err.table == "users"

    nn = exc.NotNullViolationError("v", column="email")
    assert nn.column == "email"
    assert nn.constraint is None


def test_driver_error_attributes() -> None:
    err = exc.DriverError("wrapped", driver="asyncpg", operation="query")
    assert err.driver == "asyncpg"
    assert err.operation == "query"


def test_optimistic_lock_error_message() -> None:
    err = exc.OptimisticLockError("Order", 42, expected_version=3)
    assert err.entity_type == "Order"
    assert err.entity_id == 42
    assert err.expected_version == 3
    assert "Order(id=42)" in str(err)
    assert "expected version 3" in str(err)


def test_entity_not_found_error_message() -> None:
    err = exc.EntityNotFoundError("User", 7)
    assert err.entity_type == "User"
    assert err.entity_id == 7
    assert err.message == "User with id=7 not found"
    assert "User with id=7 not found" in str(err)


def test_tenant_scoping_error_message() -> None:
    err = exc.TenantScopingError("orders", "INSERT")
    assert err.table == "orders"
    assert err.operation == "INSERT"
    assert "INSERT on table 'orders'" in str(err)
    assert exc.TenantScopingError("orders").operation == "SELECT"


# ── QuadkitError base API through SQL subclasses ───────────────────


def test_error_serialization_and_built() -> None:
    err = exc.TableNotFoundError("missing", details={"table": "t"}, hint="create it")
    assert err.code == "QK_ERR_SQL_020"
    assert err.message == "missing"
    assert err.hint == "create it"
    assert err.docs_url.endswith("QK_ERR_SQL_020")

    payload = err.to_dict()
    assert payload["code"] == "QK_ERR_SQL_020"
    assert payload["message"] == "missing"
    assert payload["details"] == {"table": "t"}
    assert payload["hint"] == "create it"

    enriched = err.with_details(retried=True)
    # documented contract: with_details mutates and returns self
    assert enriched is err
    assert enriched.details == {"table": "t", "retried": True}

    hinted = err.with_hint("new hint")
    assert hinted is err
    assert hinted.hint == "new hint"

    # catchability through the hierarchy
    with pytest.raises(exc.SchemaError):
        raise err
    with pytest.raises(DatabaseError):
        raise err
