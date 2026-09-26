"""SQLUserStore CRUD and mapping tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.auth.models.user import User
from quadkit.auth.storage._mongo_store import MongoDBUserStore
from quadkit.auth.storage._sql_store import SQLUserStore



class MockQueryResult:
    """Mock query result for database provider."""

    def __init__(self, rows: list[dict] | dict | None = None):
        self._rows = rows

    @property
    def rows(self):
        return self._rows


class MockDatabaseProvider:
    """Mock database provider for testing."""

    def __init__(self):
        self._executed_queries = []

    async def execute_query(self, query: str, params: list | None = None):
        self._executed_queries.append((query, params))
        return MockQueryResult()

    async def execute_insert(self, table: str, payload: dict):
        self._executed_queries.append(("INSERT", table, payload))
        return "test_user_id"

    async def execute_update(self, table: str, payload: dict, where: str, params: list):
        self._executed_queries.append(("UPDATE", table, payload, where, params))
        return 1

    async def execute_delete(self, table: str, where: str, params: list):
        self._executed_queries.append(("DELETE", table, where, params))
        return 1




class TestSQLUserStore:
    """TestSQLUserStore - test create_user, get_user, update_user."""

    @pytest.fixture
    def mock_db(self) -> MockDatabaseProvider:
        """Create a mock database provider."""
        return MockDatabaseProvider()

    @pytest.fixture
    def store(self, mock_db: MockDatabaseProvider) -> SQLUserStore:
        """Create a SQL user store with mock database."""
        store = SQLUserStore(mock_db)
        store._ensure_tables = AsyncMock()
        return store

    @pytest.mark.asyncio
    async def test_create_user(self, store: SQLUserStore, mock_db: MockDatabaseProvider) -> None:
        """Test creating a new user."""
        mock_db.execute_insert = AsyncMock(return_value="new_user_id")

        user = await store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed_password",
            roles=["user"],
            permissions=["read"],
            profile={"bio": "test bio"},
        )

        assert user is not None
        assert user.name == "testuser"
        assert user.email == "test@example.com"
        assert user.roles == ["user"]
        assert user.permissions == ["read"]
        assert user.profile == {"bio": "test bio"}

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, store: SQLUserStore, mock_db: MockDatabaseProvider) -> None:
        """Test getting a user by ID."""
        mock_row = {
            "user_id": "user_123",
            "name": "testuser",
            "email": "test@example.com",
            "hashed_password": "hashed_password",
            "is_active": True,
            "is_verified": True,
            "roles": '["user"]',
            "permissions": '["read"]',
            "profile": "{}",
            "created_at": None,
            "updated_at": None,
            "last_login_at": None,
            "login_count": 0,
        }
        mock_db.execute_query = AsyncMock(return_value=MockQueryResult([mock_row]))

        user = await store.get_user_by_id("user_123")

        assert user is not None
        assert user.user_id == "user_123"
        assert user.name == "testuser"
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(
        self, store: SQLUserStore, mock_db: MockDatabaseProvider
    ) -> None:
        """Test getting a non-existent user by ID."""
        mock_db.execute_query = AsyncMock(return_value=MockQueryResult([]))

        user = await store.get_user_by_id("nonexistent")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, store: SQLUserStore, mock_db: MockDatabaseProvider) -> None:
        """Test getting a user by email."""
        mock_row = {
            "user_id": "user_123",
            "name": "testuser",
            "email": "test@example.com",
            "hashed_password": "hashed_password",
            "is_active": True,
            "is_verified": True,
            "roles": '["user"]',
            "permissions": '["read"]',
            "profile": "{}",
            "created_at": None,
            "updated_at": None,
            "last_login_at": None,
            "login_count": 0,
        }
        mock_db.execute_query = AsyncMock(return_value=MockQueryResult([mock_row]))

        user = await store.get_user_by_email("test@example.com")

        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_update_user(self, store: SQLUserStore, mock_db: MockDatabaseProvider) -> None:
        """Test updating user information."""
        mock_db.execute_update = AsyncMock(return_value=1)

        user = User(
            user_id="user_123",
            name="updateduser",
            email="updated@example.com",
            is_active=True,
            is_verified=True,
            roles=["user", "admin"],
            permissions=["read", "write"],
            profile={"bio": "updated bio"},
            login_count=5,
        )

        await store.update_user(user)

        mock_db.execute_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user(self, store: SQLUserStore, mock_db: MockDatabaseProvider) -> None:
        """Test deleting a user."""
        mock_db.execute_delete = AsyncMock(return_value=1)

        await store.delete_user("user_123")

        mock_db.execute_delete.assert_called_once_with(
            "users", "user_id = ?", ["user_123"]
        )

    @pytest.mark.asyncio
    async def test_list_users(self, store: SQLUserStore, mock_db: MockDatabaseProvider) -> None:
        """Test listing users with pagination."""
        mock_rows = [
            {
                "user_id": "user_1",
                "name": "user1",
                "email": "user1@example.com",
                "is_active": True,
                "is_verified": True,
                "roles": '["user"]',
                "permissions": '["read"]',
                "profile": "{}",
                "created_at": None,
                "updated_at": None,
                "last_login_at": None,
                "login_count": 0,
            },
            {
                "user_id": "user_2",
                "name": "user2",
                "email": "user2@example.com",
                "is_active": True,
                "is_verified": True,
                "roles": '["user"]',
                "permissions": '["read"]',
                "profile": "{}",
                "created_at": None,
                "updated_at": None,
                "last_login_at": None,
                "login_count": 0,
            },
        ]
        mock_db.execute_query = AsyncMock(return_value=MockQueryResult(mock_rows))

        users = await store.list_users(skip=0, limit=10)

        assert len(users) == 2
        assert users[0].user_id == "user_1"
        assert users[1].user_id == "user_2"

    @pytest.mark.asyncio
    async def test_count_users(self, store: SQLUserStore, mock_db: MockDatabaseProvider) -> None:
        """Test counting total users."""
        mock_db.execute_query = AsyncMock(return_value=MockQueryResult([{"count": 42}]))

        count = await store.count_users()

        assert count == 42




class _AsyncCtxManager:
    """Async context manager double for scoped_context()."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


