"""SQLUserStore against a real SQLite database (no mocks).

The mock-based suite pins call shapes; this pins that the store
actually persists: it creates its own table, honours a custom table
name, rejects non-identifier names, keeps the InMemory uniqueness
contract, and survives a provider restart against the same file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.auth.exceptions import EmailExistsError, UsernameExistsError
from quadkit.auth.storage._sql_store import SQLUserStore
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


async def _provider(path: str = ":memory:") -> SQLiteProvider:
    provider = SQLiteProvider(path)
    await provider.connect()
    return provider


@pytest.mark.asyncio
async def test_round_trip_default_table() -> None:
    provider = await _provider()
    try:
        store = SQLUserStore(provider)
        assert not store.initialized

        user = await store.create_user(
            name="Ada",
            email="ada@example.com",
            hashed_password="hash-1",
            roles=["user"],
            permissions=["notes:read"],
            profile={"bio": "first"},
        )
        assert store.initialized

        by_id = await store.get_user_by_id(user.user_id)
        assert by_id is not None
        assert by_id.email == "ada@example.com"
        assert by_id.roles == ["user"]
        assert by_id.permissions == ["notes:read"]
        assert by_id.profile == {"bio": "first"}

        by_email = await store.get_user_by_email("ada@example.com")
        assert by_email is not None
        assert by_email.user_id == user.user_id

        creds = await store.get_credentials(user.user_id)
        assert creds is not None
        assert creds.hashed_password == "hash-1"

        creds.hashed_password = "hash-2"
        creds.previous_hashes = ["hash-1"]
        await store.update_credentials(creds)
        rotated = await store.get_credentials(user.user_id)
        assert rotated is not None
        assert rotated.hashed_password == "hash-2"
        assert rotated.previous_hashes == ["hash-1"]

        by_id.name = "Ada Lovelace"
        by_id.login_count = 3
        await store.update_user(by_id)
        updated = await store.get_user_by_id(user.user_id)
        assert updated is not None
        assert updated.name == "Ada Lovelace"
        assert updated.login_count == 3

        assert await store.count_users() == 1
        assert [u.user_id for u in await store.list_users()] == [user.user_id]

        await store.delete_user(user.user_id)
        assert await store.get_user_by_id(user.user_id) is None
        assert await store.count_users() == 0
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
async def test_custom_table_name() -> None:
    provider = await _provider()
    try:
        store = SQLUserStore(provider, table_name="app_users")
        await store.create_user(
            name="Ben", email="ben@example.com", hashed_password="h"
        )

        assert await provider.table_exists("app_users")
        assert not await provider.table_exists("users")
        found = await store.get_user_by_email("ben@example.com")
        assert found is not None
        assert found.name == "Ben"
    finally:
        await provider.disconnect()


@pytest.mark.parametrize(
    "bad_name",
    ["", "1users", "user table", "users; DROP TABLE users", 'users"x'],
)
def test_invalid_table_name_rejected(bad_name: str) -> None:
    with pytest.raises(ValueError, match="Invalid users table name"):
        SQLUserStore(object(), table_name=bad_name)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_uniqueness_contract_matches_in_memory() -> None:
    provider = await _provider()
    try:
        store = SQLUserStore(provider)
        await store.create_user(
            name="Ada", email="ada@example.com", hashed_password="h"
        )
        with pytest.raises(UsernameExistsError, match="Name 'Ada' already exists"):
            await store.create_user(
                name="Ada", email="other@example.com", hashed_password="h"
            )
        with pytest.raises(
            EmailExistsError, match=r"Email 'ada@example\.com' already exists"
        ):
            await store.create_user(
                name="Other", email="ada@example.com", hashed_password="h"
            )
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
async def test_persists_across_provider_restart(tmp_path: Path) -> None:
    db_file = str(tmp_path / "identity.db")

    first = await _provider(db_file)
    store = SQLUserStore(first)
    created = await store.create_user(
        name="Ada", email="ada@example.com", hashed_password="hash-1",
        roles=["user"],
    )
    await first.disconnect()

    second = await _provider(db_file)
    try:
        reopened = SQLUserStore(second)
        found = await reopened.get_user_by_email("ada@example.com")
        assert found is not None
        assert found.user_id == created.user_id
        assert found.roles == ["user"]
        creds = await reopened.get_credentials(created.user_id)
        assert creds is not None
        assert creds.hashed_password == "hash-1"
    finally:
        await second.disconnect()


@pytest.mark.asyncio
async def test_initialize_is_idempotent() -> None:
    provider = await _provider()
    try:
        store = SQLUserStore(provider)
        await store.initialize()
        await store.initialize()
        assert store.initialized
        await store.create_user(
            name="Ada", email="ada@example.com", hashed_password="h"
        )
        assert await store.count_users() == 1
    finally:
        await provider.disconnect()
