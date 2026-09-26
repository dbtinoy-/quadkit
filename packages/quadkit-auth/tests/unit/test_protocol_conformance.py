"""Protocol conformance tests for quadkit-auth implementations.

Verifies at test-time that the concrete classes in quadkit-auth satisfy
the ``@runtime_checkable`` protocols defined in ``quadkit-contracts``.
These tests act as regression guards: if a protocol definition or a class
signature changes in an incompatible way, these tests will fail immediately.
"""

from __future__ import annotations

from pydantic import SecretStr
import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.security import PasswordHasher
from quadkit.auth.authz.service import AuthorizationService
from quadkit.auth.models.user import User
from quadkit.auth.policies.engine import PolicyEngine
from quadkit.auth.session.manager import SessionManagerImpl
from quadkit.contracts.auth import (
    AuthenticatedUserProtocol,
    AuthorizerProtocol,
    PasswordHasherProtocol,
    TokenManagerProtocol,
)
from quadkit.contracts.auth.policy import PolicyStoreProtocol

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_SECRET = SecretStr("test-secret-key-longer-than-32-bytes!")


def _make_jwt_manager() -> JWTTokenManager:
    """Return a minimal JWTTokenManager suitable for structural checks."""
    return JWTTokenManager(current_key_id="default", keys={"default": _TEST_SECRET})


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------


class TestUserProtocolConformance:
    """User satisfies AuthenticatedUserProtocol from contracts."""

    def test_user_is_authenticated_user(self) -> None:
        user = User(user_id="u1", email="a@b.com", name="Alice")
        assert isinstance(user, AuthenticatedUserProtocol)

    def test_user_has_role_method(self) -> None:
        user = User(user_id="u1", email="a@b.com", roles=["admin"])
        assert user.has_role("admin")
        assert not user.has_role("viewer")

    def test_user_has_permission_method(self) -> None:
        user = User(user_id="u1", email="a@b.com", permissions=["posts.read"])
        assert user.has_permission("posts.read")
        assert not user.has_permission("posts.write")


# ---------------------------------------------------------------------------
# PasswordHasher
# ---------------------------------------------------------------------------


class TestPasswordHasherConformance:
    """PasswordHasher satisfies PasswordHasherProtocol."""

    def test_isinstance_password_hasher_protocol(self) -> None:
        hasher = PasswordHasher()
        assert isinstance(hasher, PasswordHasherProtocol)

    def test_has_hash_method(self) -> None:
        assert callable(getattr(PasswordHasher, "hash", None))

    def test_has_verify_method(self) -> None:
        assert callable(getattr(PasswordHasher, "verify", None))

    def test_has_needs_rehash_method(self) -> None:
        assert callable(getattr(PasswordHasher, "needs_rehash", None))

    def test_has_rehash_if_needed_method(self) -> None:
        assert callable(getattr(PasswordHasher, "rehash_if_needed", None))


# ---------------------------------------------------------------------------
# JWTTokenManager
# ---------------------------------------------------------------------------


class TestJWTTokenManagerConformance:
    """JWTTokenManager satisfies TokenManagerProtocol from contracts."""

    def test_isinstance_token_manager(self) -> None:
        mgr = _make_jwt_manager()
        assert isinstance(mgr, TokenManagerProtocol)

    def test_has_create_token(self) -> None:
        mgr = _make_jwt_manager()
        assert callable(getattr(mgr, "create_token", None))

    def test_has_verify_token(self) -> None:
        mgr = _make_jwt_manager()
        assert callable(getattr(mgr, "verify_token", None))

    def test_has_refresh_token(self) -> None:
        mgr = _make_jwt_manager()
        assert callable(getattr(mgr, "refresh_token", None))

    def test_create_token_delegates_to_create_token_pair(self) -> None:
        """create_token() must return an AuthToken just like create_token_pair()."""
        mgr = _make_jwt_manager()
        user = User(user_id="u1", email="a@b.com", name="Alice")
        token_pair = mgr.create_token_pair(user)
        token = mgr.create_token(user)

        # Both return AuthToken instances with an access token
        assert token.token
        assert token_pair.token
        assert token.refresh_token


# ---------------------------------------------------------------------------
# AuthorizationService
# ---------------------------------------------------------------------------


