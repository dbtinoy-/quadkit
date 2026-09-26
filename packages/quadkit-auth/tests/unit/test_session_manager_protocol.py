"""Regression tests for the auth `SessionManagerImpl` protocol binding.

`SessionProvider.register()` used to bind `SessionManagerImpl` (the
device-aware login-session manager — `create_session`, `validate_session`,
`revoke_session`, `verify_mfa`, `revoke_all_sessions`, `get_active_sessions`)
against `quadkit.contracts.ai.session.SessionManagerProtocol`, which is an
entirely different, AI-conversation-session contract (`create`, `resume`,
`add_turn`, `get_state`, `checkpoint`, `restore`, `close`, `suspend`).

`SessionManagerImpl` never satisfied that protocol, so the registration
bypassed the container's own protocol-conformance guard with
`validate=False` instead of surfacing the mismatch. Anything resolving the
exported protocol type would have received an object missing every method
the type claimed to provide.

The fix introduces `quadkit.contracts.auth.protocols.AuthSessionManagerProtocol`
— a protocol that actually matches `SessionManagerImpl`'s real surface — and
binds against that instead, with normal (non-bypassed) validation.
"""

from __future__ import annotations

import pytest

from quadkit.auth.di.sub_providers.session_provider import SessionProvider
from quadkit.auth.session.manager import SessionManagerImpl
from quadkit.contracts.ai.session import (
    SessionManagerProtocol as AISessionManagerProtocol,
)
from quadkit.contracts.auth import AuthSessionManagerProtocol
from quadkit.di.container import Container


class TestAuthSessionManagerProtocolConformance:
    """SessionManagerImpl must structurally satisfy AuthSessionManagerProtocol."""

    def test_isinstance_protocol(self) -> None:
        manager = SessionManagerImpl()
        assert isinstance(manager, AuthSessionManagerProtocol)

    def test_does_not_satisfy_unrelated_ai_session_protocol(self) -> None:
        """Guards against ever re-introducing the original bug: the AI
        conversation-session protocol has a disjoint method surface
        (create/resume/add_turn/checkpoint/restore/suspend) and
        SessionManagerImpl must not be mistaken for an implementation of it.
        """
        manager = SessionManagerImpl()
        assert not isinstance(manager, AISessionManagerProtocol)


class TestSessionProviderRegistration:
    """SessionProvider must register against the correct protocol, validated."""

    @pytest.mark.asyncio
    async def test_registers_auth_session_manager_protocol(self) -> None:
        container = Container()
        provider = SessionProvider(config=None)

        await provider.register(container)

        resolved = await container.resolve(AuthSessionManagerProtocol)
        assert isinstance(resolved, SessionManagerImpl)

    @pytest.mark.asyncio
    async def test_registration_passes_real_protocol_validation(self) -> None:
        """Registration must succeed under normal (non-bypassed) validation.

        Previously this binding only worked because `validate=False`
        suppressed the container's protocol-conformance check; with the
        correct protocol in place, validation should pass on its own merits.
        """
        container = Container()
        provider = SessionProvider(config=None)

        # Should not raise RegistrationError / ProtocolValidationError.
        await provider.register(container)

    @pytest.mark.asyncio
    async def test_resolved_manager_exposes_login_session_api(self) -> None:
        container = Container()
        provider = SessionProvider(config=None)
        await provider.register(container)

        manager = await container.resolve(AuthSessionManagerProtocol)
        session = await manager.create_session("user-1", {"ua": "pytest"})
        assert session.user_id == "user-1"

        active = await manager.get_active_sessions("user-1")
        assert any(s.session_id == session.session_id for s in active)
