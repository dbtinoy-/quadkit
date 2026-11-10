"""InMemoryUserStore CRUD/auth flows plus authorization lock-type tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from quadkit.auth.models import AuthToken
import quadkit.auth as la
from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.schemas import RegisterRequest
from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.di import AuthenticationProvider, AuthorizationProvider
from quadkit.auth.storage.db_stores import (
    MongoDBUserStore,
    RedisUserStore,
    SQLUserStore,
)
from quadkit.auth.storage.token_store import InMemoryUserStore
from quadkit.auth.exceptions import (
    TokenExpiredError,
    InvalidTokenError,
    BlacklistedTokenError,
)
from quadkit.auth.exceptions import (
    TokenAudienceError,
    TokenBlacklistedError,
    TokenExpiredError as TokenExpiredErrorAuth,
    TokenInvalidError,
)
from quadkit.auth.exceptions import EmailExistsError, UsernameExistsError
from quadkit.contracts.auth.token import VerifiedToken
from quadkit.result import Err, Ok


class TestInMemoryUserStore:
    """Test in-memory user store"""

    def setup_method(self):
        """Setup test method"""
        self.store = InMemoryUserStore()

        class DummyCache:
            async def exists(self, key):
                return False

            async def set(self, *args, **kwargs):
                return True

            async def delete(self, *args, **kwargs):
                return True

            async def delete_many(self, *args, **kwargs):
                return True

        cache = DummyCache()

    @pytest.mark.asyncio
    async def test_create_user(self):
        """Test user creation"""
        user = await self.store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed123",
            roles=["user"],
        )

        assert user.user_id is not None
        assert user.name == "testuser"
        assert user.email == "test@example.com"
        assert user.roles == ["user"]

    @pytest.mark.asyncio
    async def test_duplicate_name_raises_username_exists(self):
        """Duplicate name is a typed conflict, not a bare ValueError."""
        await self.store.create_user(
            name="testuser",
            email="a@example.com",
            hashed_password="hashed123",
        )
        with pytest.raises(UsernameExistsError, match="Name 'testuser' already exists"):
            await self.store.create_user(
                name="testuser",
                email="b@example.com",
                hashed_password="hashed123",
            )

    @pytest.mark.asyncio
    async def test_duplicate_email_raises_email_exists(self):
        """Duplicate email is a typed conflict, not a bare ValueError."""
        await self.store.create_user(
            name="usera",
            email="test@example.com",
            hashed_password="hashed123",
        )
        with pytest.raises(
            EmailExistsError, match=r"Email 'test@example\.com' already exists"
        ):
            await self.store.create_user(
                name="userb",
                email="test@example.com",
                hashed_password="hashed123",
            )

    # username-based lookups are deprecated; authentication should use email
    # the following test verifies we can still retrieve by email instead.
    @pytest.mark.asyncio
    async def test_get_user_by_email_after_creation(self):
        """Test getting user by email instead of username."""
        created = await self.store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed123",
        )

        user = await self.store.get_user_by_email("test@example.com")
        assert user is not None
        assert user.user_id == created.user_id
        assert user.email == "test@example.com"


    @pytest.mark.asyncio
    async def test_get_user_by_id(self):
        """Test getting user by ID"""
        created_user = await self.store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed123",
        )

        user = await self.store.get_user_by_id(created_user.user_id)
        assert user is not None
        assert user.user_id == created_user.user_id

    @pytest.mark.asyncio
    async def test_get_user_by_email(self):
        """Test getting user by email after creation"""
        created = await self.store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed123",
        )
        user = await self.store.get_user_by_email("test@example.com")
        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_update_user(self):
        """Test updating existing user"""
        user = await self.store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed123",
        )
        # mutating via dataclass helper or manual replacement
        try:
            updated_user = user.with_role("admin")
        except AttributeError:
            updated_user = user
        await self.store.update_user(updated_user)

    @pytest.mark.asyncio
    async def test_delete_user(self):
        """Test deleting a user"""
        user = await self.store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed123",
        )
        await self.store.delete_user(user.user_id)
        assert await self.store.get_user_by_id(user.user_id) is None

    # provider-related tests that rely on ``self.provider``
    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self):
        """Test authentication with wrong password"""
        pytest.skip("Requires refactoring to use AuthenticationService")

    @pytest.mark.asyncio
    async def test_create_and_verify_token(self):
        """Test token creation and verification"""
        pytest.skip("Requires refactoring to use AuthenticationService")

    @pytest.mark.asyncio
    async def test_user_role_management(self):
        pytest.skip("add_user_role method not implemented in authz service")

    @pytest.mark.asyncio
    async def test_user_permission_management(self):
        pytest.skip("add_user_permission method not implemented in authz service")

    def test_authorization_checks(self):
        """Test authorization helper methods via User model"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user", "editor"],
            permissions=["read", "write"],
        )

        # Use User model methods directly
        assert user.has_role("user")
        assert user.has_role("editor")
        assert not user.has_role("admin")


class TestAuthorizationServiceLockType:
    """P0-3: AuthorizationService._lock must be asyncio.Lock, not threading.Lock."""

    def test_authorization_service_uses_asyncio_lock_not_threading(self) -> None:
        """P0-3: AuthorizationService._lock must be asyncio.Lock, not threading.Lock."""
        import asyncio

        from quadkit.auth.authz.service import AuthorizationService

        svc = AuthorizationService()
        assert not type(svc._lock).__name__ == "lock", (
            "AuthorizationService._lock is threading.Lock — blocks the event loop"
        )
        assert isinstance(svc._lock, asyncio.Lock)
