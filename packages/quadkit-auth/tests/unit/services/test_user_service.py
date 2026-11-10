"""UserService.create_user duplicate-contract tests.

Stores are the uniqueness authority for name and email; the service
must surface their typed conflicts as ``Err`` values — distinctly,
never collapsed into one another and never raised bare.
"""

from __future__ import annotations

import pytest

from quadkit.auth.authn.security import PasswordPolicy
from quadkit.auth.authn.user_service import UserService
from quadkit.auth.exceptions import EmailExistsError, UsernameExistsError
from quadkit.auth.storage.token_store import InMemoryUserStore


@pytest.fixture
def service() -> UserService:
    return UserService(
        password_policy=PasswordPolicy(),
        user_store=InMemoryUserStore(),
    )


@pytest.mark.asyncio
async def test_create_user_success(service: UserService) -> None:
    result = await service.create_user("alice", "alice@example.com", "Secure!Pass42")
    assert result.is_ok()
    assert result.unwrap().email == "alice@example.com"


@pytest.mark.asyncio
async def test_create_user_duplicate_email(service: UserService) -> None:
    first = await service.create_user("alice", "alice@example.com", "Secure!Pass42")
    assert first.is_ok()

    result = await service.create_user("alice2", "alice@example.com", "Secure!Pass42")
    assert result.is_err()
    assert isinstance(result.unwrap_err(), EmailExistsError)


@pytest.mark.asyncio
async def test_create_user_duplicate_name(service: UserService) -> None:
    first = await service.create_user("alice", "alice@example.com", "Secure!Pass42")
    assert first.is_ok()

    result = await service.create_user("alice", "other@example.com", "Secure!Pass42")
    assert result.is_err()
    assert isinstance(result.unwrap_err(), UsernameExistsError)
