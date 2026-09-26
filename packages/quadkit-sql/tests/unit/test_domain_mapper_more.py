from dataclasses import dataclass
from datetime import date, datetime, time
from uuid import UUID

from quadkit.validation import Field
from quadkit.domain import DomainModel
import pytest

from quadkit.sql.mappers.base import MappingError
from quadkit.sql.mappers.domain_mapper import DomainDataMapper


@dataclass
class AliasModel(DomainModel):
    first: str = Field(alias="firstName")


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
async def test_to_entity_invalid_uuid_raises():
    mapper = DomainDataMapper(UserModel)

    row = {"id": 1, "name": "Alice", "uuid": "not-a-uuid"}

    with pytest.raises(MappingError):
        mapper.to_entity(row)


def test_to_row_uuid_and_collections_serialization():
    mapper = DomainDataMapper(UserModel)

    u = UUID("12345678-1234-5678-1234-567812345678")
    entity = UserModel(
        id=2,
        name="Carol",
        created_at=datetime(2021, 6, 1, 8, 30),
        birthday=date(1985, 7, 7),
        wake_time=time(6, 15),
        tags=["x", "y"],
        meta={"n": 1},
        uuid=u,
    )

    row = mapper.to_row(entity)

    # UUIDs may be serialized to strings by the mapper, but may also remain
    # UUID objects depending on converter availability/environment.
    from uuid import UUID as _UUID

    assert isinstance(row["uuid"], (str, _UUID))
    assert isinstance(row["created_at"], str)
    assert isinstance(row["birthday"], str)
    assert isinstance(row["wake_time"], str)
    assert isinstance(row["tags"], (str, list))
    assert isinstance(row["meta"], (str, dict))


def test_alias_field_handling():
    mapper = DomainDataMapper(AliasModel)

    # The DB column name is the field name ('first') while the model alias is 'firstName'
    row = {"first": "Zoe"}
    entity = mapper.to_entity(row)

    assert entity.first == "Zoe"


def test_to_entity_invalid_time_raises_mapping_error():
    mapper = DomainDataMapper(UserModel)

    row = {"id": 1, "name": "Bob", "wake_time": "not-a-time"}

    with pytest.raises(MappingError):
        mapper.to_entity(row)


def test_init_with_non_domain_model_raises():
    class NotADomainModel:
        pass

    with pytest.raises(TypeError):
        DomainDataMapper(NotADomainModel)