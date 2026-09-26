"""Regression tests: AuthenticationProvider must genuinely satisfy AuthProviderProtocol.

Background: ``AuthProviderProtocol`` declares ``session_manager``,
``api_key_manager``, and ``mfa_manager`` as "Optional managers — None when
the feature is disabled/not configured", plus ``has_any_role`` /
``has_any_permission`` methods. Before this fix, ``AuthenticationProvider``
(the class bound to ``AuthProviderProtocol`` by ``AuthenticationProvider.
register()``) never set those three attributes at all — accessing them
raised ``AttributeError`` instead of returning ``None`` — and never defined
``has_any_role`` / ``has_any_permission``. This was invisible because
nothing resolved ``AuthenticatorProtocol`` from a real container to
exercise the session/API-key/MFA code paths that read these attributes
(``SessionAuthenticator``, ``ApiKeyAuthenticator``, the MFA guard decorator
in ``AuthMiddleware``, and ``SessionValidator.check_authorization``).

This also covers a companion bug found alongside it:
``SessionAuthenticator.authenticate()`` treated ``SessionManagerImpl.
validate_session()``'s return value as the session object directly, when it
actually returns a ``Result`` (Ok/Err) that must be unwrapped first.
"""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.auth.authn.security import PasswordHasher
from quadkit.auth.authz.service import AuthorizationService
from quadkit.auth.di.bundle_provider import AuthBundleProvider
from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)
from quadkit.auth.session.manager import SessionManagerImpl
from quadkit.auth.storage.in_memory_stores import InMemorySessionStore
from quadkit.auth.storage.token_store import InMemoryUserStore
from quadkit.auth.web.middleware.session_authenticator import SessionAuthenticator
from quadkit.contracts.auth import AuthenticatorProtocol, AuthProviderProtocol
from quadkit.di.container import Container


async def _make_user(user_store: InMemoryUserStore, name: str, email: str):
    hashed = await PasswordHasher().hash("Password123!")
    return await user_store.create_user(name=name, email=email, hashed_password=hashed)


class TestAuthenticationProviderDefaultAttributes:
    """AuthenticationProvider must expose all AuthProviderProtocol attributes."""

    def test_optional_managers_default_to_none_not_missing(self) -> None:
        """Regression: accessing these used to raise AttributeError."""
        provider = AuthenticationProvider()

        assert provider.session_manager is None
        assert provider.api_key_manager is None
        assert provider.mfa_manager is None
        assert provider.delegation_manager is None

    def test_satisfies_auth_provider_protocol_structurally(self) -> None:
        """Regression: isinstance() check used to fail (missing attributes)."""
        provider = AuthenticationProvider()
        assert isinstance(provider, AuthProviderProtocol)

    def test_has_any_role_without_authorization_service_returns_false(self) -> None:
        """No AuthorizationProvider registered => conservatively deny, don't crash."""
        provider = AuthenticationProvider()
        user = object()
        assert provider.has_any_role(user, ["admin"]) is False
        assert provider.has_any_permission(user, ["articles.write"]) is False


class TestAuthenticationProviderBootWiring:
    """boot() must attach real sibling-provider managers when present."""

    @pytest.mark.asyncio
    async def test_boot_attaches_session_manager_and_authorization_service(
        self,
    ) -> None:
        container = Container()
        bundle = AuthBundleProvider()
        await bundle.register(container)
        container.freeze()
        await bundle.boot(container)

        authn = bundle._authn
        assert isinstance(authn.session_manager, SessionManagerImpl)
        assert isinstance(authn._authorization_service, AuthorizationService)

    @pytest.mark.asyncio
    async def test_has_any_role_delegates_to_real_authorization_service_after_boot(
        self,
    ) -> None:
        container = Container()
        bundle = AuthBundleProvider(
            initial_roles={"editor": {"permissions": ["articles.write"]}},
        )
        await bundle.register(container)
        container.freeze()
        await bundle.boot(container)

        authn = bundle._authn

        class FakeUser:
            roles = ["editor"]
            permissions: list[str] = []
            is_superuser = False

        assert authn.has_any_role(FakeUser(), ["editor"]) is True
        assert authn.has_any_role(FakeUser(), ["admin"]) is False


