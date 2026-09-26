"""MongoDB user store plus SQLAlchemy OAuth identity store tests."""

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




class TestMongoDBUserStore:
    """TestMongoDBUserStore - test CRUD operations."""

    @pytest.fixture
    def mock_collection(self) -> MagicMock:
        """Create a mock MongoDB collection."""
        collection = MagicMock()
        collection.insert_one = AsyncMock()
        collection.find_one = AsyncMock()
        collection.replace_one = AsyncMock()
        collection.delete_one = AsyncMock()
        collection.count_documents = AsyncMock(return_value=0)

        async def mock_find(query, skip=0, limit=100):
            return MagicMock(
                __aiter__=lambda _: iter([]),
                skip=lambda _x: _,
                limit=lambda _x: _,
            )

        collection.find = MagicMock(side_effect=mock_find)
        return collection

    @pytest.fixture
    def mock_document_store(self, mock_collection: MagicMock) -> MagicMock:
        """Create a mock document store."""
        store = MagicMock()
        store.collection = MagicMock(return_value=mock_collection)
        return store

    @pytest.fixture
    def store(self, mock_document_store: MagicMock) -> MongoDBUserStore:
        """Create a MongoDB user store with mock document store."""
        return MongoDBUserStore(document_store=mock_document_store, collection_name="users")

    @pytest.mark.asyncio
    async def test_create_user(self, store: MongoDBUserStore, mock_collection: MagicMock) -> None:
        """Test creating a new user."""
        mock_collection.insert_one = AsyncMock()

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
        mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id(
        self, store: MongoDBUserStore, mock_collection: MagicMock
    ) -> None:
        """Test getting a user by ID."""
        mock_doc = {
            "_id": "user_123",
            "name": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "is_verified": True,
            "roles": ["user"],
            "permissions": ["read"],
            "profile": {},
            "created_at": None,
            "updated_at": None,
            "last_login_at": None,
            "login_count": 0,
        }
        mock_collection.find_one = AsyncMock(return_value=mock_doc)

        user = await store.get_user_by_id("user_123")

        assert user is not None
        assert user.user_id == "user_123"
        assert user.name == "testuser"
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(
        self, store: MongoDBUserStore, mock_collection: MagicMock
    ) -> None:
        """Test getting a non-existent user by ID."""
        mock_collection.find_one = AsyncMock(return_value=None)

        user = await store.get_user_by_id("nonexistent")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_email(
        self, store: MongoDBUserStore, mock_collection: MagicMock
    ) -> None:
        """Test getting a user by email."""
        mock_doc = {
            "_id": "user_123",
            "name": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "is_verified": True,
            "roles": ["user"],
            "permissions": ["read"],
            "profile": {},
            "created_at": None,
            "updated_at": None,
            "last_login_at": None,
            "login_count": 0,
        }
        mock_collection.find_one = AsyncMock(return_value=mock_doc)

        user = await store.get_user_by_email("test@example.com")

        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_update_user(
        self, store: MongoDBUserStore, mock_collection: MagicMock
    ) -> None:
        """Test updating user information."""
        mock_collection.replace_one = AsyncMock()

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

        mock_collection.replace_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user(
        self, store: MongoDBUserStore, mock_collection: MagicMock
    ) -> None:
        """Test deleting a user."""
        mock_collection.delete_one = AsyncMock()

        await store.delete_user("user_123")

        mock_collection.delete_one.assert_called_once_with({"_id": "user_123"})

    @pytest.mark.asyncio
    async def test_list_users(
        self, store: MongoDBUserStore, mock_collection: MagicMock
    ) -> None:
        """Test listing users with pagination."""
        mock_docs = [
            {
                "_id": "user_1",
                "name": "user1",
                "email": "user1@example.com",
                "is_active": True,
                "is_verified": True,
                "roles": ["user"],
                "permissions": ["read"],
                "profile": {},
                "created_at": None,
                "updated_at": None,
                "last_login_at": None,
                "login_count": 0,
            },
            {
                "_id": "user_2",
                "name": "user2",
                "email": "user2@example.com",
                "is_active": True,
                "is_verified": True,
                "roles": ["user"],
                "permissions": ["read"],
                "profile": {},
                "created_at": None,
                "updated_at": None,
                "last_login_at": None,
                "login_count": 0,
            },
        ]

        class MockCursor:
            def __init__(self, docs):
                self.docs = docs

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.docs:
                    return self.docs.pop(0)
                raise StopAsyncIteration

            def skip(self, n):
                return self

            def limit(self, n):
                return self

        mock_collection.find = MagicMock(return_value=MockCursor(mock_docs))

        users = await store.list_users(skip=0, limit=10)

        assert len(users) == 2
        assert users[0].user_id == "user_1"
        assert users[1].user_id == "user_2"

    @pytest.mark.asyncio
    async def test_count_users(
        self, store: MongoDBUserStore, mock_collection: MagicMock
    ) -> None:
        """Test counting total users."""
        mock_collection.count_documents = AsyncMock(return_value=42)

        count = await store.count_users()

        assert count == 42




class TestSQLAlchemyOAuthIdentityStore:
    """Tests for SQLAlchemyOAuthIdentityStore schema bootstrap."""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """Build a db provider mock with a scoped async connection."""
        conn = AsyncMock()
        db = MagicMock()
        db.get_scoped_connection = AsyncMock(return_value=conn)
        db.scoped_context = MagicMock(return_value=_AsyncCtxManager())
        return db

    @pytest.mark.asyncio
    async def test_ensure_tables_splits_ddl_into_single_statements(
        self, mock_db: MagicMock
    ) -> None:
        """Each DDL statement is executed separately (multi-statement executes fail)."""
        from quadkit.auth.storage.oauth_identity_store import (
            SQLAlchemyOAuthIdentityStore,
        )

        store = SQLAlchemyOAuthIdentityStore(mock_db)

        await store._ensure_tables()

        conn = mock_db.get_scoped_connection.return_value
        assert conn.execute.call_count == 2
        assert all(
            ";" not in call[0][0].rstrip(";") for call in conn.execute.call_args_list
        )

    @pytest.mark.asyncio
    async def test_ensure_tables_is_idempotent(self, mock_db: MagicMock) -> None:
        """A second call skips re-executing the DDL."""
        from quadkit.auth.storage.oauth_identity_store import (
            SQLAlchemyOAuthIdentityStore,
        )

        store = SQLAlchemyOAuthIdentityStore(mock_db)

        await store._ensure_tables()
        await store._ensure_tables()

        conn = mock_db.get_scoped_connection.return_value
        assert conn.execute.call_count == 2


class _AsyncCtxManager:
    """Async context manager double for scoped_context()."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


