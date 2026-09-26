"""Tests to ensure password verification works correctly."""

from unittest.mock import AsyncMock, patch

import pytest

from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.authn.services import AuthenticationService
from quadkit.auth.storage.token_store import InMemoryUserStore
from quadkit.auth.authn.core import User
from quadkit.auth.models.user import UserCredentials


@pytest.mark.asyncio
async def test_password_verification_called_for_existing_user():
    """Ensure PasswordHasher.verify is called when user exists and has a hash."""
    user_store = InMemoryUserStore()
    service = AuthenticationService(
        password_policy=PasswordPolicy(),
        user_store=user_store,
        token_manager=None,
    )

    from datetime import datetime
    fake_user = User(
        user_id="u1",
        email="user1@example.com",
        name="user1",
        is_active=True,
        roles=[],
        created_at=datetime.now(),
    )
    fake_creds = UserCredentials(
        user_id="u1",
        hashed_password="$2b$12$testhash",
    )

    async def fake_get_by_email(email):
        return fake_user

    async def fake_get_credentials(user_id):
        return fake_creds

    user_store.get_user_by_email = fake_get_by_email
    user_store.get_credentials = fake_get_credentials

    async def fake_update(user):
        pass

    user_store.update_user = fake_update

    with patch.object(PasswordHasher, "verify", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True
        result = await service.authenticate_user("user1@example.com", "password123")
        assert result.is_ok()
        mock_verify.assert_called_once()
