"""Tests for ObjectMapperImpl.auto_map() with Pydantic v2 models.

Verifies that the auto_map() method's model_validate() path works
correctly when the destination type is a Pydantic v2 BaseModel.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
import pytest

from quadkit.mapping.core.mapper import ObjectMapperImpl


class UserCreateRequest(BaseModel):
    """Pydantic v2 model for user creation (destination)."""

    name: str
    email: str
    age: int = 0


class UserResponse(BaseModel):
    """Pydantic v2 model for user response."""

    name: str
    email: str
    age: int


@dataclass
class UserRaw:
    """Plain dataclass source."""

    name: str
    email: str
    age: int
    internal_notes: str = ""  # extra field — should be ignored


class TestAutoMapPydanticV2:
    """Tests for auto_map() → model_validate() path with Pydantic v2 models."""

    @pytest.fixture
    def mapper(self) -> ObjectMapperImpl:
        return ObjectMapperImpl()

    def test_auto_map_dataclass_to_pydantic_model(self, mapper: ObjectMapperImpl) -> None:
        """auto_map() uses model_validate() for Pydantic v2 BaseModel destination."""
        source = UserRaw(name="Alice", email="alice@example.com", age=30)
        result = mapper.auto_map(source, UserCreateRequest)
        assert isinstance(result, UserCreateRequest)
        assert result.name == "Alice"
        assert result.email == "alice@example.com"
        assert result.age == 30

    def test_auto_map_ignores_extra_fields(self, mapper: ObjectMapperImpl) -> None:
        """Extra fields in source are silently ignored during auto_map()."""
        source = UserRaw(
            name="Bob",
            email="bob@example.com",
            age=25,
            internal_notes="do not expose",
        )
        result = mapper.auto_map(source, UserCreateRequest)
        assert result.name == "Bob"
        # internal_notes is NOT a field on UserCreateRequest
        assert not hasattr(result, "internal_notes")

    def test_auto_map_uses_pydantic_defaults(self, mapper: ObjectMapperImpl) -> None:
        """Fields missing from source use Pydantic model defaults."""

        @dataclass
        class MinimalSource:
            name: str
            email: str

        source = MinimalSource(name="Carol", email="carol@example.com")
        result = mapper.auto_map(source, UserCreateRequest)
        assert result.name == "Carol"
        assert result.age == 0  # default from Pydantic model

    def test_auto_map_pydantic_to_pydantic(self, mapper: ObjectMapperImpl) -> None:
        """auto_map() works from one Pydantic model to another with matching fields."""
        source = UserResponse(name="Dave", email="dave@example.com", age=40)
        result = mapper.auto_map(source, UserCreateRequest)
        assert isinstance(result, UserCreateRequest)
        assert result.name == "Dave"
        assert result.email == "dave@example.com"
        assert result.age == 40

    def test_auto_map_result_is_pydantic_instance(self, mapper: ObjectMapperImpl) -> None:
        """Result of auto_map() is a proper Pydantic model instance, not a dict."""
        source = UserRaw(name="Eve", email="eve@example.com", age=22)
        result = mapper.auto_map(source, UserCreateRequest)
        # Verify it behaves like a Pydantic model
        assert result.model_dump() == {"name": "Eve", "email": "eve@example.com", "age": 22}

    def test_auto_map_many_pydantic_v2(self, mapper: ObjectMapperImpl) -> None:
        """auto_map_many() works with Pydantic v2 destination type."""
        sources = [
            UserRaw(name=f"User{i}", email=f"user{i}@example.com", age=20 + i) for i in range(4)
        ]
        results = mapper.auto_map_many(sources, UserCreateRequest)
        assert len(results) == 4
        assert all(isinstance(r, UserCreateRequest) for r in results)
        assert results[2].name == "User2"
        assert results[2].age == 22

    def test_auto_map_pydantic_validation_catches_type_error(self, mapper: ObjectMapperImpl) -> None:
        """Pydantic v2 validation rejects incompatible field types."""

        @dataclass
        class BadSource:
            name: str
            email: str
            age: str  # string, not int

        source = BadSource(name="Frank", email="frank@example.com", age="not-a-number")
        with pytest.raises(ValidationError):
            mapper.auto_map(source, UserCreateRequest)

    def test_map_or_auto_falls_back_to_auto_map_for_pydantic(self, mapper: ObjectMapperImpl) -> None:
        """map_or_auto() falls back to auto_map() for unregistered types."""
        source = UserRaw(name="Grace", email="grace@example.com", age=35)
        result = mapper.map_or_auto(source, UserCreateRequest)
        assert isinstance(result, UserCreateRequest)
        assert result.name == "Grace"
