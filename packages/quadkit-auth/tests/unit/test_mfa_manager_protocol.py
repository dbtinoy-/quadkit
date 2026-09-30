"""Regression tests for MFAManager's MFAManagerProtocol conformance.

`MFAManagerProtocol` (quadkit.contracts.auth) declares a generic
enroll/verify/revoke/list_methods/get_mfa surface, and
`AuthProviderProtocol.mfa_manager` is typed as `MFAManagerProtocol | None`.
`AuthMiddleware`'s `require_mfa()` step-up decorator calls
`auth_provider.mfa_manager.get_mfa(user_id)` directly. Before this fix,
`MFAManager` only implemented the TOTP-specific `enable_totp`/`verify_totp`/
`disable_totp` trio and had no `get_mfa` (or `enroll`/`verify`/`revoke`/
`list_methods`) at all, so `require_mfa()` crashed with `AttributeError`
the first time it was exercised against a real, fully-wired
`AuthenticationProvider` (which now always attaches a real `MFAManager`
via `_attach_sibling_managers`, once the MFA sub-provider is registered).

These tests exercise the adapter methods directly against a real
`InMemoryUserStore`, and one end-to-end test drives `require_mfa()` itself
against a real booted `AuthBundleProvider` container to prove the
decorator no longer crashes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("pyotp")

import pyotp

from quadkit.auth.config import MFAConfig
from quadkit.auth.di.bundle_provider import AuthBundleProvider
from quadkit.auth.mfa.manager import MFAManager
from quadkit.auth.storage.token_store import InMemoryUserStore
from quadkit.auth.web.middleware.auth import require_mfa
from quadkit.contracts.auth import AuthProviderProtocol, MFAManagerProtocol
from quadkit.contracts.web import ResponseFactoryProtocol
from quadkit.di.container import Container


@pytest.fixture
def user_store() -> InMemoryUserStore:
    return InMemoryUserStore()


@pytest.fixture
def manager(user_store: InMemoryUserStore) -> MFAManager:
    return MFAManager(user_store=user_store, config=MFAConfig())


async def _make_user(user_store: InMemoryUserStore, email: str) -> Any:
    return await user_store.create_user(
        name=email.split("@", maxsplit=1)[0],
        email=email,
        hashed_password="hashed",
    )


class TestMFAManagerProtocolStructural:
    """MFAManager must structurally satisfy MFAManagerProtocol."""

    def test_isinstance_protocol(self, manager: MFAManager) -> None:
        assert isinstance(manager, MFAManagerProtocol)


class TestGetMfa:
    """get_mfa() — new adapter method, previously entirely missing."""

    @pytest.mark.asyncio
    async def test_get_mfa_unknown_user_returns_none(
        self, manager: MFAManager
    ) -> None:
        assert await manager.get_mfa("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_mfa_before_enrollment(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "nomfa@example.com")
        mfa = await manager.get_mfa(user.user_id)
        assert mfa is not None
        assert mfa.is_enabled is False
        assert mfa.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_get_mfa_after_enable_totp(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "withmfa@example.com")
        secret, _uri, _codes = await manager.enable_totp(user.user_id)

        mfa = await manager.get_mfa(user.user_id)
        assert mfa is not None
        assert mfa.is_enabled is True
        assert mfa.mfa_type == "totp"
        assert mfa.secret == secret

    @pytest.mark.asyncio
    async def test_get_mfa_after_disable(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "disabled@example.com")
        await manager.enable_totp(user.user_id)
        await manager.disable_totp(user.user_id)

        mfa = await manager.get_mfa(user.user_id)
        assert mfa is not None
        assert mfa.is_enabled is False


class TestEnrollVerifyRevokeListMethods:
    """The remaining MFAManagerProtocol adapter methods."""

    @pytest.mark.asyncio
    async def test_enroll_totp_returns_credentials(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "enroll@example.com")
        result = await manager.enroll(user.user_id, "totp")
        assert set(result.keys()) == {"secret", "provisioning_uri", "backup_codes"}
        assert len(result["backup_codes"]) > 0

    @pytest.mark.asyncio
    async def test_enroll_unsupported_method_raises(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "badmethod@example.com")
        with pytest.raises(ValueError, match="Unsupported MFA method"):
            await manager.enroll(user.user_id, "sms")

    @pytest.mark.asyncio
    async def test_verify_correct_totp_code(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "verify@example.com")
        enrolled = await manager.enroll(user.user_id, "totp")
        code = pyotp.TOTP(enrolled["secret"]).now()

        assert await manager.verify(user.user_id, "totp", code) is True

    @pytest.mark.asyncio
    async def test_verify_wrong_code_fails(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "verifywrong@example.com")
        await manager.enroll(user.user_id, "totp")

        assert await manager.verify(user.user_id, "totp", "000000") is False

    @pytest.mark.asyncio
    async def test_verify_unsupported_method_returns_false(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "verifyunsupported@example.com")
        assert await manager.verify(user.user_id, "sms", "123456") is False

    @pytest.mark.asyncio
    async def test_list_methods_empty_before_enrollment(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "listempty@example.com")
        assert await manager.list_methods(user.user_id) == []

    @pytest.mark.asyncio
    async def test_list_methods_after_enrollment(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "listfull@example.com")
        await manager.enroll(user.user_id, "totp")
        assert await manager.list_methods(user.user_id) == ["totp"]

    @pytest.mark.asyncio
    async def test_revoke_disables_totp(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "revoke@example.com")
        await manager.enroll(user.user_id, "totp")

        await manager.revoke(user.user_id, "totp")

        mfa = await manager.get_mfa(user.user_id)
        assert mfa is not None
        assert mfa.is_enabled is False

    @pytest.mark.asyncio
    async def test_revoke_unsupported_method_is_noop(
        self, manager: MFAManager, user_store: InMemoryUserStore
    ) -> None:
        user = await _make_user(user_store, "revokenoop@example.com")
        await manager.enroll(user.user_id, "totp")

        await manager.revoke(user.user_id, "sms")

        mfa = await manager.get_mfa(user.user_id)
        assert mfa is not None
        assert mfa.is_enabled is True  # unaffected


class _FakeState:
    def __init__(self, user: Any, session: Any) -> None:
        self.user = user
        self.session = session


class _FakeResponse:
    def __init__(self, status_code: int, content: Any) -> None:
        self.status_code = status_code
        self.content = content


class _FakeResponseFactory:
    """Minimal ResponseFactoryProtocol stand-in (no WebModule in these tests)."""

    def json(
        self,
        content: Any,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> _FakeResponse:
        return _FakeResponse(status_code, content)

    def html(
        self,
        content: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> _FakeResponse:
        return _FakeResponse(status_code, content)

    def redirect(
        self,
        url: str,
        status_code: int = 302,
        headers: dict[str, str] | None = None,
    ) -> _FakeResponse:
        return _FakeResponse(status_code, url)


class _FakeRequest:
    """Minimal stand-in satisfying AuthMiddleware's `_extract_request`."""

    def __init__(self, user: Any, session: Any) -> None:
        self.state = _FakeState(user, session)
        self.headers: dict[str, str] = {}
        self.container = None  # set by the test after boot


