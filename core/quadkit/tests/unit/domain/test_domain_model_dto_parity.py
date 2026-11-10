"""Unit tests for DomainModel EmailStr validation, Field(alias=...), and from_attributes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import SimpleNamespace
from typing import Any

import pytest

from quadkit.contracts.exceptions import ValidationError
from quadkit.domain import DomainModel
from quadkit.validation import (
    AliasChoices,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


@dataclass(init=False, eq=False, kw_only=True)
class _SyncDTO(DomainModel):
    user_id: str
    email: EmailStr


@dataclass(init=False, eq=False, kw_only=True)
class _AliasedDTO(DomainModel):
    pet_id: str = Field(alias="petId")
    payload: dict[str, Any]


@dataclass(init=False, eq=False, kw_only=True)
class _FromAttrsDTO(DomainModel):
    model_config = ConfigDict(from_attributes=True)
    email: EmailStr
    display_name: str | None = None


def test_domain_model_validates_email_str() -> None:
    """DomainModel rejects malformed EmailStr values with ValidationError."""
    ok = _SyncDTO(user_id="u-1", email="pet@owner.com")
    assert ok.email == "pet@owner.com"

    with pytest.raises(ValidationError):
        _SyncDTO(user_id="u-1", email="not-an-email")


def test_domain_model_supports_field_alias() -> None:
    """DomainModel accepts both declared field names and Field(alias=...) keys."""
    via_alias = _AliasedDTO.model_validate({"petId": "p-9", "payload": {"k": 1}})
    assert via_alias.pet_id == "p-9"
    assert via_alias.payload == {"k": 1}

    via_name = _AliasedDTO(pet_id="p-10", payload={"k": 2})
    assert via_name.pet_id == "p-10"


def test_domain_model_supports_from_attributes() -> None:
    """DomainModel.model_validate hydrates attribute-bearing objects when from_attributes=True."""
    entity = SimpleNamespace(email="vet@clinic.org", display_name="Dr. Bark")
    dto = _FromAttrsDTO.model_validate(entity)
    assert dto.email == "vet@clinic.org"
    assert dto.display_name == "Dr. Bark"


class _Urgency(StrEnum):
    LOW = "low"
    EMERGENCY = "emergency"


@dataclass(init=False, eq=False, kw_only=True)
class _SubItem(DomainModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    note: str | None = None


@dataclass(init=False, eq=False, kw_only=True)
class _RichDomainEntity(DomainModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        use_enum_values=True,
    )
    pet_type_id: str
    urgency: _Urgency = _Urgency.LOW
    should_escalate: bool = False
    confidence: float | None = Field(
        default=None,
        validation_alias=AliasChoices("confidence", "confidence_score"),
    )
    items: list[_SubItem] = Field(default_factory=list)

    @computed_field
    def species(self) -> str:
        return self.pet_type_id.replace("_", " ").title()

    @model_validator(mode="before")
    @classmethod
    def _map_orm(cls, values: Any) -> Any:
        if (
            isinstance(values, dict)
            and "raw_type" in values
            and "pet_type_id" not in values
        ):
            values["pet_type_id"] = values["raw_type"]
        return values

    @field_validator("should_escalate", mode="after")
    @classmethod
    def _force_escalate(cls, v: bool, info: Any) -> bool:
        if info.data.get("urgency") == _Urgency.EMERGENCY.value:
            return True
        return v


def test_domain_model_computed_field_alias_choices_exclude_none_and_schema() -> None:
    """DomainModel supports AliasChoices, @computed_field, 3-arg after validators, exclude_none, and nested JSON schema."""
    orm_obj = SimpleNamespace(
        raw_type="golden_retriever",
        urgency=_Urgency.EMERGENCY,
        confidence_score=0.92,
        items=[{"label": "xray", "unknown_extra": 123}],
        unmapped_db_col="ignored",
    )
    ent = _RichDomainEntity.model_validate(orm_obj)
    assert ent.species == "Golden Retriever"
    assert ent.urgency == "emergency"
    assert ent.should_escalate is True
    assert ent.confidence == 0.92
    assert ent.model_extra is None

    dumped = ent.model_dump(exclude_none=True)
    assert dumped["species"] == "Golden Retriever"
    assert dumped["items"] == [{"label": "xray"}]
    assert "unmapped_db_col" not in dumped

    schema = _RichDomainEntity.model_json_schema()
    assert schema["properties"]["urgency"]["enum"] == ["low", "emergency"]
    assert schema["properties"]["items"]["type"] == "array"
    assert schema["properties"]["items"]["items"]["type"] == "object"
