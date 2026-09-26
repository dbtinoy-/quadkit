from dataclasses import dataclass
#!/usr/bin/env python3
"""Simple test script for the entity mapping system."""

import pytest

from quadkit.sql.mappers.base import FieldMapping, MappingError
from quadkit.sql.mappers import DomainDataMapper


def test_field_mapping():
    """Test FieldMapping basic functionality."""
    mapping = FieldMapping("test_field", "test_column")
    assert mapping.convert_to_entity("value") == "value"
    assert mapping.convert_to_db("value") == "value"


def test_mapping_error():
    """Test MappingError."""
    error = MappingError("test error", "TestEntity", "test_field", "test_value")
    assert (
        str(error)
        == "MappingError(test error, entity_type=TestEntity, field=test_field, value=test_value)"
    )


def test_domain_mapper():
    """Test DomainDataMapper basic functionality."""
    from quadkit.domain import DomainModel

    @dataclass
    class TestEntity(DomainModel):
        id: int
        name: str

    mapper = DomainDataMapper(TestEntity)

    # Test basic mapping
    row = {"id": 1, "name": "Test"}
    entity = mapper.to_entity(row)
    assert entity.id == 1
    assert entity.name == "Test"

    # Test reverse mapping
    row_back = mapper.to_row(entity)
    assert row_back["id"] == 1
    assert row_back["name"] == "Test"