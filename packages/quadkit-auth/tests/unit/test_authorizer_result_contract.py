"""Authorizer contracts and boolean permission consumers must agree on grants."""

from types import SimpleNamespace
from typing import get_type_hints
from unittest.mock import AsyncMock

import pytest

from quadkit.auth.authz.service import AuthorizationService
from quadkit.contracts.auth.guard import AuthorizerProtocol
from quadkit.contracts.core.result import Err, Ok, Result
from quadkit.contracts.exceptions import AuthorizationError


def test_authorize_contract_uses_canonical_result() -> None:
    assert (
        get_type_hints(AuthorizerProtocol.authorize)["return"]
        == Result[bool, AuthorizationError]
    )


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (Ok(True), True),
        (Ok(False), False),
        (Err(AuthorizationError()), False),
        (Ok(1), False),
        (Ok("yes"), False),
        (Ok(None), False),
    ],
)
async def test_can_requires_exact_true_payload(monkeypatch, decision, expected) -> None:
    service = AuthorizationService()
    monkeypatch.setattr(service, "authorize", AsyncMock(return_value=decision))
    assert await service.can(object(), "read", "posts") is expected


async def test_real_service_denial_is_successful_decision_not_grant() -> None:
    service = AuthorizationService()
    principal = SimpleNamespace(user_id="reader", permissions=[])
    decision = await service.authorize(principal, "read", "posts")
    assert decision.is_ok()  # Evaluation succeeded, but permission was denied.
    assert decision.unwrap() is False
    assert await service.can(principal, "read", "posts") is False


async def test_can_does_not_swallow_infrastructure_error(monkeypatch) -> None:
    service = AuthorizationService()
    monkeypatch.setattr(
        service, "authorize", AsyncMock(side_effect=RuntimeError("offline"))
    )
    with pytest.raises(RuntimeError, match="offline"):
        await service.can(object(), "read", "posts")
