from dataclasses import dataclass
"""Tests for the entity mapping system."""

from datetime import date, datetime, time
from typing import TYPE_CHECKING, cast
from typing import Any as _Any
from uuid import UUID, uuid4

import pytest

if TYPE_CHECKING:
    from quadkit.validation import Field
    from quadkit.domain import DomainModel

    PYDANTIC_AVAILABLE = True
else:
    try:
        from quadkit.validation import Field
        from quadkit.domain import DomainModel

        PYDANTIC_AVAILABLE = True
    except ImportError:
        PYDANTIC_AVAILABLE = False
        DomainModel = _Any
        Field = cast(_Any, lambda **kwargs: None)


from quadkit.sql.mappers.base import FieldMapping, MappingError
from quadkit.sql.mappers import DomainDataMapper


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestDomainDataMapper:
    """Test the Domain data mapper."""

    def test_basic_mapping(self):
        """Test basic entity to row and row to entity mapping."""

        @dataclass
        class User(DomainModel):
            id: int
            name: str
            email: str
            age: int | None = None

        mapper = DomainDataMapper(User)

        # Test row to entity
        row = {"id": 1, "name": "John Doe", "email": "john@example.com", "age": 30}

        user = mapper.to_entity(row)
        assert user.id == 1
        assert user.name == "John Doe"
        assert user.email == "john@example.com"
        assert user.age == 30

        # Test entity to row
        row_back = mapper.to_row(user)
        assert row_back["id"] == 1
        assert row_back["name"] == "John Doe"
        assert row_back["email"] == "john@example.com"
        assert row_back["age"] == 30

    def test_datetime_mapping(self):
        """Test datetime field mapping."""

        @dataclass
        class Event(DomainModel):
            id: int
            name: str
            created_at: datetime
            event_date: date | None = None
            event_time: time | None = None

        mapper = DomainDataMapper(Event)

        created_at = datetime(2023, 1, 1, 12, 0, 0)
        event_date = date(2023, 12, 25)
        event_time = time(15, 30, 0)

        row = {
            "id": 1,
            "name": "Test Event",
            "created_at": created_at.isoformat(),
            "event_date": event_date.isoformat(),
            "event_time": event_time.isoformat(),
        }

        event = mapper.to_entity(row)
        assert event.created_at == created_at
        assert event.event_date == event_date
        assert event.event_time == event_time

        # Test round trip
        row_back = mapper.to_row(event)
        assert row_back["created_at"] == created_at.isoformat()
        assert row_back["event_date"] == event_date.isoformat()
        assert row_back["event_time"] == event_time.isoformat()

    def test_uuid_mapping(self):
        """Test UUID field mapping."""

        @dataclass
        class Document(DomainModel):
            id: UUID
            title: str

        mapper = DomainDataMapper(Document)

        doc_id = uuid4()
        row = {"id": str(doc_id), "title": "Test Document"}

        doc = mapper.to_entity(row)
        assert doc.id == doc_id
        assert doc.title == "Test Document"

        # Test round trip
        row_back = mapper.to_row(doc)
        assert row_back["id"] == str(doc_id)
        assert row_back["title"] == "Test Document"

    def test_json_mapping(self):
        """Test JSON field mapping."""

        @dataclass
        class Config(DomainModel):
            id: int
            settings: dict
            tags: list[str]

        mapper = DomainDataMapper(Config)

        settings = {"theme": "dark", "notifications": True}
        tags = ["important", "urgent"]

        row = {
            "id": 1,
            "settings": '{"theme": "dark", "notifications": true}',
            "tags": '["important", "urgent"]',
        }

        config = mapper.to_entity(row)
        assert config.settings == settings
        assert config.tags == tags

        # Test round trip
        row_back = mapper.to_row(config)
        assert row_back["settings"] == '{"theme":"dark","notifications":true}'
        assert row_back["tags"] == '["important","urgent"]'

    def test_custom_field_mapping(self):
        """Test custom field mappings."""

        @dataclass
        class User(DomainModel):
            user_id: int = Field(alias="id")
            full_name: str = Field(alias="name")
            email_address: str

        # Custom mapping for email_address
        field_mappings = [
            FieldMapping("user_id", "user_id"),
            FieldMapping("full_name", "full_name"),
            FieldMapping("email_address", "email_addr"),
        ]

        mapper = DomainDataMapper(User, field_mappings=field_mappings, auto_map=False)

        row = {"user_id": 1, "full_name": "John Doe", "email_addr": "john@example.com"}

        user = mapper.to_entity(row)
        assert user.user_id == 1
        assert user.full_name == "John Doe"
        assert user.email_address == "john@example.com"

    def test_column_prefix_suffix(self):
        """Test column prefix and suffix."""

        @dataclass
        class User(DomainModel):
            id: int
            name: str

        mapper = DomainDataMapper(User, column_prefix="user_", column_suffix="_col")

        row = {"user_id_col": 1, "user_name_col": "John"}

        user = mapper.to_entity(row)
        assert user.id == 1
        assert user.name == "John"

        row_back = mapper.to_row(user)
        assert "user_id_col" in row_back
        assert "user_name_col" in row_back

    def test_bulk_operations(self):
        """Test bulk entity/row operations."""

        @dataclass
        class User(DomainModel):
            id: int
            name: str

        mapper = DomainDataMapper(User)

        rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
        ]

        # Test to_entities
        users = mapper.to_entities(rows)
        assert len(users) == 3
        assert users[0].name == "Alice"
        assert users[1].name == "Bob"
        assert users[2].name == "Charlie"

        # Test to_rows
        rows_back = mapper.to_rows(users)
        assert len(rows_back) == 3
        assert rows_back[0]["name"] == "Alice"

    def test_validation_errors(self):
        """Test validation error handling."""

        @dataclass
        class User(DomainModel):
            id: int
            name: str
            age: int  # Required field

        mapper = DomainDataMapper(User)

        # Missing required field
        row = {
            "id": 1,
            "name": "John",
            # age is missing
        }

        with pytest.raises(MappingError) as exc_info:
            mapper.to_entity(row)

        assert "Required field" in str(exc_info.value)
        assert "age" in str(exc_info.value)

        # Missing all required fields
        row_empty: dict[str, _Any] = {}

        with pytest.raises(MappingError) as exc_info:
            mapper.to_entity(row_empty)

        assert "Required field" in str(exc_info.value)

    def test_none_row_handling(self):
        """Test handling of None rows."""

        @dataclass
        class User(DomainModel):
            id: int
            name: str

        mapper = DomainDataMapper(User)

        with pytest.raises(MappingError) as exc_info:
            mapper.to_entity(None)

        assert "Row cannot be None" in str(exc_info.value)


class TestFieldMapping:
    """Test field mapping configuration."""

    def test_basic_field_mapping(self):
        """Test basic field mapping operations."""
        mapping = FieldMapping("entity_field", "db_column")

        # Test conversions without converters
        assert mapping.convert_to_entity("value") == "value"
        assert mapping.convert_to_db("value") == "value"

    def test_field_mapping_with_converters(self):
        """Test field mapping with custom converters."""

        def to_upper(value):
            return str(value).upper()

        def to_lower(value):
            return str(value).lower()

        mapping = FieldMapping(
            "entity_field", "db_column", converter=to_upper, reverse_converter=to_lower,
        )

        assert mapping.convert_to_entity("hello") == "HELLO"
        assert mapping.convert_to_db("WORLD") == "world"