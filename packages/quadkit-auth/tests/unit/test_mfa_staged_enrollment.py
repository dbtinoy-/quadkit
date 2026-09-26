"""Tests for staged TOTP enrollment used by Gatewai's new-api parity routes."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from quadkit.auth.authn.mfa import generate_totp_code
from quadkit.auth.mfa.manager import MFAManager


@dataclass
class _User:
    user_id: str
    name: str
    email: str
    profile: dict[str, object] = field(default_factory=dict)


class _Store:
    def __init__(self, user: _User) -> None:
        self.user = user

    async def get_user_by_id(self, user_id: str) -> _User | None:
        return self.user if user_id == self.user.user_id else None

    async def update_user(self, user: _User) -> None:
        self.user = user


@pytest.mark.asyncio
async def test_staged_totp_enrollment_only_enables_after_code() -> None:
    store = _Store(_User("u1", "Alice", "alice@example.test"))
    manager = MFAManager(store)

    setup = await manager.begin_totp_setup("u1")
    assert setup["setup_token"]
    assert store.user.profile == {}

    backup_codes = await manager.complete_totp_setup(
        "u1",
        str(setup["setup_token"]),
        generate_totp_code(str(setup["secret"])),
    )
    assert backup_codes == setup["backup_codes"]
    assert store.user.profile["mfa"]["enabled"] is True  # type: ignore[index]


@pytest.mark.asyncio
async def test_staged_totp_enrollment_consumes_invalid_token() -> None:
    store = _Store(_User("u2", "Bob", "bob@example.test"))
    manager = MFAManager(store)
    setup = await manager.begin_totp_setup("u2")

    assert await manager.complete_totp_setup("u2", str(setup["setup_token"]), "000000") is None
    assert await manager.complete_totp_setup(
        "u2",
        str(setup["setup_token"]),
        generate_totp_code(str(setup["secret"])),
    ) is None
    assert store.user.profile == {}
