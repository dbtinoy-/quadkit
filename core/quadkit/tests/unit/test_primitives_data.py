"""Tests for primitives/data.py — Abstract repository and mapper classes."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.primitives.data import (
    AbstractReadOnlyRepository,
    AbstractRepository,
    DataMapper,
    ReadOnlyMapper,
)


class MockEntity:
    """Mock entity for testing."""

    def __init__(self, id: str, name: str = "test") -> None:
        self.id = id
        self.name = name


class TestAbstractReadOnlyRepository:
    """Tests for AbstractReadOnlyRepository."""

    def test_is_abstract(self) -> None:
        """Test AbstractReadOnlyRepository is abstract."""

        with pytest.raises(TypeError):
            AbstractReadOnlyRepository()

    @pytest.mark.asyncio
    async def test_get_delegates_to_fetch_by_id(self) -> None:
        """Test get() calls _fetch_by_id."""

        class TestRepo(AbstractReadOnlyRepository[MockEntity, str]):
            async def _fetch_by_id(self, entity_id: Any) -> MockEntity | None:
                return MockEntity(id=str(entity_id))

            async def _fetch_many(
                self, *, skip: int, limit: int, filters: dict[str, Any]
            ) -> list[MockEntity]:
                return []

            async def _count(self, *, filters: dict[str, Any]) -> int:
                return 0

            async def find_by_spec(self, spec: Any) -> list[MockEntity]:
                return []

        repo = TestRepo()
        result = await repo.get("123")
        assert result is not None
        assert result.id == "123"

    @pytest.mark.asyncio
    async def test_list_delegates_to_fetch_many(self) -> None:
        """Test list() calls _fetch_many."""

        class TestRepo(AbstractReadOnlyRepository[MockEntity, str]):
            async def _fetch_by_id(self, entity_id: Any) -> MockEntity | None:
                return None

            async def _fetch_many(
                self, *, skip: int, limit: int, filters: dict[str, Any]
            ) -> list[MockEntity]:
                return [MockEntity(id="1"), MockEntity(id="2")]

            async def _count(self, *, filters: dict[str, Any]) -> int:
                return 2

            async def find_by_spec(self, spec: Any) -> list[MockEntity]:
                return []

        repo = TestRepo()
        result = await repo.list(skip=0, limit=10)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_count_delegates_to_count(self) -> None:
        """Test count() calls _count."""

        class TestRepo(AbstractReadOnlyRepository[MockEntity, str]):
            async def _fetch_by_id(self, entity_id: Any) -> MockEntity | None:
                return None

            async def _fetch_many(
                self, *, skip: int, limit: int, filters: dict[str, Any]
            ) -> list[MockEntity]:
                return []

            async def _count(self, *, filters: dict[str, Any]) -> int:
                return 42

            async def find_by_spec(self, spec: Any) -> list[MockEntity]:
                return []

        repo = TestRepo()
        result = await repo.count()
        assert result == 42


class TestAbstractRepository:
    """Tests for AbstractRepository."""

    def test_is_abstract(self) -> None:
        """Test AbstractRepository is abstract."""

        with pytest.raises(TypeError):
            AbstractRepository()

    @pytest.mark.asyncio
    async def test_save_calls_save_and_hooks(self) -> None:
        """Test save() calls _save and post-save hooks."""

        class TestRepo(AbstractRepository[MockEntity, str]):
            async def _fetch_by_id(self, entity_id: Any) -> MockEntity | None:
                return None

            async def _fetch_many(
                self, *, skip: int, limit: int, filters: dict[str, Any]
            ) -> list[MockEntity]:
                return []

            async def _count(self, *, filters: dict[str, Any]) -> int:
                return 0

            async def find_by_spec(self, spec: Any) -> list[MockEntity]:
                return []

            async def _save(self, entity: MockEntity) -> MockEntity:
                entity.name = "saved"
                return entity

            async def _delete(self, entity_id: Any) -> bool:
                return True

        repo = TestRepo()
        hook = AsyncMock()
        repo.register_post_save_hook(hook)

        entity = MockEntity(id="123", name="original")
        result = await repo.save(entity)

        assert result.name == "saved"
        hook.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_delete_calls_delete_and_hooks(self) -> None:
        """Test delete() calls _delete and post-delete hooks."""

        class TestRepo(AbstractRepository[MockEntity, str]):
            async def _fetch_by_id(self, entity_id: Any) -> MockEntity | None:
                return None

            async def _fetch_many(
                self, *, skip: int, limit: int, filters: dict[str, Any]
            ) -> list[MockEntity]:
                return []

            async def _count(self, *, filters: dict[str, Any]) -> int:
                return 0

            async def find_by_spec(self, spec: Any) -> list[MockEntity]:
                return []

            async def _save(self, entity: MockEntity) -> MockEntity:
                return entity

            async def _delete(self, entity_id: Any) -> bool:
                return True

        repo = TestRepo()
        hook = AsyncMock()
        repo.register_post_delete_hook(hook)

        result = await repo.delete("123")

        assert result is True
        hook.assert_awaited_once_with("123")

    @pytest.mark.asyncio
    async def test_delete_skips_hooks_on_failure(self) -> None:
        """Test delete() skips hooks when delete returns False."""

        class TestRepo(AbstractRepository[MockEntity, str]):
            async def _fetch_by_id(self, entity_id: Any) -> MockEntity | None:
                return None

            async def _fetch_many(
                self, *, skip: int, limit: int, filters: dict[str, Any]
            ) -> list[MockEntity]:
                return []

            async def _count(self, *, filters: dict[str, Any]) -> int:
                return 0

            async def find_by_spec(self, spec: Any) -> list[MockEntity]:
                return []

            async def _save(self, entity: MockEntity) -> MockEntity:
                return entity

            async def _delete(self, entity_id: Any) -> bool:
                return False

        repo = TestRepo()
        hook = AsyncMock()
        repo.register_post_delete_hook(hook)

        result = await repo.delete("123")

        assert result is False
        hook.assert_not_called()


class TestReadOnlyMapper:
    """Tests for ReadOnlyMapper."""

    @pytest.mark.asyncio
    async def test_to_target_batch_default_implementation(self) -> None:
        """Test to_target_batch uses to_target by default."""

        class TestMapper(ReadOnlyMapper[str, int]):
            async def to_target(self, source: str) -> int:
                return int(source)

        mapper = TestMapper()
        result = await mapper.to_target_batch(["1", "2", "3"])
        assert result == [1, 2, 3]


class TestDataMapper:
    """Tests for DataMapper."""

    @pytest.mark.asyncio
    async def test_to_source_batch_default_implementation(self) -> None:
        """Test to_source_batch uses to_source by default."""

        class TestMapper(DataMapper[str, int]):
            async def to_target(self, source: str) -> int:
                return int(source)

            async def to_source(self, target: int) -> str:
                return str(target)

        mapper = TestMapper()
        result = await mapper.to_source_batch([1, 2, 3])
        assert result == ["1", "2", "3"]
