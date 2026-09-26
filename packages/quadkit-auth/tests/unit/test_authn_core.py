"""Unit tests for authentication core services."""

from __future__ import annotations

from unittest.mock import MagicMock

from pydantic import SecretStr
import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.schemas import RegisterRequest
from quadkit.auth.authn.security import PasswordHasher
from quadkit.auth.authn.services import AuthenticationService, LoginAttemptTracker
from quadkit.auth.exceptions import AccountLockedError, InvalidCredentialsError
from quadkit.auth.models import AuthToken, User
from quadkit.auth.storage.token_store import InMemoryUserStore


async def _make_user(store: InMemoryUserStore, name: str, email: str, password: str):
    """Helper: hash password and create user."""
    hashed = await PasswordHasher().hash(password)
    return await store.create_user(name=name, email=email, hashed_password=hashed)


class TestAuthenticationService:
    """TestAuthenticationService - test login, logout, verify methods."""

    @pytest.fixture
    def user_store(self) -> InMemoryUserStore:
        """Create an in-memory user store."""
        return InMemoryUserStore()

    @pytest.fixture
    def token_manager(self) -> JWTTokenManager:
        """Create a JWT token manager."""
        return JWTTokenManager(
            current_key_id="test",
            keys={"test": SecretStr("test_secret_key_12345678901234567890123456789123")},
            access_expiration_hours=1,
            refresh_expiration_days=30,
        )

    @pytest.fixture
    def auth_service(
        self, user_store: InMemoryUserStore, token_manager: JWTTokenManager
    ) -> AuthenticationService:
        """Create an authentication service."""
        return AuthenticationService(
            password_policy=MagicMock(),
            user_store=user_store,
            token_manager=token_manager,
        )

    @pytest.mark.asyncio
    async def test_authenticate_user_success(
        self, auth_service: AuthenticationService, user_store: InMemoryUserStore
    ) -> None:
        """Test successful user authentication."""
        user = await _make_user(user_store, "testuser", "test@example.com", "Password123!")
        result = await auth_service.authenticate_user("test@example.com", "Password123!")

        assert result.is_ok()
        assert result.unwrap().user_id == user.user_id
        assert result.unwrap().email == user.email

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(
        self, auth_service: AuthenticationService, user_store: InMemoryUserStore
    ) -> None:
        """Test authentication with wrong password."""
        await _make_user(user_store, "testuser", "test@example.com", "Password123!")
        result = await auth_service.authenticate_user("test@example.com", "WrongPassword!")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), InvalidCredentialsError)

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(
        self, auth_service: AuthenticationService
    ) -> None:
        """Test authentication with non-existent user."""
        result = await auth_service.authenticate_user("nonexistent@example.com", "Password123!")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), InvalidCredentialsError)

    @pytest.mark.asyncio
    async def test_authenticate_user_locked_out(
        self, user_store: InMemoryUserStore, token_manager: JWTTokenManager
    ) -> None:
        """Test authentication with locked account."""
        tracker = LoginAttemptTracker(max_attempts=3, lockout_duration_seconds=300)
        auth_service = AuthenticationService(
            password_policy=MagicMock(),
            user_store=user_store,
            token_manager=token_manager,
            tracker=tracker,
        )

        await _make_user(user_store, "testuser", "test@example.com", "Password123!")

        for _ in range(3):
            await auth_service.authenticate_user("test@example.com", "WrongPassword!")

        result = await auth_service.authenticate_user("test@example.com", "Password123!")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), AccountLockedError)

    @pytest.mark.asyncio
    async def test_register_user_success(
        self, auth_service: AuthenticationService
    ) -> None:
        """Test successful user registration."""
        request = RegisterRequest(
            name="newuser",
            email="new@example.com",
            password="Password123!",
            confirm_password="Password123!",
        )
        result = await auth_service.register_user(request)

        assert result.is_ok()
        assert result.unwrap().name == "newuser"
        assert result.unwrap().email == "new@example.com"
        assert "user" in result.unwrap().roles

    @pytest.mark.asyncio
    async def test_register_user_password_mismatch(
        self, auth_service: AuthenticationService
    ) -> None:
        """Test registration with password mismatch."""
        request = RegisterRequest(
            name="newuser",
            email="new@example.com",
            password="Password123!",
            confirm_password="DifferentPassword!",
        )
        result = await auth_service.register_user(request)

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(
        self, auth_service: AuthenticationService, user_store: InMemoryUserStore
    ) -> None:
        """Test registration with duplicate email."""
        await _make_user(user_store, "existing", "existing@example.com", "Password123!")

        request = RegisterRequest(
            name="newuser",
            email="existing@example.com",
            password="Password123!",
            confirm_password="Password123!",
        )
        result = await auth_service.register_user(request)

        assert result.is_err()

    def test_create_token(
        self, auth_service: AuthenticationService, user_store: InMemoryUserStore
    ) -> None:
        """Test token creation for a user."""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
            permissions=["read"],
        )
        token = auth_service.create_token(user)

        assert isinstance(token, AuthToken)
        assert token.token is not None
        assert token.refresh_token is not None

    @pytest.mark.asyncio
    async def test_verify_token(
        self, auth_service: AuthenticationService, user_store: InMemoryUserStore
    ) -> None:
        """Test token verification."""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
        )
        token = auth_service.create_token(user)
        result = await auth_service.verify_token(token.token)

        assert result.is_ok()
        assert result.unwrap().user_id == "user123"


