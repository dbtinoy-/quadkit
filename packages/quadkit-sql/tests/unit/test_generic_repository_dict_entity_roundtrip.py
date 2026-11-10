"""Regression tests for GenericRepository dict -> TEntity hydration and JSONB codecs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from quadkit.contracts.data import (
    DatabaseProviderProtocol,
    InsertResult,
    QueryResult,
    UpdateResult,
)
from quadkit.domain import DomainModel
from quadkit.sql import DatabaseConfig, DatabaseService
from quadkit.sql.providers.postgres_provider import _decode_jsonb, _encode_jsonb
from quadkit.sql.repositories.generic_repository import GenericRepository


@dataclass(init=False, eq=False, kw_only=True)
class _ScoreEntity(DomainModel):
    id: str
    pet_id: str
    score: float


@dataclass(init=False, eq=False, kw_only=True)
class _UuidDefaultEntity(DomainModel):
    id: UUID = field(default_factory=uuid4)
    label: str
    created_at: Any = None
    updated_at: Any = None


@pytest.mark.asyncio
async def test_generic_repository_create_with_dict_returns_typed_entity() -> None:
    """GenericRepository.create(dict) converts the inserted dict into entity_class."""
    provider = Mock(spec=DatabaseProviderProtocol)
    provider.get_table_columns = AsyncMock(
        return_value=frozenset({"id", "pet_id", "score"})
    )
    provider.execute_insert = AsyncMock(return_value=InsertResult("s1", 1, 0.001, True))
    repo: GenericRepository[_ScoreEntity, str] = GenericRepository(
        provider=provider,
        table_name="wellness_scores",
        entity_class=_ScoreEntity,
    )

    created = await repo.create({"id": "s1", "pet_id": "p1", "score": 88.5})
    assert isinstance(created, _ScoreEntity)
    assert created.pet_id == "p1"
    assert created.score == 88.5


@pytest.mark.asyncio
async def test_generic_repository_partial_dict_update_falls_back_to_find_by_id() -> (
    None
):
    """Partial dict updates missing required entity fields re-fetch via find_by_id."""
    provider = Mock(spec=DatabaseProviderProtocol)
    provider.get_table_columns = AsyncMock(
        return_value=frozenset({"id", "pet_id", "score"})
    )
    provider.execute_update = AsyncMock(return_value=UpdateResult(1, 0.001, True))
    provider.execute_query = AsyncMock(
        return_value=QueryResult(
            rows=[{"id": "s1", "pet_id": "p1", "score": 92.0}],
            row_count=1,
            execution_time=0.001,
            success=True,
        )
    )
    repo: GenericRepository[_ScoreEntity, str] = GenericRepository(
        provider=provider,
        table_name="wellness_scores",
        entity_class=_ScoreEntity,
    )

    updated = await repo.update({"id": "s1", "score": 92.0})
    assert isinstance(updated, _ScoreEntity)
    assert updated.id == "s1"
    assert updated.pet_id == "p1"
    assert updated.score == 92.0


@pytest.mark.asyncio
async def test_generic_repository_dict_entity_class_preserves_dict_return() -> None:
    """When entity_class is dict, create() preserves raw dict return semantics."""
    provider = Mock(spec=DatabaseProviderProtocol)
    provider.get_table_columns = AsyncMock(return_value=frozenset({"id", "score"}))
    provider.execute_insert = AsyncMock(return_value=InsertResult("s2", 1, 0.001, True))
    repo: GenericRepository[dict[str, Any], str] = GenericRepository(
        provider=provider,
        table_name="wellness_scores",
        entity_class=dict,
    )

    created = await repo.create({"id": "s2", "score": 77.0})
    assert isinstance(created, dict)
    assert created["score"] == 77.0


def test_postgres_jsonb_codec_avoids_double_encoding_json_strings() -> None:
    """_encode_jsonb/_decode_jsonb preserve dicts, lists, and pre-serialized JSON strings."""
    assert _encode_jsonb({"a": 1}) == '{"a":1}'
    assert _encode_jsonb('{"a": 1}') == '{"a": 1}'
    assert _encode_jsonb("[1, 2]") == "[1, 2]"
    assert _encode_jsonb("plain-string") == '"plain-string"'

    assert _decode_jsonb('{"a": 1}') == {"a": 1}
    assert _decode_jsonb('"{\\"a\\": 1}"') == {"a": 1}
    assert _decode_jsonb('"[\\"x\\", \\"y\\"]"') == ["x", "y"]
    assert _decode_jsonb('"plain"') == "plain"


@pytest.mark.asyncio
async def test_database_service_delegates_get_table_columns_for_append_only_table() -> (
    None
):
    """DatabaseService exposes get_table_columns so append-only tables skip updated_at."""
    svc = DatabaseService(DatabaseConfig.from_url("sqlite:///:memory:"))
    svc.db_provider = Mock()
    svc.db_provider.get_table_columns = AsyncMock(
        return_value=[
            {"name": "id", "type": "uuid"},
            {"name": "label", "type": "text"},
            {"name": "created_at", "type": "timestamp without time zone"},
        ]
    )
    inserted_rows: list[dict[str, Any]] = []

    async def _capture_insert(_table: str, data: dict[str, Any]) -> InsertResult:
        inserted_rows.append(dict(data))
        return InsertResult(data.get("id"), 1, 0.001, True)

    svc.db_provider.execute_insert = AsyncMock(side_effect=_capture_insert)

    repo: GenericRepository[_UuidDefaultEntity, UUID] = GenericRepository(
        provider=svc,
        table_name="community_shares",
        entity_class=_UuidDefaultEntity,
    )
    created = await repo.create({"label": "copy_link"})
    assert isinstance(created, _UuidDefaultEntity)
    assert len(inserted_rows) == 1
    assert str(inserted_rows[0]["id"]) == str(created.id)
    assert "created_at" in inserted_rows[0]
    assert inserted_rows[0]["created_at"].tzinfo is None
    assert "updated_at" not in inserted_rows[0]


@dataclass(init=False, eq=False, kw_only=True)
class _ColumnAliasedGoal(DomainModel):
    id: UUID = field(default_factory=uuid4)
    goal_type: str
    title: str


@pytest.mark.asyncio
async def test_generic_repository_create_filters_db_column_mapped_dict_to_table_columns() -> (
    None
):
    """DB-column-mapped dict payloads filter model_dump keys against table_columns()."""
    from quadkit.validation import model_validator

    @dataclass(init=False, eq=False, kw_only=True)
    class _MappedGoal(DomainModel):
        id: UUID = field(default_factory=uuid4)
        goal_type: str
        title: str

        @model_validator(mode="before")
        @classmethod
        def _map_cols(cls, values: Any) -> Any:
            if not isinstance(values, dict):
                return values
            mapped = dict(values)
            if "type" in mapped and "goal_type" not in mapped:
                mapped["goal_type"] = mapped["type"]
            return mapped

    cols = [
        {"name": "id", "type": "uuid"},
        {"name": "type", "type": "varchar"},
        {"name": "title", "type": "varchar"},
    ]
    provider = Mock(spec=DatabaseProviderProtocol)
    provider.get_table_columns = AsyncMock(return_value=cols)
    inserted_rows: list[dict[str, Any]] = []

    async def _capture_insert(_table: str, data: dict[str, Any]) -> InsertResult:
        inserted_rows.append(dict(data))
        return InsertResult(data.get("id"), 1, 0.001, True)

    provider.execute_insert = AsyncMock(side_effect=_capture_insert)
    repo: GenericRepository[_MappedGoal, UUID] = GenericRepository(
        provider=provider,
        table_name="wellness_goals",
        entity_class=_MappedGoal,
    )
    caller_payload = {"type": "exercise", "title": "Evening walk"}
    created = await repo.create(caller_payload)
    assert caller_payload == {"type": "exercise", "title": "Evening walk"}
    assert isinstance(created, _MappedGoal)
    assert created.goal_type == "exercise"
    assert len(inserted_rows) == 1
    assert inserted_rows[0]["type"] == "exercise"
    assert "goal_type" not in inserted_rows[0]
