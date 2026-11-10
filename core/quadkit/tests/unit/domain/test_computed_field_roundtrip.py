"""Regression tests for read-only @property / @computed_field round-tripping on DomainModel."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.domain import DomainModel
from quadkit.validation import ConfigDict, computed_field


@dataclass(init=False, eq=False, kw_only=True)
class BreedWithComputedSpecies(DomainModel):
    """DomainModel mirroring a downstream Breed model with a @computed_field property."""

    model_config = ConfigDict(extra="allow", from_attributes=True)

    id: str
    pet_type_id: str
    name: str

    @computed_field
    @property
    def species(self) -> str:
        return self.pet_type_id


@dataclass(init=False, eq=False, kw_only=True)
class ModelWithWritableProperty(DomainModel):
    """DomainModel with a property that defines a setter."""

    model_config = ConfigDict(extra="allow")

    id: str
    _tag: str = ""

    @property
    def tag(self) -> str:
        return self._tag

    @tag.setter
    def tag(self, value: str) -> None:
        self._tag = value.upper()


def test_computed_field_round_trips_through_model_dump_and_validate() -> None:
    """model_dump() emits @computed_field keys; model_validate() must skip read-only properties."""
    breed = BreedWithComputedSpecies(
        id="dog_golden_retriever",
        pet_type_id="dog",
        name="Golden Retriever",
    )
    dumped = breed.model_dump()
    assert dumped["species"] == "dog"

    rehydrated = BreedWithComputedSpecies.model_validate(dumped)
    assert isinstance(rehydrated, BreedWithComputedSpecies)
    assert rehydrated.id == "dog_golden_retriever"
    assert rehydrated.species == "dog"


def test_writable_property_setter_is_still_invoked_on_extra_keys() -> None:
    """Properties that define fset continue to accept extra-key assignment."""
    item = ModelWithWritableProperty.model_validate({"id": "1", "tag": "featured"})
    assert item.tag == "FEATURED"
