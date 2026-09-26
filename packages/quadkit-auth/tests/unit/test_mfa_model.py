"""Tests for auth MFA model."""

import pytest
from datetime import datetime

from quadkit.auth.models.mfa import UserMFA


class TestUserMFA:
    def test_user_mfa_creation(self) -> None:
        mfa = UserMFA(mfa_id="mfa-123", user_id="user-456")
        assert mfa.mfa_id == "mfa-123"
        assert mfa.user_id == "user-456"
        assert mfa.mfa_type == "totp"
        assert mfa.secret == ""
        assert mfa.is_enabled is False
        assert mfa.last_used_at is None
        assert mfa.created_at is None
        assert mfa.updated_at is None

    def test_user_mfa_with_custom_type(self) -> None:
        mfa = UserMFA(mfa_id="mfa-123", user_id="user-456", mfa_type="sms")
        assert mfa.mfa_type == "sms"

    def test_user_mfa_with_secret(self) -> None:
        secret = "JBSWY3DPEHPK3PXP"
        mfa = UserMFA(mfa_id="mfa-123", user_id="user-456", secret=secret)
        assert mfa.secret == secret

    def test_user_mfa_is_frozen(self) -> None:
        mfa = UserMFA(mfa_id="mfa-123", user_id="user-456")
        with pytest.raises(Exception):
            mfa.mfa_id = "new-id"

    def test_user_mfa_equality(self) -> None:
        mfa1 = UserMFA(mfa_id="mfa-123", user_id="user-456")
        mfa2 = UserMFA(mfa_id="mfa-123", user_id="user-456")
        assert mfa1 == mfa2

    def test_user_mfa_with_timestamps(self) -> None:
        now = datetime.now()
        mfa = UserMFA(
            mfa_id="mfa-123",
            user_id="user-456",
            last_used_at=now,
            created_at=now,
            updated_at=now,
        )
        assert mfa.last_used_at == now
        assert mfa.created_at == now
        assert mfa.updated_at == now
