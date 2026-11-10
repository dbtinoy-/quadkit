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
        assert AuthIntegration._is_invocable_authenticator(
            OptionalRequestAuthenticator()
        )

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
        config = _FakeWebConfig()
        documentation = await AuthIntegration.configure(app, container, config)
        assert documentation.exclude_paths == tuple(config.auth_exclude_paths)
        assert documentation.responses_for("/private")["401"]["content"]
        assert documentation.responses_for(config.auth_exclude_paths[0]) == {}

        auth_mw = next(
            m
            for m in app.user_middleware
            if m.cls.__name__ == "AuthenticationMiddleware"
        )
        authenticators: list[Any] = auth_mw.kwargs["authenticators"]
        assert len(authenticators) == 2
        assert all(
            type(a) in (RequestAuthenticator, OptionalRequestAuthenticator)
            for a in authenticators
        )


@pytest.mark.parametrize("kind", ["empty", "incompatible", "lookup_failure"])
@pytest.mark.asyncio
async def test_enabled_auth_without_usable_authenticators_fails_startup(kind) -> None:
    from quadkit.contracts.exceptions.config import ConfigurationError

    class FailingContainer(_FakeContainer):
        async def resolve_all(self, service_type: Any) -> list[Any]:
            raise LookupError("private lookup detail")

    container = (
        FailingContainer([])
        if kind == "lookup_failure"
        else _FakeContainer([CredentialStore()] if kind == "incompatible" else [])
    )
    app = Starlette()
    with pytest.raises(
        ConfigurationError, match=r"requires.*AuthenticatorProtocol"
    ) as exc:
        await AuthIntegration.configure(app, container, _FakeWebConfig())
    assert "private lookup detail" not in str(exc.value)
    assert not any(
        m.cls.__name__ == "AuthenticationMiddleware" for m in app.user_middleware
    )


@pytest.mark.parametrize("kind", ["no_arguments", "required_keyword", "two_arguments"])
def test_signature_filter_refuses_callables_that_cannot_accept_request(kind) -> None:
    class NoArguments:
        async def authenticate(self):
            return None

    class RequiredKeyword:
        async def authenticate(self, request, *, api_key):
            return None

    candidates = {
        "no_arguments": NoArguments(),
        "required_keyword": RequiredKeyword(),
        "two_arguments": CredentialStore(),
    }
    assert not AuthIntegration._is_invocable_authenticator(candidates[kind])


def test_authenticator_with_uninspectable_signature_is_rejected() -> None:
    class UnknownSignature:
        @property
        def __signature__(self):
            raise ValueError("uninspectable")

        async def __call__(self, request):
            return None

    class UnknownAuthenticator:
        authenticate = UnknownSignature()

    assert not AuthIntegration._is_invocable_authenticator(UnknownAuthenticator())
