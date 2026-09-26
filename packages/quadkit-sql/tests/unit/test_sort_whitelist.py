"""Repository sort-identifier safety tests (F5)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.contracts.data import InvalidIdentifierError
from quadkit.sql.exceptions import RepositoryError
from quadkit.sql.repositories.base import SQLRepository
from quadkit.sql.specification import RawSpecification

PAYLOAD = "id; DROP TABLE users;--"


class _Entity:
    def __init__(self, _id: int, name: str) -> None:
        self.id = _id
        self.name = name


@pytest.fixture
def mock_provider() -> Mock:
    provider = Mock()
    provider.execute_query = AsyncMock(
        return_value=Mock(success=True, rows=[], error_message="")
    )
    provider.execute_insert = AsyncMock()
    provider.execute_update = AsyncMock()
    provider.execute_delete = AsyncMock()
    return provider


@pytest.fixture
def repository(mock_provider: Mock) -> SQLRepository[_Entity, int]:
    class ConcreteRepository(SQLRepository[_Entity, int]):
        def _entity_to_dict(self, entity: _Entity) -> dict[str, Any]:
            return {"id": entity.id, "name": entity.name}

        def _row_to_entity(self, row: dict[str, Any]) -> _Entity:
            return _Entity(row["id"], row.get("name", ""))

    return ConcreteRepository(mock_provider, "test_entities", "id")


@pytest.mark.asyncio
async def test_find_many_rejects_payload_sort(
    repository: SQLRepository[_Entity, int],
) -> None:
    """find_many() raises for a sort_by that breaks out of ORDER BY."""
    with pytest.raises(InvalidIdentifierError):
        await repository.find_many(sort_by=PAYLOAD)


@pytest.mark.asyncio
async def test_find_many_rejects_whitelist_violation(
    repository: SQLRepository[_Entity, int],
    mock_provider: Mock,
) -> None:
    """find_many() raises RepositoryError when sort_by is not whitelisted."""
    with pytest.raises(RepositoryError, match="not allowed"):
        await repository.find_many(
            sort_by="created_at",
            allowed_sort_fields=["name"],
        )
    assert not mock_provider.execute_query.await_count


@pytest.mark.asyncio
async def test_find_many_whitelisted_sort_builds_quoted_order_by(
    repository: SQLRepository[_Entity, int],
    mock_provider: Mock,
) -> None:
    """A whitelisted sort renders a quoted ORDER BY column."""
    await repository.find_many(
        sort_by="name",
        allowed_sort_fields=["name"],
        sort_order="desc",
    )
    query = mock_provider.execute_query.call_args.args[0]
    assert query.rstrip().endswith('ORDER BY "name" DESC')


@pytest.mark.asyncio
async def test_find_by_spec_rejects_payload_sort(
    repository: SQLRepository[_Entity, int],
) -> None:
    """find_by_spec() raises for a payload sort_by."""
    with pytest.raises(InvalidIdentifierError):
        await repository.find_by_spec(RawSpecification("1 = 1"), sort_by=PAYLOAD)


@pytest.mark.asyncio
async def test_paginate_cursor_rejects_payload_sort(
    repository: SQLRepository[_Entity, int],
) -> None:
    """paginate_cursor() raises for a payload sort_by."""
    with pytest.raises(InvalidIdentifierError):
        await repository.paginate_cursor(sort_by=PAYLOAD)
