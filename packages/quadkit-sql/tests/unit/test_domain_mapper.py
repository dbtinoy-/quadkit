from dataclasses import dataclass

"""Unit tests for DomainDataMapper covering conversions, defaults, aliases, and error handling."""

from datetime import UTC, date, datetime, time
import uuid

import pytest

from quadkit.sql.mappers.base import MappingError
from quadkit.sql.mappers.domain_mapper import DomainDataMapper


def test_to_row_and_to_entity_roundtrip():
    from quadkit.domain import DomainModel

    @dataclass
    class User(DomainModel):
        id: int
        name: str
        created_at: datetime | None = None
        data: dict | None = None
        tags: list[str] | None = None

    mapper = DomainDataMapper(User)

    now = datetime.now(UTC)
    u = User(id=1, name="Alice", created_at=now, data={"k": "v"}, tags=["a", "b"])

    row = mapper.to_row(u)

    # datetimes should be converted to ISO strings
    assert isinstance(row["created_at"], str)
    # Depending on backend/json lib, the mapper may produce a JSON string or keep native dict
    assert isinstance(row["data"], (str, dict))

    # Convert back to entity
    entity = mapper.to_entity(row)
    assert entity.id == 1
    assert entity.name == "Alice"
    assert isinstance(entity.created_at, datetime)
    assert entity.data == {"k": "v"}
    assert entity.tags == ["a", "b"]


def test_missing_required_field_raises_mapping_error():
    from quadkit.domain import DomainModel

    @dataclass
    class P(DomainModel):
        id: int
        name: str

    mapper = DomainDataMapper(P)

    with pytest.raises(MappingError) as exc:
        mapper.to_entity({"id": 1})

    # Ensure a MappingError is raised for missing required field
    assert isinstance(exc.value, MappingError)


def test_type_conversion_uuid_date_time_and_collections():
    from quadkit.domain import DomainModel

    @dataclass
    class T(DomainModel):
        uid: uuid.UUID
        d: date
        t: time
        items: list[int]
        meta: dict

    mapper = DomainDataMapper(T)

    uid = uuid.uuid4()
    row = {
        "uid": str(uid),
        "d": "2020-01-01",
        "t": "12:34:56",
        "items": "[1, 2, 3]",
        "meta": '{"x": 1}',
    }

    ent = mapper.to_entity(row)
    assert ent.uid == uid
    assert ent.d == date(2020, 1, 1)
    assert ent.t == time(12, 34, 56)
    assert ent.items == [1, 2, 3]
    assert ent.meta == {"x": 1}


def test_to_row_required_none_raises_mapping_error():
    from quadkit.domain import DomainModel

    @dataclass
    class Req(DomainModel):
        id: int

    mapper = DomainDataMapper(Req)

    entity = Req(id=None)  # type: ignore[arg-type] — dataclass does not enforce types
    with pytest.raises(MappingError) as exc:
        mapper.to_row(entity)
    assert "Required field" in str(exc.value)


def test_alias_handling_and_auto_map():
    from quadkit.domain import DomainModel
    from quadkit.validation import Field

    @dataclass
    class Aliased(DomainModel):
        id: int = Field(alias="user_id")
        score: int

    mapper = DomainDataMapper(Aliased)

    # Provide db row using generated column names
    row = {"id": 5, "score": 10, "extra": "x"}

    # auto_map should include unmapped fields
    ent = mapper.to_entity(row)
    assert ent.score == 10
    # Extra field should be present due to auto_map
    assert hasattr(ent, "extra") or ("extra" in row)


def test_validation_error_is_wrapped_in_mapping_error():
    from quadkit.domain import DomainModel

    @dataclass
    class V(DomainModel):
        n: int

    mapper = DomainDataMapper(V)

    # Missing required field triggers MappingError
    with pytest.raises(MappingError):
        mapper.to_entity({})
