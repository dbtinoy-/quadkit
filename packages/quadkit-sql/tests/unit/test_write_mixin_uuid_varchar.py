"""Unit tests for _WriteMixin UUID-to-VARCHAR column type coercion."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from quadkit.domain import DomainModel
from quadkit.sql.repositories.generic_repository import GenericRepository


@dataclass(init=False, eq=False, kw_only=True)
class _VarcharMediaRow(DomainModel):
    id: UUID
    key: str
    user_id: UUID | None = None


def _mock_provider_with_columns(col_defs: list[dict[str, Any]]) -> Any:
    provider = AsyncMock()
    provider.dialect = "postgresql"
    provider.get_table_columns = AsyncMock(return_value=col_defs)
    provider.execute_insert = AsyncMock(
        return_value=SimpleNamespace(success=True, inserted_id=None, affected_rows=1)
    )
    provider.execute_update = AsyncMock(
        return_value=SimpleNamespace(success=True, affected_rows=1)
    )
    provider.execute_query = AsyncMock(
        return_value=SimpleNamespace(success=True, rows=[], row_count=1)
    )
    return provider


@pytest.mark.asyncio
async def test_write_mixin_coerces_uuid_to_str_for_varchar_columns() -> None:
    """UUID fields are coerced to str on VARCHAR/TEXT columns across create/update/upsert."""
    provider = _mock_provider_with_columns(
        [
            {"name": "id", "type": "character varying"},
            {"name": "key", "type": "character varying(1024)"},
            {"name": "user_id", "type": "text"},
        ]
    )
    repo: GenericRepository[_VarcharMediaRow, UUID] = GenericRepository(
        provider,
        "media_assets",
        _VarcharMediaRow,
    )

    media_id = uuid4()
    owner_id = uuid4()

    await repo.create(
        {"id": str(media_id), "key": "tmp/a.png", "user_id": str(owner_id)}
    )
    insert_payload = provider.execute_insert.call_args.args[1]
    assert insert_payload["id"] == str(media_id)
    assert isinstance(insert_payload["id"], str)
    assert insert_payload["user_id"] == str(owner_id)
    assert isinstance(insert_payload["user_id"], str)

    entity = _VarcharMediaRow(id=media_id, key="tmp/b.png", user_id=owner_id)
    await repo.update(entity)
    update_payload = provider.execute_update.call_args.args[1]
    assert update_payload["user_id"] == str(owner_id)
    assert isinstance(update_payload["user_id"], str)

    await repo.upsert(entity)
    upsert_params = provider.execute_query.call_args.args[1]
    assert all(not isinstance(param, UUID) for param in upsert_params)


@pytest.mark.asyncio
async def test_write_mixin_preserves_native_uuid_for_uuid_columns() -> None:
    """Native UUID columns retain uuid.UUID values without stringification."""
    provider = _mock_provider_with_columns(
        [
            {"name": "id", "type": "uuid"},
            {"name": "key", "type": "character varying"},
            {"name": "user_id", "type": "uuid"},
        ]
    )
    repo: GenericRepository[_VarcharMediaRow, UUID] = GenericRepository(
        provider,
        "pet_images",
        _VarcharMediaRow,
    )

    media_id = uuid4()
    owner_id = uuid4()
    await repo.create({"id": media_id, "key": "pets/1.png", "user_id": owner_id})
    insert_payload = provider.execute_insert.call_args.args[1]
    assert isinstance(insert_payload["id"], UUID)
    assert isinstance(insert_payload["user_id"], UUID)
