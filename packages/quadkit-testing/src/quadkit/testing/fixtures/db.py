"""Database-specific test fixtures"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

pytest_asyncio: Any | None = None
try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

from collections.abc import Callable
from typing import Any as _Any

# Explicitly type the chosen fixture decorator so mypy treats decorated functions as typed
fixture_decorator: Callable[..., _Any] = (
    pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
)

try:
    from quadkit.sql.abstractions.connection import (  # type: ignore[attr-defined]
        ConnectionPool,
        DatabaseConnection,
    )
except ImportError:
    # Fallback if quadkit-sql is not available
    ConnectionPool: Any = Any  # type: ignore[no-redef]
    DatabaseConnection: Any = Any  # type: ignore[no-redef]
from quadkit.testing.clients.db import (
    DatabaseTestBed,
    DatabaseTestClient,
)


@fixture_decorator
async def db_test_bed() -> AsyncGenerator[DatabaseTestBed, None]:
    """Fixture for DatabaseTestBed with automatic cleanup"""
    test_bed = DatabaseTestBed()
    async with test_bed as tb:
        yield tb


@fixture_decorator
async def test_database_client() -> AsyncGenerator[DatabaseTestClient, None]:
    """Fixture for DatabaseTestClient"""
    client = DatabaseTestClient()
    async with client as c:
        yield c


@pytest.fixture
def mock_connection() -> DatabaseConnection:
    """Fixture for mock database connection"""
    mock_conn = Mock(spec=DatabaseConnection)

    # Mock async methods
    mock_conn.execute = AsyncMock()
    mock_conn.execute_many = AsyncMock()
    mock_conn.fetch_one = AsyncMock()
    mock_conn.fetch_all = AsyncMock()
    mock_conn.close = AsyncMock()

    # Additional methods expected by tests
    mock_conn.fetchone = AsyncMock()
    mock_conn.fetchall = AsyncMock()

    # Mock transaction context manager
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_transaction.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = Mock(return_value=mock_transaction)

    return mock_conn


@pytest.fixture
def mock_connection_pool() -> ConnectionPool:
    """Fixture for mock connection pool"""
    mock_pool = Mock(spec=ConnectionPool)

    # Mock async methods
    mock_pool.get_connection = AsyncMock()
    mock_pool.close = AsyncMock()
    mock_pool.health_check = Mock(return_value={"status": "healthy"})
    mock_pool.get_stats = Mock(return_value={"connections": 5})

    # Additional methods expected by tests
    mock_pool.acquire = AsyncMock()
    mock_pool.release = AsyncMock()

    return mock_pool


@fixture_decorator
async def seeded_database(
    db_test_bed: DatabaseTestBed,
    sample_user_data: list[dict[str, Any]],
    sample_order_data: list[dict[str, Any]],
    sample_product_data: list[dict[str, Any]],
) -> DatabaseTestBed:
    """Fixture for database with sample data"""
    # Create users table
    await db_test_bed.create_test_table(
        "users",
        "id INTEGER PRIMARY KEY, name TEXT, email TEXT, role TEXT",
    )

    # Create orders table
    await db_test_bed.create_test_table(
        "orders",
        "id INTEGER PRIMARY KEY, user_id INTEGER, total REAL, status TEXT, items TEXT",
    )

    # Create products table
    await db_test_bed.create_test_table(
        "products",
        "id INTEGER PRIMARY KEY, name TEXT, price REAL, category TEXT",
    )

    # Seed sample data
    await db_test_bed.seed_test_data("users", sample_user_data)
    await db_test_bed.seed_test_data("orders", sample_order_data)
    await db_test_bed.seed_test_data("products", sample_product_data)

    return db_test_bed


@fixture_decorator
async def clean_database(db_test_bed: DatabaseTestBed) -> DatabaseTestBed:
    """Fixture for clean database with tables but no data"""
    # Create users table
    await db_test_bed.create_test_table(
        "users",
        "id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT",
    )

    # Create orders table
    await db_test_bed.create_test_table(
        "orders",
        "id INTEGER PRIMARY KEY, user_id INTEGER, total REAL, status TEXT",
    )

    return db_test_bed


@pytest.fixture
def sample_user_data() -> list[dict[str, Any]]:
    """Sample user data for testing"""
    return [
        {
            "id": 1,
            "name": "Alice Johnson",
            "email": "alice@example.com",
            "role": "user",
        },
        {"id": 2, "name": "Bob Smith", "email": "bob@example.com", "role": "admin"},
        {
            "id": 3,
            "name": "Charlie Brown",
            "email": "charlie@example.com",
            "role": "user",
        },
    ]


@pytest.fixture
def sample_order_data() -> list[dict[str, Any]]:
    """Sample order data for testing"""
    return [
        {"id": 1, "user_id": 1, "total": 99.99, "status": "completed", "items": 3},
        {"id": 2, "user_id": 2, "total": 149.50, "status": "pending", "items": 5},
        {"id": 3, "user_id": 1, "total": 75.25, "status": "shipped", "items": 2},
    ]


@pytest.fixture
def sample_product_data() -> list[dict[str, Any]]:
    """Sample product data for testing"""
    return [
        {"id": 1, "name": "Widget A", "price": 29.99, "category": "electronics"},
        {"id": 2, "name": "Widget B", "price": 49.99, "category": "tools"},
        {"id": 3, "name": "Widget C", "price": 19.99, "category": "accessories"},
    ]


@pytest.fixture
def database_provider() -> Any:
    """Placeholder fixture for a real DatabaseProviderProtocol instance.

    Returns ``None`` by default so that ``db_transaction`` skips gracefully
    in test suites that do not configure a live database.

    Override this in your ``conftest.py`` to connect ``db_transaction`` to
    the real database provider resolved from the application container::

        from quadkit.contracts.data import DatabaseProviderProtocol

        @pytest.fixture
        async def database_provider(container: Container):
            return await container.resolve(DatabaseProviderProtocol)

    Where ``container`` is whatever fixture you use to provide the booted DI
    container for your integration tests.
    """
    return None


@fixture_decorator
async def db_transaction(
    database_provider: Any,
) -> AsyncGenerator[Any, None]:
    """Wrap an integration test in a database transaction that always rolls back.

    Opens a scoped database context, begins a transaction, and yields the
    active :class:`~quadkit.contracts.data.ConnectionProtocol` so that the
    test can run queries.  The transaction is *always* rolled back during
    teardown regardless of test outcome, keeping the database state clean and
    making tests fully order-independent.

    Requires the ``database_provider`` fixture to be overridden in the test
    suite's ``conftest.py`` (see :func:`database_provider` for instructions).
    When ``database_provider`` returns ``None`` (the default), the test is
    skipped with an informative message.

    Example::

        # conftest.py
        from quadkit.contracts.data import DatabaseProviderProtocol

        @pytest.fixture
        async def database_provider(container):
            return await container.resolve(DatabaseProviderProtocol)

        # test_users.py
        @pytest.mark.asyncio
        async def test_create_user(db_transaction) -> None:
            await db_transaction.execute(
                "INSERT INTO users(name, email) VALUES($1, $2)",
                "Alice", "alice@example.com",
            )
            row = await db_transaction.fetch_one(
                "SELECT name FROM users WHERE email = $1", "alice@example.com"
            )
            assert row["name"] == "Alice"
            # No teardown needed — the transaction is automatically rolled back.
    """
    if database_provider is None:
        pytest.skip(
            "db_transaction requires a 'database_provider' fixture. "
            "Override it in conftest.py with a real DatabaseProviderProtocol instance."
        )

    async with database_provider.scoped_context():
        conn = await database_provider.get_scoped_connection()
        await conn.execute("BEGIN")
        try:
            yield conn
        finally:
            await conn.execute("ROLLBACK")


__all__ = [
    "clean_database",
    "database_provider",
    "db_test_bed",
    "db_transaction",
    "mock_connection",
    "mock_connection_pool",
    "sample_order_data",
    "sample_product_data",
    "sample_user_data",
    "seeded_database",
    "test_database_client",
]
