"""Tests for ObjectMapperImpl and MappingRegistry behaviors."""

from __future__ import annotations

import dataclasses

import pytest

from quadkit.mapping import MappingRegistry, ObjectMapperImpl


@dataclasses.dataclass
class Address:
    street: str
    city: str


@dataclasses.dataclass
class UserDTO:
    name: str
    address: Address


@dataclasses.dataclass
class Person:
    name: str
    address: Address


def test_mapping_registry_basic():
    reg = MappingRegistry()

    def to_str(x: int) -> str:
        return str(x)

    reg.register(int, str, to_str)
    assert reg.has(int, str)
    assert reg.get(int, str)(123) == "123"

    with pytest.raises(ValueError):
        reg.register(int, str, to_str)

    assert reg.unregister(int, str) is None
    assert not reg.has(int, str)


def test_auto_map_nested():
    mapper = ObjectMapperImpl()
    dto = UserDTO(name="Alice", address=Address(street="1st", city="NY"))
    # converting to Person should auto-map the nested Address
    p = mapper.auto_map(dto, Person)
    assert isinstance(p, Person)
    assert p.name == "Alice"
    assert isinstance(p.address, Address)
    assert p.address.city == "NY"