class TestRequireMfaDecoratorEndToEnd:
    """require_mfa() against a real booted AuthBundleProvider container.

    Reproduces the exact crash surfaced via examples/auth-mfa: before this
    fix, `auth_provider.mfa_manager.get_mfa(...)` raised AttributeError the
    moment a route protected by `@require_mfa()` was hit, because
    `MFAManager` had no `get_mfa` method.
    """

    @pytest.mark.asyncio
    async def test_require_mfa_blocks_unenrolled_user(self) -> None:
        container = Container()
        container.singleton(ResponseFactoryProtocol, instance=_FakeResponseFactory())
        provider = AuthBundleProvider()
        await provider.register(container)
        container.freeze()
        await provider.boot(container)

        from quadkit.di.resolution.context import current_resolver_var

        current_resolver_var.set(container)

        auth_provider = await container.resolve(AuthProviderProtocol)
        assert auth_provider.mfa_manager is not None

        user = await auth_provider.user_store.create_user(
            name="unenrolled",
            email="unenrolled@example.com",
            hashed_password="hashed",
        )

        @require_mfa()
        async def protected(request: Any) -> str:
            return "OK"

        request = _FakeRequest(user=user, session=None)
        request.container = container  # type: ignore[assignment]
        request.resolver = container  # type: ignore[attr-defined]

        result = await protected(request)
        assert getattr(result, "status_code", None) == 403

    @pytest.mark.asyncio
    async def test_require_mfa_allows_enrolled_and_stepped_up_user(self) -> None:
        container = Container()
        container.singleton(ResponseFactoryProtocol, instance=_FakeResponseFactory())
        provider = AuthBundleProvider()
        await provider.register(container)
        container.freeze()
        await provider.boot(container)

        from quadkit.di.resolution.context import current_resolver_var

        current_resolver_var.set(container)

        auth_provider = await container.resolve(AuthProviderProtocol)
        assert auth_provider.mfa_manager is not None

        user = await auth_provider.user_store.create_user(
            name="stepped-up",
            email="steppedup@example.com",
            hashed_password="hashed",
        )
        await auth_provider.mfa_manager.enable_totp(user.user_id)

        @require_mfa()
        async def protected(request: Any) -> str:
            return "OK"

        session = SimpleNamespace(mfa_verified_at=datetime.now(UTC))
        request = _FakeRequest(user=user, session=session)
        request.container = container  # type: ignore[assignment]
        request.resolver = container  # type: ignore[attr-defined]

        result = await protected(request)
        assert result == "OK"
