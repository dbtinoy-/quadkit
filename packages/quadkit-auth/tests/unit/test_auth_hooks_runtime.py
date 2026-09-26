"""Focused runtime hook tests for quadkit-auth."""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr
import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.authn.services import AuthenticationService
from quadkit.auth.config import AuthConfig, JWTConfig
from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)
from quadkit.auth.di.sub_providers.token_provider import TokenProvider
from quadkit.auth.hooks import (
    AuthTokenRefreshedHook,
    AuthTokenRevokedHook,
    AuthUserAuthenticatedHook,
)
from quadkit.auth.models.user import User
from quadkit.auth.storage.token_store import InMemoryUserStore
from quadkit.contracts.core import HookRegistryProtocol


class _RecordingHooks:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def register_action(
        self,
        hook_name: str,
        handler: Any,
        priority: int = 100,
        *,
        once: bool = False,
    ) -> None:
        raise NotImplementedError

    def register_filter(
        self,
        hook_name: str,
        handler: Any,
        priority: int = 100,
        *,
        once: bool = False,
    ) -> None:
        raise NotImplementedError

    def unregister_action(self, hook_name: str, handler: Any) -> bool:
        raise NotImplementedError

    def unregister_filter(self, hook_name: str, handler: Any) -> bool:
        raise NotImplementedError

    async def call_action(self, hook_name: str, **kwargs: Any) -> None:
        self.calls.append((hook_name, kwargs["payload"]))

    async def apply_filter(self, hook_name: str, value: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def has_action(self, hook_name: str) -> bool:
        raise NotImplementedError

    def has_filter(self, hook_name: str) -> bool:
        raise NotImplementedError

    def clear(self, hook_name: str | None = None) -> None:
        raise NotImplementedError


def _payloads_for(hooks: _RecordingHooks, hook_name: str) -> list[object]:
    return [payload for name, payload in hooks.calls if name == hook_name]


def _make_token_manager() -> JWTTokenManager:
    return JWTTokenManager(
        current_key_id="test",
        keys={"test": SecretStr("test_secret_key_12345678901234567890123456789123")},
        access_expiration_hours=1,
        refresh_expiration_days=30,
    )


def _make_user() -> User:
    return User(
        user_id="user-123",
        name="Test User",
        email="test@example.com",
        roles=["user"],
        permissions=["read"],
    )


class _HookingContainer:
    def __init__(self, hooks: HookRegistryProtocol | None) -> None:
        self._hooks = hooks

    async def resolve_optional(self, protocol: type[object]) -> object | None:
        if protocol is HookRegistryProtocol:
            return self._hooks
        return None

    async def resolve(self, protocol: type[object]) -> object | None:
        _ = protocol
        return None


class _Registrar:
    def singleton(
        self,
        service_type: object,
        instance: object | None = None,
        *,
        name: str | None = None,
        factory: object | None = None,
        validate: bool = True,
    ) -> None:
        _ = (service_type, instance, name, factory, validate)

    def has(self, service_type: object) -> bool:
        _ = service_type
        return False


@pytest.mark.asyncio
async def test_authenticate_user_emits_auth_login_hook() -> None:
    hooks = _RecordingHooks()
    user_store = InMemoryUserStore()
    password = "Password123!"
    hashed_password = await PasswordHasher().hash(password)
    user = await user_store.create_user(
        name="test",
        email="test@example.com",
        hashed_password=hashed_password,
        roles=["user"],
    )
    service = AuthenticationService(
        password_policy=PasswordPolicy(),
        user_store=user_store,
        token_manager=_make_token_manager(),
    )

    service.set_hook_registry(hooks)

    result = await service.authenticate_user("test@example.com", password)

    assert result.is_ok()
    assert _payloads_for(hooks, "auth.login") == [
        AuthUserAuthenticatedHook(user_id=user.user_id, method="password")
    ]


@pytest.mark.asyncio
async def test_logout_emits_auth_logout_hook() -> None:
    hooks = _RecordingHooks()
    manager = _make_token_manager()
    manager.set_hook_registry(hooks)
    token_pair = manager.create_token_pair(_make_user())

    result = await manager.logout(token_pair.token)

    assert result.is_ok()
    assert _payloads_for(hooks, "auth.logout") == [
        AuthTokenRevokedHook(user_id="user-123", token_type="access")
    ]


@pytest.mark.asyncio
async def test_refresh_access_token_emits_token_refreshed_hook() -> None:
    hooks = _RecordingHooks()
    manager = _make_token_manager()
    manager.set_hook_registry(hooks)
    token_pair = manager.create_token_pair(_make_user())

    refreshed = await manager.refresh_access_token(token_pair.refresh_token or "")

    assert refreshed.refresh_token is not None
    assert _payloads_for(hooks, "token.refreshed") == [
        AuthTokenRefreshedHook(user_id="user-123", token_type="access")
    ]


@pytest.mark.asyncio
async def test_authentication_provider_boot_wires_optional_hooks_into_runtime_services() -> (
    None
):
    hooks = _RecordingHooks()
    secret = "test_secret_key_12345678901234567890123456789123"
    provider = AuthenticationProvider(
        config=AuthConfig(
            secret_key=secret,
            token=JWTConfig(secret_key=secret),
        )
    )

    await provider.boot(_HookingContainer(hooks))

    assert provider.service._hooks is hooks
    assert provider.token_manager._hooks is hooks


@pytest.mark.asyncio
async def test_token_provider_boot_wires_optional_hooks_into_jwt_token_manager() -> (
    None
):
    hooks = _RecordingHooks()
    provider = TokenProvider(
        secret_key="test_secret_key_12345678901234567890123456789123"
    )

    await provider.register(_Registrar())
    await provider.boot(_HookingContainer(hooks))

    assert provider.token_manager._hooks is hooks
