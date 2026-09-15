"""Tests for the in-memory repository (memory/repository.py)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from quadkit.testing.memory.repository import InMemoryRepository


@dataclass
class User:
    id: str
    name: str = ""
    active: bool = True


@pytest.fixture
def repo() -> InMemoryRepository[User]:
    return InMemoryRepository[User]()


async def _seed(repo: InMemoryRepository[User]) -> list[User]:
    users = [
        User(id="u1", name="Alice", active=True),
        User(id="u2", name="Bob", active=False),
        User(id="u3", name="Carol", active=True),
    ]
    return await repo.save_many(users)


class TestInMemoryRepository:
    @pytest.mark.asyncio
    async def test_save_and_get(self, repo) -> None:
        user = await repo.save(User(id="u1", name="Alice"))
        assert user.id == "u1"
        found = await repo.get("u1")
        assert found is user
        assert await repo.get("missing") is None

    @pytest.mark.asyncio
    async def test_save_upserts_by_id(self, repo) -> None:
        await repo.save(User(id="u1", name="Alice"))
        updated = await repo.save(User(id="u1", name="Alice B."))
        assert (await repo.get("u1")) is updated
        assert (await repo.get("u1")).name == "Alice B."
        assert await repo.count() == 1

    @pytest.mark.asyncio
    async def test_delete(self, repo) -> None:
        await repo.save(User(id="u1"))
        assert await repo.delete("u1") is True
        assert await repo.delete("u1") is False
        assert await repo.get("u1") is None

    @pytest.mark.asyncio
    async def test_exists(self, repo) -> None:
        await repo.save(User(id="u1"))
        assert await repo.exists("u1") is True
        assert await repo.exists("missing") is False

    @pytest.mark.asyncio
    async def test_list_without_filters(self, repo) -> None:
        await _seed(repo)
        items = await repo.list()
        assert [u.id for u in items] == ["u1", "u2", "u3"]

    @pytest.mark.asyncio
    async def test_list_with_skip_limit(self, repo) -> None:
        await _seed(repo)
        items = await repo.list(skip=1, limit=1)
        assert [u.id for u in items] == ["u2"]

    @pytest.mark.asyncio
    async def test_list_with_filters(self, repo) -> None:
        await _seed(repo)
        items = await repo.list(active=True)
        assert [u.id for u in items] == ["u1", "u3"]
        filtered = await repo.list(active=False, name="Bob")
        assert [u.id for u in filtered] == ["u2"]

    @pytest.mark.asyncio
    async def test_count_with_and_without_filters(self, repo) -> None:
        await _seed(repo)
        assert await repo.count() == 3
        assert await repo.count(active=True) == 2
        assert await repo.count(name="Nobody") == 0

    @pytest.mark.asyncio
    async def test_find_by_and_find_one_by(self, repo) -> None:
        await _seed(repo)
        matches = await repo.find_by(active=False)
        assert [u.id for u in matches] == ["u2"]
        one = await repo.find_one_by(name="Carol")
        assert one is not None
        assert one.id == "u3"
        assert await repo.find_one_by(name="Nobody") is None

    @pytest.mark.asyncio
    async def test_find_by_spec(self, repo) -> None:
        await _seed(repo)

        class ActiveSpec:
            def is_satisfied_by(self, entity: Any) -> bool:
                return entity.active

        items = await repo.find_by_spec(ActiveSpec())
        assert [u.id for u in items] == ["u1", "u3"]

    @pytest.mark.asyncio
    async def test_find_by_filter_and_query_are_noop_mocks(self, repo) -> None:
        await _seed(repo)
        assert await repo.find_by_filter(object()) == []
        assert await repo.find_by_query("SELECT *") == []

    @pytest.mark.asyncio
    async def test_save_many_returns_same_list(self, repo) -> None:
        users = await _seed(repo)
        assert await repo.count() == 3
        assert users == await repo.list()

    @pytest.mark.asyncio
    async def test_delete_many(self, repo) -> None:
        await _seed(repo)
        removed = await repo.delete_many(["u1", "u3", "missing"])
        assert removed == 2
        assert [u.id for u in await repo.list()] == ["u2"]

    @pytest.mark.asyncio
    async def test_custom_id_attr(self) -> None:
        # A repository keyed on a different attribute must key on it.
        keyed: InMemoryRepository[User] = InMemoryRepository(id_attr="name")
        await keyed.save(User(id="x", name="Alice"))
        assert await keyed.get("Alice") is not None
        assert await keyed.get("x") is None

    @pytest.mark.asyncio
    async def test_post_save_and_post_delete_hooks(self, repo) -> None:
        saved: list[Any] = []
        deleted: list[Any] = []

        async def on_save(entity: Any) -> None:
            saved.append(entity)

        async def on_delete(entity_id: Any) -> None:
            deleted.append(entity_id)

        repo.register_post_save_hook(on_save)
        repo.register_post_delete_hook(on_delete)

        user = await repo.save(User(id="u1", name="Alice"))
        assert saved == [user]
        await repo.delete("u1")
        assert deleted == ["u1"]
        # Hooks must not fire when delete finds nothing.
        await repo.delete("missing")
        assert deleted == ["u1"]