class TestAuthenticatorProtocolEndToEnd:
    """Resolve AuthenticatorProtocol from a booted container and exercise it."""

    @pytest.mark.asyncio
    async def test_session_cookie_authenticates_real_user(self) -> None:
        """Regression: crashed with AttributeError on session_manager,
        then with AttributeError on unwrapping the Result from
        validate_session() once session_manager was wired.
        """
        container = Container()
        bundle = AuthBundleProvider()
        await bundle.register(container)
        container.freeze()
        await bundle.boot(container)

        authenticator = await container.resolve(AuthenticatorProtocol)
        auth_provider = await container.resolve(AuthProviderProtocol)

        user = await _make_user(auth_provider.user_store, "sessuser", "sess@example.com")
        session = await auth_provider.session_manager.create_session(
            user_id=user.user_id,
            fingerprint_data={},
        )

        request = _FakeRequest(cookies={"session_id": session.session_id})
        result = await authenticator.authenticate(request)

        assert result is not None
        assert result.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_unknown_session_cookie_returns_none_not_crash(self) -> None:
        container = Container()
        bundle = AuthBundleProvider()
        await bundle.register(container)
        container.freeze()
        await bundle.boot(container)

        authenticator = await container.resolve(AuthenticatorProtocol)
        request = _FakeRequest(cookies={"session_id": "does-not-exist"})

        result = await authenticator.authenticate(request)
        assert result is None

    @pytest.mark.asyncio
    async def test_anonymous_request_returns_none(self) -> None:
        container = Container()
        bundle = AuthBundleProvider()
        await bundle.register(container)
        container.freeze()
        await bundle.boot(container)

        authenticator = await container.resolve(AuthenticatorProtocol)
        request = _FakeRequest(cookies={})

        result = await authenticator.authenticate(request)
        assert result is None


class TestSessionAuthenticatorResultUnwrapping:
    """SessionAuthenticator must unwrap the Result validate_session() returns."""

    @pytest.mark.asyncio
    async def test_unwraps_ok_result_from_real_session_manager(self) -> None:
        user_store = InMemoryUserStore()
        user = await _make_user(user_store, "realsess", "realsess@example.com")

        session_manager = SessionManagerImpl(session_store=InMemorySessionStore())
        session = await session_manager.create_session(
            user_id=user.user_id, fingerprint_data={}
        )

        auth_provider = _StubAuthProvider(
            user_store=user_store, session_manager=session_manager
        )
        authenticator = SessionAuthenticator(auth_provider)

        request = _FakeRequest(cookies={"session_id": session.session_id})
        result = await authenticator.authenticate(request)

        assert result is not None
        assert result.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_err_result_from_missing_session_returns_none(self) -> None:
        user_store = InMemoryUserStore()
        session_manager = SessionManagerImpl(session_store=InMemorySessionStore())
        auth_provider = _StubAuthProvider(
            user_store=user_store, session_manager=session_manager
        )
        authenticator = SessionAuthenticator(auth_provider)

        request = _FakeRequest(cookies={"session_id": "nonexistent"})
        result = await authenticator.authenticate(request)

        assert result is None

    @pytest.mark.asyncio
    async def test_still_supports_a_session_manager_returning_plain_object(
        self,
    ) -> None:
        """Backward compatibility: a simpler session manager that returns the
        session object directly (no Result wrapper) must keep working.
        """
        user_store = InMemoryUserStore()
        user = await _make_user(user_store, "plainsess", "plainsess@example.com")

        class _PlainSession:
            user_id = user.user_id

        class _PlainSessionManager:
            async def validate_session(self, session_id: str) -> Any:
                return _PlainSession() if session_id == "good" else None

        auth_provider = _StubAuthProvider(
            user_store=user_store, session_manager=_PlainSessionManager()
        )
        authenticator = SessionAuthenticator(auth_provider)

        ok_request = _FakeRequest(cookies={"session_id": "good"})
        result = await authenticator.authenticate(ok_request)
        assert result is not None
        assert result.user_id == user.user_id

        bad_request = _FakeRequest(cookies={"session_id": "bad"})
        assert await authenticator.authenticate(bad_request) is None


class _FakeState:
    """Minimal stand-in for Starlette's request.state (attribute bag)."""


class _FakeRequest:
    def __init__(self, cookies: dict[str, str]) -> None:
        self.cookies = cookies
        self.headers: dict[str, str] = {}
        self.query_params: dict[str, str] = {}
        self.state = _FakeState()


class _StubAuthProvider:
    """Minimal AuthProviderProtocol stand-in for SessionAuthenticator unit tests."""

    def __init__(self, *, user_store: InMemoryUserStore, session_manager: Any) -> None:
        self.user_store = user_store
        self.session_manager = session_manager
        self.delegation_manager = None
        self.api_key_manager = None
        self.mfa_manager = None

    async def get_user(self, user_id: str) -> Any | None:
        return await self.user_store.get_user_by_id(user_id)
