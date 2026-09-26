"""Cost-parameter upgrade-on-login tests (F1)."""

from __future__ import annotations

import bcrypt
import pytest

from quadkit.auth.authn.security import PasswordHasher


@pytest.mark.asyncio
async def test_needs_rehash_false_for_current_cost() -> None:
    hasher = PasswordHasher(rounds=12)
    hashed = await hasher.hash("correcthorse")
    assert hasher.needs_rehash(hashed) is False


@pytest.mark.asyncio
async def test_needs_rehash_true_for_lower_cost() -> None:
    stored = bcrypt.hashpw(b"correcthorse", bcrypt.gensalt(rounds=4)).decode("ascii")
    assert PasswordHasher(rounds=12).needs_rehash(stored) is True


@pytest.mark.asyncio
async def test_rehash_upgrades_hash_after_verify() -> None:
    stored = bcrypt.hashpw(b"correcthorse", bcrypt.gensalt(rounds=4)).decode("ascii")
    hasher = PasswordHasher(rounds=12)
    assert await hasher.verify("correcthorse", stored)
    new_hash = await hasher.rehash_if_needed("correcthorse", stored)
    assert new_hash is not None
    assert new_hash != stored
    assert new_hash.split("$")[2] == "12"


@pytest.mark.asyncio
async def test_unparseable_hash_is_fail_closed_rehash() -> None:
    hasher = PasswordHasher(rounds=12)
    assert hasher.needs_rehash("not-a-valid-hash-format") is True