class TestLoginAttemptTracker:
    """TestLoginAttemptTracker - test tracking failed login attempts."""

    @pytest.mark.asyncio
    async def test_record_failure_and_check_locked(self) -> None:
        """Test recording failures and checking lockout."""
        tracker = LoginAttemptTracker(max_attempts=3, lockout_duration_seconds=300)

        await tracker.record_failure("test@example.com")
        assert not await tracker.is_locked("test@example.com")

        await tracker.record_failure("test@example.com")
        await tracker.record_failure("test@example.com")

        assert await tracker.is_locked("test@example.com")

    @pytest.mark.asyncio
    async def test_clear_on_success(self) -> None:
        """Test clearing failures on successful login."""
        tracker = LoginAttemptTracker(max_attempts=3, lockout_duration_seconds=300)

        await tracker.record_failure("test@example.com")
        await tracker.record_failure("test@example.com")
        await tracker.clear("test@example.com")

        assert not await tracker.is_locked("test@example.com")

    @pytest.mark.asyncio
    async def test_no_lockout_within_window(self) -> None:
        """Test lockout only happens within the observation window."""
        tracker = LoginAttemptTracker(max_attempts=3, lockout_duration_seconds=1)

        await tracker.record_failure("test@example.com")
        await tracker.record_failure("test@example.com")
        await tracker.record_failure("test@example.com")
        assert await tracker.is_locked("test@example.com")

        import asyncio
        await asyncio.sleep(1.1)

        assert not await tracker.is_locked("test@example.com")


class TestTokenGenerator:
    """TestTokenGenerator - test token generation."""

    @pytest.fixture
    def token_manager(self) -> JWTTokenManager:
        """Create a JWT token manager."""
        return JWTTokenManager(
            current_key_id="test",
            keys={"test": SecretStr("test_secret_key_12345678901234567890123456789123")},
            access_expiration_hours=1,
            refresh_expiration_days=30,
        )

    def test_create_access_token(self, token_manager: JWTTokenManager) -> None:
        """Test access token creation."""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
            permissions=["read"],
        )
        token = token_manager.create_access_token(user)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_token_pair(self, token_manager: JWTTokenManager) -> None:
        """Test token pair creation."""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
        )
        token_pair = token_manager.create_token_pair(user)

        assert isinstance(token_pair, AuthToken)
        assert token_pair.token is not None
        assert token_pair.refresh_token is not None
        assert token_pair.expires_at is not None
        assert token_pair.refresh_expires_at is not None

    @pytest.mark.asyncio
    async def test_verify_valid_token(self, token_manager: JWTTokenManager) -> None:
        """Test verification of a valid token."""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
        )
        token = token_manager.create_access_token(user)
        result = await token_manager.verify_token(token)

        assert result.is_ok()
        assert result.unwrap().user_id == user.user_id
        assert result.unwrap().email == user.email

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, token_manager: JWTTokenManager) -> None:
        """Test verification of an invalid token."""
        result = await token_manager.verify_token("invalid.token.here")

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_verify_expired_token(self) -> None:
        """Test verification of an expired token."""
        expired_manager = JWTTokenManager(
            current_key_id="test",
            keys={"test": SecretStr("test_secret_key_12345678901234567890123456789123")},
            access_expiration_hours=-1,
        )
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
        )
        token = expired_manager.create_access_token(user)
        result = await expired_manager.verify_token(token)

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_get_user_from_token(self, token_manager: JWTTokenManager) -> None:
        """Test extracting user information from token."""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user", "admin"],
            permissions=["read", "write"],
        )
        token = token_manager.create_access_token(user)
        result = await token_manager.get_user_from_token(token)

        assert result.is_ok()
        verified = result.unwrap()
        assert verified.user_id == "user123"
        assert verified.email == "test@example.com"
        assert "user" in verified.roles
        assert "admin" in verified.roles
