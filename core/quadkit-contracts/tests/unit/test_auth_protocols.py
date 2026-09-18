"""Tests for auth protocol definitions."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from quadkit.contracts.auth.protocols import (
    AuthProviderProtocol,
    MFAManagerProtocol,
    PasswordHasherProtocol,
    PasswordPolicyProtocol,
)


class TestPasswordHasherProtocol:
    """Tests for PasswordHasherProtocol."""

    @pytest.mark.asyncio
    async def test_has_hash_method(self) -> None:
        """Test protocol has hash async method."""

        class Hasher:
            async def hash(self, password: str) -> str:
                return "hashed"

        hasher = Hasher()
        result = await hasher.hash("password")
        assert result == "hashed"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Hasher:
            async def hash(self, password: str) -> str:
                return ""

            async def verify(self, password: str, hashed_password: str) -> bool:
                return False

            def needs_rehash(self, hashed_password: str) -> bool:
                return False

            async def rehash_if_needed(
                self, password: str, hashed_password: str | None
            ) -> str | None:
                return None

        assert isinstance(Hasher(), PasswordHasherProtocol)

    @pytest.mark.asyncio
    async def test_has_verify_method(self) -> None:
        """Test protocol has verify async method."""

        class Hasher:
            async def verify(self, password: str, hashed_password: str) -> bool:
                return True

        hasher = Hasher()
        result = await hasher.verify("password", "hash")
        assert result is True


class TestPasswordPolicyProtocol:
    """Tests for PasswordPolicyProtocol."""

    def test_has_validate_method(self) -> None:
        """Test protocol has validate method."""

        class Policy:
            def validate(self, password: str) -> None:
                if len(password) < 8:
                    raise ValueError("Too short")

        policy = Policy()
        policy.validate("password123")

    def test_has_is_valid_method(self) -> None:
        """Test protocol has is_valid method."""

        class Policy:
            def is_valid(self, password: str) -> bool:
                return len(password) >= 8

        policy = Policy()
        assert policy.is_valid("password123") is True

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Policy:
            def validate(self, password: str) -> None:
                pass

            def is_valid(self, password: str) -> bool:
                return False

        assert isinstance(Policy(), PasswordPolicyProtocol)


class TestMFAManagerProtocol:
    """Tests for MFAManagerProtocol."""

    @pytest.mark.asyncio
    async def test_has_enroll_method(self) -> None:
        """Test protocol has enroll async method."""

        class Manager:
            async def enroll(self, user_id: str, method: str) -> dict[str, Any]:
                return {"user_id": user_id, "method": method}

        manager = Manager()
        result = await manager.enroll("user1", "totp")
        assert result["method"] == "totp"

    @pytest.mark.asyncio
    async def test_has_verify_method(self) -> None:
        """Test protocol has verify async method."""

        class Manager:
            async def verify(self, user_id: str, method: str, code: str) -> bool:
                return code == "123456"

        manager = Manager()
        result = await manager.verify("user1", "totp", "123456")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_revoke_method(self) -> None:
        """Test protocol has revoke async method."""

        class Manager:
            async def revoke(self, user_id: str, method: str) -> None:
                pass

        manager = Manager()
        await manager.revoke("user1", "totp")

    @pytest.mark.asyncio
    async def test_has_list_methods_method(self) -> None:
        """Test protocol has list_methods async method."""

        class Manager:
            async def list_methods(self, user_id: str) -> list[str]:
                return ["totp", "email"]

        manager = Manager()
        result = await manager.list_methods("user1")
        assert "totp" in result

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Manager:
            async def enroll(self, user_id: str, method: str) -> dict[str, Any]:
                return {}

            async def verify(self, user_id: str, method: str, code: str) -> bool:
                return False

            async def revoke(self, user_id: str, method: str) -> None:
                pass

            async def list_methods(self, user_id: str) -> list[str]:
                return []

            async def get_mfa(self, user_id: str) -> Any | None:
                return None

        assert isinstance(Manager(), MFAManagerProtocol)


class TestAuthProviderProtocol:
    """Tests for AuthProviderProtocol."""

    @pytest.mark.asyncio
    async def test_has_get_user_method(self) -> None:
        """Test protocol has get_user async method."""

        class Provider:
            async def get_user(self, user_id: str) -> Any | None:
                return {"id": user_id}

        provider = Provider()
        result = await provider.get_user("user1")
        assert result["id"] == "user1"

    @pytest.mark.asyncio
    async def test_has_verify_token_method(self) -> None:
        """Test protocol has verify_token async method."""

        class Provider:
            async def verify_token(self, token: str) -> Any:
                return {"user_id": "user1"}

        provider = Provider()
        result = await provider.verify_token("token123")
        assert result["user_id"] == "user1"

    def test_has_has_any_role_method(self) -> None:
        """Test protocol has has_any_role method."""

        class Provider:
            def has_any_role(self, user: Any, roles: list[str]) -> bool:
                return "admin" in roles

        provider = Provider()
        user = MagicMock()
        result = provider.has_any_role(user, ["admin", "user"])
        assert result is True

    def test_has_has_any_permission_method(self) -> None:
        """Test protocol has has_any_permission method."""

        class Provider:
            def has_any_permission(self, user: Any, permissions: list[str]) -> bool:
                return "read" in permissions

        provider = Provider()
        user = MagicMock()
        result = provider.has_any_permission(user, ["read", "write"])
        assert result is True

    def test_protocol_has_provider_methods(self) -> None:
        """Test AuthProviderProtocol has Provider methods."""

        assert hasattr(AuthProviderProtocol, "name")
        assert hasattr(AuthProviderProtocol, "priority")
        assert hasattr(AuthProviderProtocol, "register")
        assert hasattr(AuthProviderProtocol, "boot")