class TestAuthorizationServiceConformance:
    """AuthorizationService satisfies AuthorizerProtocol from contracts."""

    def test_isinstance_authorizer(self) -> None:
        svc = AuthorizationService()
        assert isinstance(svc, AuthorizerProtocol)

    def test_has_authorize_method(self) -> None:
        svc = AuthorizationService()
        assert callable(getattr(svc, "authorize", None))

    def test_has_check_access_method(self) -> None:
        svc = AuthorizationService()
        assert callable(getattr(svc, "check_access", None))

    def test_has_can_method(self) -> None:
        svc = AuthorizationService()
        assert callable(getattr(svc, "can", None))

    @pytest.mark.asyncio
    async def test_authorize_with_audit_logger_does_not_raise(self) -> None:
        """AuditLoggerProtocol integration: authorize() calls the audit logger."""
        from unittest.mock import AsyncMock

        audit_logger = AsyncMock()
        audit_logger.log = AsyncMock()
        svc = AuthorizationService(audit_logger=audit_logger)

        user = User(user_id="u1", email="a@b.com", roles=["admin"])
        # With admin role and no explicit rules, access may or may not be granted;
        # what matters is that the audit logger was called.
        await svc.authorize(user, "read", "posts")
        audit_logger.log.assert_awaited_once()


# ---------------------------------------------------------------------------
# SessionManagerImpl
# ---------------------------------------------------------------------------


class TestSessionManagerInit:
    """SessionManagerImpl accepts optional audit_logger."""

    def test_default_init(self) -> None:
        mgr = SessionManagerImpl()
        assert mgr._audit_logger is None

    def test_accepts_audit_logger_kwarg(self) -> None:
        from unittest.mock import MagicMock

        audit_logger = MagicMock()
        mgr = SessionManagerImpl(audit_logger=audit_logger)
        assert mgr._audit_logger is audit_logger


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------


class TestPolicyEngineConformance:
    """PolicyEngine accepts optional PolicyStoreProtocol."""

    def test_default_init_empty_policies(self) -> None:
        engine = PolicyEngine()
        assert engine.policies == []
        assert engine._store is None

    def test_accepts_policy_store(self) -> None:
        from unittest.mock import AsyncMock

        store = AsyncMock(spec=PolicyStoreProtocol)
        engine = PolicyEngine(store=store)
        assert engine._store is store

    @pytest.mark.asyncio
    async def test_load_from_store_noop_without_store(self) -> None:
        """load_from_store() is a no-op when no store is configured."""
        engine = PolicyEngine()
        await engine.load_from_store()  # Must not raise
        assert engine.policies == []


# ---------------------------------------------------------------------------
# CachedUserStore
# ---------------------------------------------------------------------------


class TestCachedUserStorePubSub:
    """CachedUserStore publishes invalidation events via PubSubProtocol."""

    @pytest.mark.asyncio
    async def test_update_user_publishes_invalidation(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from quadkit.auth.storage.cached_user_store import (
            CACHE_INVALIDATION_TOPIC,
            CachedUserStore,
        )

        user_store = AsyncMock()
        cache_service = MagicMock()
        cache_service.get = AsyncMock(return_value=None)
        cache_service.set = AsyncMock()
        cache_service.delete_many = AsyncMock()

        pubsub = AsyncMock()
        pubsub.publish = AsyncMock()

        store = CachedUserStore(
            user_store=user_store,
            cache_service=cache_service,
            pubsub=pubsub,
        )
        user = User(user_id="u1", email="a@b.com", name="Alice")
        user_store.update_user = AsyncMock()
        await store.update_user(user)

        pubsub.publish.assert_awaited_once()
        call_args = pubsub.publish.call_args
        assert call_args[0][0] == CACHE_INVALIDATION_TOPIC
        payload = call_args[0][1]
        assert payload["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_subscribe_to_invalidations_subscribes(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from quadkit.auth.storage.cached_user_store import (
            CACHE_INVALIDATION_TOPIC,
            CachedUserStore,
        )

        user_store = AsyncMock()
        cache_service = MagicMock()
        pubsub = AsyncMock()
        pubsub.subscribe = AsyncMock()

        store = CachedUserStore(
            user_store=user_store,
            cache_service=cache_service,
            pubsub=pubsub,
        )
        await store.subscribe_to_invalidations()
        pubsub.subscribe.assert_awaited_once_with(
            CACHE_INVALIDATION_TOPIC, store._handle_invalidation
        )

    @pytest.mark.asyncio
    async def test_handle_invalidation_evicts_l1_cache(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from quadkit.auth.storage.cached_user_store import CachedUserStore

        user_store = AsyncMock()
        cache_service = MagicMock()

        store = CachedUserStore(user_store=user_store, cache_service=cache_service)
        # Manually populate L1 cache
        import time

        store._memory_cache["user:id:u1"] = {
            "user": None,
            "expires_at": time.monotonic() + 60,
        }
        store._memory_cache["user:email:a@b.com"] = {
            "user": None,
            "expires_at": time.monotonic() + 60,
        }

        await store._handle_invalidation({"user_id": "u1", "email": "a@b.com"})

        assert "user:id:u1" not in store._memory_cache
        assert "user:email:a@b.com" not in store._memory_cache
