"""Tests for the APIKey model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quadkit.auth.models.apikey import APIKey


def _key(
    expires_at: datetime | None = None, revoked_at: datetime | None = None
) -> APIKey:
    return APIKey(
        key_id="key-1",
        name="test key",
        key_hash="hash",
        prefix="lx",
        user_id="user-1",
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


class TestAPIKeyIsActive:
    def test_active_with_no_expiry(self) -> None:
        assert _key().is_active() is True

    def test_active_with_future_aware_expiry(self) -> None:
        assert (
            _key(expires_at=datetime.now(UTC) + timedelta(days=1)).is_active() is True
        )

    def test_expired_aware_expiry(self) -> None:
        assert (
            _key(expires_at=datetime.now(UTC) - timedelta(days=1)).is_active() is False
        )

    def test_active_with_future_naive_expiry(self) -> None:
        # Naive values are assumed to be UTC (in-memory store convention).
        assert (
            _key(
                expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
            ).is_active()
            is True
        )

    def test_expired_naive_expiry(self) -> None:
        naive_past = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
        assert _key(expires_at=naive_past).is_active() is False

    def test_revoked_key_is_inactive_even_with_future_expiry(self) -> None:
        key = _key(
            expires_at=datetime.now(UTC) + timedelta(days=1),
            revoked_at=datetime.now(UTC),
        )
        assert key.is_active() is False

    def test_expiring_soon_is_still_active(self) -> None:
        assert (
            _key(expires_at=datetime.now(UTC) + timedelta(seconds=30)).is_active()
            is True
        )
