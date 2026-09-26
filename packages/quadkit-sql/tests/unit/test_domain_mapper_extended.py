from dataclasses import dataclass
from datetime import date, datetime, time
from uuid import UUID

from quadkit.domain import DomainModel
import pytest

from quadkit.sql.mappers.base import MappingError
from quadkit.sql.mappers.domain_mapper import DomainDataMapper


@dataclass
class UserModel(DomainModel):
    id: int
    name: str
    created_at: datetime | None = None
    birthday: date | None = None
    wake_time: time | None = None
    tags: list[str] | None = None
    meta: dict | None = None
    uuid: UUID | None = None


@pytest.mark.asyncio
async def test_to_entity_and_parsing():
    mapper = DomainDataMapper(UserModel)

    row = {
        "id": 1,
        "name": "Alice",
        "created_at": "2020-01-01T12:00:00+00:00",
        "birthday": "1990-05-20",
        "wake_time": "07:30:00",
        "tags": ["a", "b"],
        "meta": {"k": "v"},
        "uuid": "12345678-1234-5678-1234-567812345678",
        "extra_column": "should_be_mapped_when_auto_map",
    }

    entity = mapper.to_entity(row)

    assert entity.id == 1
    assert entity.name == "Alice"
    assert isinstance(entity.created_at, datetime)
    assert isinstance(entity.birthday, date)
    assert isinstance(entity.wake_time, time)
    assert isinstance(entity.tags, list)
    assert isinstance(entity.meta, dict)
    assert isinstance(entity.uuid, UUID)


def test_to_entity_missing_required_field_raises():
    mapper = DomainDataMapper(UserModel)

    row = {"id": 1}

    with pytest.raises(MappingError):
        mapper.to_entity(row)


def test_to_entity_invalid_datetime_raises_mapping_error():
    mapper = DomainDataMapper(UserModel)

    row = {"id": 1, "name": "Bob", "created_at": "not-a-date"}

    with pytest.raises(MappingError):
        mapper.to_entity(row)


def test_to_row_and_type_serialization():
    mapper = DomainDataMapper(UserModel)

    entity = UserModel(
        id=2,
        name="Carol",
        created_at=datetime(2021, 6, 1, 8, 30),
        birthday=date(1985, 7, 7),
        wake_time=time(6, 15),
        tags=["x", "y"],
        meta={"n": 1},
    )

    row = mapper.to_row(entity)

    # datetime/date/time should be ISO strings
    assert isinstance(row["created_at"], str)
    assert isinstance(row["birthday"], str)
    assert isinstance(row["wake_time"], str)

    # list/dict may be serialized to strings depending on converter availability
    assert isinstance(row["tags"], (str, list))
    assert isinstance(row["meta"], (str, dict))


def test_to_row_missing_required_raises():
    mapper = DomainDataMapper(UserModel)

    # Create a model with required field None to trigger error
    entity = UserModel(id=3, name="D")

    # Manually set a required field mapping to required to simulate
    # (fields are required by default in model)
    # Using to_row should work because fields are present; test required None scenario
    entity.name = None

    with pytest.raises(MappingError):
        mapper.to_row(entity)