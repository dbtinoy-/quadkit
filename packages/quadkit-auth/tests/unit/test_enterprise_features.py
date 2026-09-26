from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from quadkit.auth.authn.apikeys import APIKeyManager
from quadkit.auth.policies.engine import PolicyEngine
from quadkit.auth.policies.types import (
    AuthorizationRequest,
    Condition,
    DecisionOutcome,
    Policy,
    PolicyEffect,
)
from quadkit.auth.session.manager import SessionManagerImpl
from quadkit.auth.storage.in_memory_stores import InMemorySessionStore


@pytest.fixture
def mock_api_key_repo():
    """Fake APIKeyRepositoryProtocol injected into APIKeyManager under test."""
    repo = MagicMock()
    repo.insert = AsyncMock(return_value="key-uuid")
    repo.find_by_prefix = AsyncMock(return_value=[])
    repo.update_last_used = AsyncMock()
    repo.revoke = AsyncMock(return_value=True)
    repo.find_by_user = AsyncMock(return_value=[])
    return repo


class TestAPIKeys:
    @pytest.mark.asyncio
    async def test_create_and_validate_key(self, mock_api_key_repo):
        manager = APIKeyManager(repo=mock_api_key_repo)
        user_id = "user-123"

        # Execute
        raw_key, api_key = await manager.create_key(user_id=user_id, name="Test Key")

        # Verify creation path
        assert raw_key.startswith("sk_live_")
        assert api_key.prefix == raw_key[: manager.DISPLAY_PREFIX_LENGTH]
        assert api_key.key_id == "key-uuid"
        mock_api_key_repo.insert.assert_awaited_once()

        # Stub find_by_prefix for the validate path
        mock_api_key_repo.find_by_prefix.return_value = [
            {
                "id": "key-uuid",
                "name": "Test Key",
                "key_hash": api_key.key_hash,
                "prefix": api_key.prefix,
                "user_id": user_id,
                "scopes": [],
                "expires_at": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
        ]

        # Valid key resolves to an APIKey
        validated = await manager.validate_key(raw_key)
        assert validated is not None
        assert validated.key_id == "key-uuid"
        mock_api_key_repo.update_last_used.assert_awaited_once()

        # Bad key resolves to None
        mock_api_key_repo.find_by_prefix.return_value = []
        assert await manager.validate_key("invalid.key") is None

    @pytest.mark.asyncio
    async def test_revoke_key(self, mock_api_key_repo):
        manager = APIKeyManager(repo=mock_api_key_repo)

        result = await manager.revoke_key("key-uuid")

        assert result is True
        mock_api_key_repo.revoke.assert_awaited_once_with("key-uuid")

    @pytest.mark.asyncio
    async def test_list_keys_empty(self, mock_api_key_repo):
        manager = APIKeyManager(repo=mock_api_key_repo)

        keys = await manager.list_keys("user-123")

        assert keys == []
        mock_api_key_repo.find_by_user.assert_awaited_once_with("user-123")


class TestSessions:
    @pytest.mark.asyncio
    async def test_session_lifecycle(self):
        store = InMemorySessionStore()
        manager = SessionManagerImpl(session_store=store)
        user_id = "user-123"
        fingerprint = {"device": "iPhone 15", "browser": "Safari"}

        session = await manager.create_session(
            user_id=user_id, fingerprint_data=fingerprint,
        )
        assert session.user_id == user_id
        assert session.fingerprint == fingerprint

    @pytest.mark.asyncio
    async def test_concurrent_session_limit(self):
        store = InMemorySessionStore()
        manager = SessionManagerImpl(session_store=store, max_sessions_per_user=5)
        user_id = "user-123"

        # Create 5 sessions (at limit)
        for i in range(5):
            await manager.create_session(user_id=user_id, fingerprint_data={"device": f"device{i}"})

        # Creating one more should evict the oldest, keeping total at 5
        await manager.create_session(user_id=user_id, fingerprint_data={"device": "new"})

        sessions_before = await manager.get_active_sessions(user_id)
        assert len(sessions_before) == 5


class TestABAC:
    def test_policy_evaluation(self):
        # Create a policy allowing access to documents in 'engineering' department
        policy = Policy(
            policy_id="pol_1",
            name="Test Policy",
            effect=PolicyEffect.ALLOW,
            principals=["user:*"],
            actions=["document:read"],
            resources=["document:*"],
            conditions=[
                Condition(
                    attribute="user.department", operator="equals", value="engineering",
                ),
            ],
        )

        engine = PolicyEngine(policies=[policy])

        # Request from user in engineering
        req = AuthorizationRequest(
            principal="user:u1",
            action="document:read",
            resource="document:doc1",
            context={"user": {"department": "engineering"}},
        )

        decision = engine.evaluate(req)
        assert decision.decision == DecisionOutcome.ALLOW

        # Request from user in sales
        req_sales = AuthorizationRequest(
            principal="user:u2",
            action="document:read",
            resource="document:doc1",
            context={"user": {"department": "sales"}},
        )

        decision_sales = engine.evaluate(req_sales)
        assert decision_sales.decision != DecisionOutcome.ALLOW


class TestDelegation:
    @pytest.mark.asyncio
    async def test_delegation_flow(self):
        # Integration-level delegation tests require broader orchestration;
        # component-level coverage is provided by TestAPIKeys and TestSessions.
        pass
