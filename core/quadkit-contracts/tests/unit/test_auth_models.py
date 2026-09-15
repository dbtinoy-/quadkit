"""Tests for auth data models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from quadkit.contracts.auth.models import UserIdentityProtocol, UserSession


class TestUserIdentityProtocol:
    """Tests for UserIdentityProtocol."""

    def test_is_runtime_checkable(self) -> None:
        """Test UserIdentityProtocol is runtime checkable."""
        assert isinstance(UserIdentityProtocol, type)

    def test_protocol_has_user_id_property(self) -> None:
        """Test protocol defines user_id property."""
        assert hasattr(UserIdentityProtocol, "user_id")

    def test_protocol_has_email_property(self) -> None:
        """Test protocol defines email property."""
        assert hasattr(UserIdentityProtocol, "email")

    def test_can_implement_protocol(self) -> None:
        """Test protocol can be implemented."""

        class MockIdentity:
            @property
            def user_id(self) -> str:
                return "user-123"

            @property
            def email(self) -> str:
                return "test@example.com"

        identity = MockIdentity()
        assert isinstance(identity, UserIdentityProtocol)
        assert identity.user_id == "user-123"
        assert identity.email == "test@example.com"


class TestUserSession:
    """Tests for UserSession."""

    def test_creation(self) -> None:
        """Test creating a UserSession."""
        session = UserSession(
            session_id="sess-123",
            user_id="user-456",
            device_id="device-789",
        )
        assert session.session_id == "sess-123"
        assert session.user_id == "user-456"
        assert session.device_id == "device-789"
        assert session.ip_address is None
        assert session.user_agent is None
        assert session.is_active is True

    def test_default_values(self) -> None:
        """Test UserSession has correct defaults."""
        session = UserSession(
            session_id="sess-123",
            user_id="user-456",
            device_id="device-789",
        )
        assert session.geo_location == {}
        assert session.fingerprint == {}
        assert session.is_active is True
        assert session.expires_at is None
        assert session.last_active_at is None
        assert session.mfa_verified_at is None
        assert session.created_at is None
        assert session.updated_at is None

    def test_custom_values(self) -> None:
        """Test UserSession with custom values."""
        now = datetime.now(UTC)
        session = UserSession(
            session_id="sess-123",
            user_id="user-456",
            device_id="device-789",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            geo_location={"country": "US"},
            fingerprint={"screen": "1920x1080"},
            is_active=False,
            expires_at=now + timedelta(hours=1),
            last_active_at=now,
            mfa_verified_at=now,
            created_at=now,
            updated_at=now,
        )
        assert session.ip_address == "192.168.1.1"
        assert session.user_agent == "Mozilla/5.0"
        assert session.geo_location == {"country": "US"}
        assert session.fingerprint == {"screen": "1920x1080"}
        assert session.is_active is False

    def test_is_expired_no_expiry(self) -> None:
        """Test is_expired returns False when no expiry set."""
        session = UserSession(
            session_id="sess-123",
            user_id="user-456",
            device_id="device-789",
        )
        assert session.is_expired() is False

    def test_is_expired_not_yet_expired(self) -> None:
        """Test is_expired returns False when not yet expired."""
        future = datetime.now(UTC) + timedelta(hours=1)
        session = UserSession(
            session_id="sess-123",
            user_id="user-456",
            device_id="device-789",
            expires_at=future,
        )
        assert session.is_expired() is False

    def test_is_expired_already_expired(self) -> None:
        """Test is_expired returns True when already expired."""
        past = datetime.now(UTC) - timedelta(hours=1)
        session = UserSession(
            session_id="sess-123",
            user_id="user-456",
            device_id="device-789",
            expires_at=past,
        )
        assert session.is_expired() is True

    def test_is_expired_naive_datetime(self) -> None:
        """Test is_expired handles naive datetime correctly."""
        # When expires_at is naive (no tzinfo), compare with naive now()
        future = datetime.now() + timedelta(hours=1)
        session = UserSession(
            session_id="sess-123",
            user_id="user-456",
            device_id="device-789",
            expires_at=future,
        )
        assert session.is_expired() is False

    def test_frozen_dataclass(self) -> None:
        """Test UserSession is frozen (immutable)."""
        from dataclasses import FrozenInstanceError

        session = UserSession(
            session_id="sess-123",
            user_id="user-456",
            device_id="device-789",
        )
        with pytest.raises(FrozenInstanceError):
            session.session_id = "new-id"


class TestUserSessionIntegration:
    """Integration tests for UserSession."""

    def test_can_use_with_identity_protocol(self) -> None:
        """Test UserSession can work with UserIdentityProtocol."""

        class SessionAsIdentity:
            def __init__(self, session: UserSession) -> None:
                self._session = session

            @property
            def user_id(self) -> str:
                return self._session.user_id

            @property
            def email(self) -> str:
                return "session@example.com"

        session = UserSession(
            session_id="sess-123",
            user_id="user-456",
            device_id="device-789",
        )
        identity = SessionAsIdentity(session)
        assert isinstance(identity, UserIdentityProtocol)
        assert identity.user_id == "user-456"

    def test_can_serialize_to_dict(self) -> None:
        """Test UserSession can be converted to dict."""
        session = UserSession(
            session_id="sess-123",
            user_id="user-456",
            device_id="device-789",
            ip_address="192.168.1.1",
            geo_location={"country": "US"},
        )
        # UserSession is a dataclass, so we can use asdict
        from dataclasses import asdict

        data = asdict(session)
        assert data["session_id"] == "sess-123"
        assert data["user_id"] == "user-456"
        assert data["geo_location"] == {"country": "US"}
