"""Fail-closed tenancy enforcement on the read path and construction."""

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


def _make_repo(*, db_ctx: object | None) -> _DocRepo:
    provider = SimpleNamespace(execute_query=AsyncMock())
    return _DocRepo(provider=provider, table_name="docs", multi_tenant=True, db_ctx=db_ctx)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_select_without_active_tenant_raises() -> None:
    db_ctx = create_db_context()  # no tenant set
    repo = _make_repo(db_ctx=db_ctx)
    with pytest.raises(TenantScopingError, match="SELECT"):
        await repo._apply_filters_to_query("SELECT * FROM docs", [], {})


@pytest.mark.asyncio
async def test_select_with_active_tenant_filters() -> None:
    db_ctx = create_db_context()
    token = db_ctx.set(TENANT_ID, "tenant-abc")
    repo = _make_repo(db_ctx=db_ctx)
    params: list[object] = []
    query = await repo._apply_filters_to_query("SELECT * FROM docs", params, {})
    assert "tenant_id = ?" in query
    assert "tenant-abc" in params
    db_ctx.reset(TENANT_ID, token)


def test_multi_tenant_requires_db_ctx() -> None:
    with pytest.raises(ValueError, match="multi_tenant=True requires db_ctx"):
        _make_repo(db_ctx=None)


@pytest.mark.asyncio
async def test_with_tenant_scope_filters_then_restores() -> None:
    db_ctx = create_db_context()
    repo = _make_repo(db_ctx=db_ctx)
    assert db_ctx.tenant_id is None
    async with repo.with_tenant_scope("tenant-abc"):
        params: list[object] = []
        query = await repo._apply_filters_to_query("SELECT * FROM docs", params, {})
        assert "tenant_id = ?" in query
        assert "tenant-abc" in params
    assert db_ctx.tenant_id is None
