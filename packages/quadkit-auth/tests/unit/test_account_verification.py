"""Tests for AccountVerificationService Result-typed methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.auth.authn.account_verification import AccountVerificationService
from quadkit.auth.exceptions import AlreadyVerifiedError
from quadkit.auth.exceptions import UserNotFoundError


class TestSendVerification:
    """AccountVerificationService.send_verification returns Result."""

    @pytest.fixture
    def user_store(self) -> MagicMock:
        store = MagicMock()
        store.get_user_by_id = AsyncMock()
        store.update_user = AsyncMock()
        return store

    @pytest.fixture
    def service(self, user_store: MagicMock) -> AccountVerificationService:
        return AccountVerificationService(user_store=user_store)

    @pytest.mark.asyncio
    async def test_returns_ok_for_unverified_user(
        self, service: AccountVerificationService, user_store: MagicMock
    ) -> None:
        """send_verification returns Ok((token, expiry)) for an unverified user."""
        user = MagicMock()
        user.is_verified = False
        user.user_id = "user-1"
        user_store.get_user_by_id.return_value = user

        result = await service.send_verification("user-1")

        assert result.is_ok()
        token, expiry = result.unwrap()
        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_returns_err_user_not_found_for_missing_user(
        self, service: AccountVerificationService, user_store: MagicMock
    ) -> None:
        """send_verification returns Err(UserNotFoundError) when user doesn't exist."""
        user_store.get_user_by_id.return_value = None

        result = await service.send_verification("nonexistent")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), UserNotFoundError)

    @pytest.mark.asyncio
    async def test_returns_err_already_verified_for_verified_user(
        self, service: AccountVerificationService, user_store: MagicMock
    ) -> None:
        """send_verification returns Err(AlreadyVerifiedError) for an already-verified user."""
        user = MagicMock()
        user.is_verified = True
        user.user_id = "user-2"
        user_store.get_user_by_id.return_value = user

        result = await service.send_verification("user-2")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), AlreadyVerifiedError)

    @pytest.mark.asyncio
    async def test_ok_updates_user_in_store(
        self, service: AccountVerificationService, user_store: MagicMock
    ) -> None:
        """send_verification persists the generated token to the user store."""
        user = MagicMock()
        user.is_verified = False
        user.user_id = "user-3"
        user_store.get_user_by_id.return_value = user

        await service.send_verification("user-3")

        user_store.update_user.assert_awaited_once_with(user)


class TestResendVerification:
    """AccountVerificationService.resend_verification returns Result."""

    @pytest.fixture
    def user_store(self) -> MagicMock:
        store = MagicMock()
        store.get_user_by_email = AsyncMock()
        store.get_user_by_id = AsyncMock()
        store.update_user = AsyncMock()
        return store

    @pytest.fixture
    def service(self, user_store: MagicMock) -> AccountVerificationService:
        return AccountVerificationService(user_store=user_store)

    @pytest.mark.asyncio
    async def test_returns_ok_for_unverified_email(
        self, service: AccountVerificationService, user_store: MagicMock
    ) -> None:
        """resend_verification returns Ok((token, expiry)) for an unverified email."""
        user = MagicMock()
        user.is_verified = False
        user.user_id = "user-10"
        user_store.get_user_by_email.return_value = user
        user_store.get_user_by_id.return_value = user

        result = await service.resend_verification("user@example.com")

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_returns_err_user_not_found_for_unknown_email(
        self, service: AccountVerificationService, user_store: MagicMock
    ) -> None:
        """resend_verification returns Err(UserNotFoundError) for an unknown email."""
        user_store.get_user_by_email.return_value = None

        result = await service.resend_verification("unknown@example.com")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), UserNotFoundError)

    @pytest.mark.asyncio
    async def test_returns_err_already_verified_for_verified_email(
        self, service: AccountVerificationService, user_store: MagicMock
    ) -> None:
        """resend_verification returns Err(AlreadyVerifiedError) when already verified."""
        user = MagicMock()
        user.is_verified = True
        user.user_id = "user-11"
        user_store.get_user_by_email.return_value = user

        result = await service.resend_verification("verified@example.com")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), AlreadyVerifiedError)
