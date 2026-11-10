"""Unit tests for PostgreSQL ARRAY vs JSON list parameter binding in PostgresProvider."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.sql import QueryResult
from quadkit.sql.providers.postgres_provider import PostgresProvider


@asynccontextmanager
async def _fake_get_conn() -> Any:
    yield MagicMock()


@pytest.mark.asyncio
async def test_postgres_insert_binds_native_list_for_array_and_json_for_text() -> None:
    """DR-31: PostgreSQL ARRAY columns receive Python lists; non-ARRAY lists stay JSON text."""
    provider = PostgresProvider("postgresql://postgres:@127.0.0.1:5432/testdb")
    info_mock = AsyncMock(
        return_value=QueryResult(
            rows=[{"name": "facility_tags"}],
            row_count=1,
            execution_time=0.0,
            success=True,
        )
    )
    exec_query = AsyncMock(return_value=[{"id": "vet-1"}])

    with (
        patch.object(provider.connection_manager, "get_connection", _fake_get_conn),
        patch.object(provider, "execute_query", info_mock),
        patch.object(provider.query_executor, "execute_query", exec_query),
    ):
        res = await provider.execute_insert(
            "veterinary_care",
            {
                "name": "Makati Vet",
                "facility_tags": ["emergency", "surgery"],
                "extra_labels": ["a", "b"],
            },
        )
        assert res.success is True
        assert res.inserted_id == "vet-1"

        # Second insert hits cached _array_columns_cache without re-querying information_schema
        await provider.execute_insert(
            "veterinary_care",
            {
                "name": "Cebu Vet",
                "facility_tags": [],
                "extra_labels": [],
            },
        )

    assert info_mock.await_count == 1
    assert exec_query.await_args_list[0].args[2] == [
        "Makati Vet",
        ["emergency", "surgery"],
        '["a","b"]',
    ]
    assert exec_query.await_args_list[1].args[2] == ["Cebu Vet", [], "[]"]


@pytest.mark.asyncio
async def test_postgres_update_binds_native_list_for_array_and_json_for_other() -> None:
    """DR-31: PostgreSQL execute_update preserves native Python lists on ARRAY columns."""
    provider = PostgresProvider("postgresql://postgres:@127.0.0.1:5432/testdb")
    info_mock = AsyncMock(
        return_value=QueryResult(
            rows=[{"name": "facility_tags"}],
            row_count=1,
            execution_time=0.0,
            success=True,
        )
    )
    exec_modify = AsyncMock(return_value=1)

    with (
        patch.object(provider.connection_manager, "get_connection", _fake_get_conn),
        patch.object(provider, "execute_query", info_mock),
        patch.object(provider.query_executor, "execute_modify", exec_modify),
    ):
        res = await provider.execute_update(
            "veterinary_care",
            {
                "facility_tags": ["diagnostics"],
                "scopes_json": ["read", "write"],
            },
            '"id" = ?',
            ["vet-1"],
        )

    assert res.success is True
    assert res.affected_rows == 1
    assert exec_modify.await_args_list[0].args[2] == [
        ["diagnostics"],
        '["read","write"]',
        "vet-1",
    ]


@pytest.mark.asyncio
async def test_postgres_insert_extracts_non_id_pk_after_nullable_omitted_columns() -> (
    None
):
    """PostgresProvider.execute_insert skips None RETURNING columns and prefers generated *_id PK."""
    provider = PostgresProvider("postgresql://postgres:@127.0.0.1:5432/testdb")
    exec_query = AsyncMock(
        return_value=[
            {
                "email": None,
                "full_name": None,
                "user_id": "guest-uuid-001",
                "display_name": "Coral Whisker",
            }
        ]
    )

    with (
        patch.object(provider.connection_manager, "get_connection", _fake_get_conn),
        patch.object(provider.query_executor, "execute_query", exec_query),
    ):
        res = await provider.execute_insert(
            "users",
            {
                "display_name": "Coral Whisker",
                "is_guest": True,
                "guest_fingerprint": "fp" * 20,
            },
        )

    assert res.success is True
    assert res.inserted_id == "guest-uuid-001"
