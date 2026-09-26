"""Fail-closed tenant enforcement on the write path (create)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from quadkit.sql.context import create_db_context
from quadkit.sql.context.keys import TENANT_ID
from quadkit.sql.exceptions import TenantScopingError
from quadkit.sql.repositories.base import SQLRepository


class _DocRepo(SQLRepository[dict, str]):
    def _entity_to_dict(self, entity: dict) -> dict[str, object]:
        return dict(entity)

    def _row_to_entity(self, row: dict[str, object]) -> dict:
        return dict(row)


def _make_repo(db_ctx: object | None) -> _DocRepo:
    result = SimpleNamespace(success=True, inserted_id="1")
    provider = SimpleNamespace(execute_insert=AsyncMock(return_value=result))
    return _DocRepo(provider=provider, table_name="docs", multi_tenant=True, db_ctx=db_ctx)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_backfills_tenant_from_db_context() -> None:
    db_ctx = create_db_context()
    token = db_ctx.set(TENANT_ID, "tenant-abc")
    repo = _make_repo(db_ctx=db_ctx)
    await repo.create({"title": "x"})
    _, persisted = repo.provider.execute_insert.call_args.args
    assert persisted["tenant_id"] == "tenant-abc"
    db_ctx.reset(TENANT_ID, token)


@pytest.mark.asyncio
async def test_create_rejects_mismatched_client_tenant() -> None:
    db_ctx = create_db_context()
    token = db_ctx.set(TENANT_ID, "tenant-abc")
    repo = _make_repo(db_ctx=db_ctx)
    with pytest.raises(TenantScopingError, match="INSERT"):
        await repo.create({"title": "x", "tenant_id": "tenant-evil"})
    db_ctx.reset(TENANT_ID, token)


@pytest.mark.asyncio
async def test_create_raises_when_no_tenant_active() -> None:
    db_ctx = create_db_context()  # no tenant set
    repo = _make_repo(db_ctx=db_ctx)
    with pytest.raises(TenantScopingError, match="INSERT"):
        await repo.create({"title": "x"})
    with pytest.raises(TenantScopingError, match="INSERT"):
        await repo.create({"title": "x", "tenant_id": "tenant-evil"})