"""Tests for integrations/auth.py — AuthIntegration authenticator filtering."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.applications import Starlette

from quadkit.web.integrations.auth import AuthIntegration


class RequestAuthenticator:
    """A real AuthenticatorProtocol implementation."""

    async def authenticate(self, request: Any) -> Any | None:
        return None


class CredentialStore:
    """Structurally similar but signature-incompatible (admin user store)."""

    async def authenticate(self, email: str, password: str) -> Any | None:
        return None


class OptionalRequestAuthenticator:
    async def authenticate(self, request: Any = None) -> Any | None:
        return None


class _FakeContainer:
    def __init__(self, candidates: list[Any]) -> None:
        self._candidates = candidates

    async def resolve(self, service_type: Any) -> Any:
        raise LookupError("not registered")

    async def resolve_optional(self, service_type: Any) -> Any | None:
        return None

    async def resolve_all(self, service_type: Any) -> list[Any]:
        return self._candidates


class _FakeWebConfig:
    auth_exclude_paths = ["/health"]
    enable_identity_resolution = False


class TestIsInvocableAuthenticator:
    def test_request_authenticator_accepted(self) -> None:
        assert AuthIntegration._is_invocable_authenticator(RequestAuthenticator())

    def test_store_with_credentials_rejected(self) -> None:
        """A store with authenticate(email, password) must not be treated as an authenticator."""
        assert not AuthIntegration._is_invocable_authenticator(CredentialStore())

    def test_optional_request_accepted(self) -> None:
        assert AuthIntegration._is_invocable_authenticator(OptionalRequestAuthenticator())

    def test_missing_authenticate_rejected(self) -> None:
        class NoMethod:
            pass

        assert not AuthIntegration._is_invocable_authenticator(NoMethod())


class TestAuthIntegrationConfigure:
    @pytest.mark.asyncio
    async def test_incompatible_candidates_filtered_out(self) -> None:
        container = _FakeContainer(
            [RequestAuthenticator(), CredentialStore(), OptionalRequestAuthenticator()]
        )
        app = Starlette()
        await AuthIntegration.configure(app, container, _FakeWebConfig())

        auth_mw = next(
            m for m in app.user_middleware if m.cls.__name__ == "AuthenticationMiddleware"
        )
        authenticators: list[Any] = auth_mw.kwargs["authenticators"]
        assert len(authenticators) == 2
        assert all(
            type(a) in (RequestAuthenticator, OptionalRequestAuthenticator)
            for a in authenticators
        )
