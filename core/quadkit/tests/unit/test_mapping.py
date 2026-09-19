"""Tests for the object mapping module."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from quadkit.mapping.core.mapper import MappingRegistry, ObjectMapperImpl


@dataclass
class UserEntity:
    """Sample source entity for mapping tests."""
    id: int
    name: str
    email: str


@dataclass
class UserDTO:
    """Sample destination DTO for mapping tests."""
    id: int
    display_name: str


def user_to_dto(user: UserEntity) -> UserDTO:
    """Sample mapping function."""
    return UserDTO(id=user.id, display_name=user.name)


class TestMappingRegistry:
    """Tests for MappingRegistry."""

    def test_register_and_get(self) -> None:
        """Register a mapping and retrieve it successfully."""
        registry = MappingRegistry()
        registry.register(UserEntity, UserDTO, user_to_dto)
        assert registry.get(UserEntity, UserDTO) is user_to_dto

    def test_has_returns_true_for_registered(self) -> None:
        """has() returns True for registered mappings."""
        registry = MappingRegistry()
        registry.register(UserEntity, UserDTO, user_to_dto)
        assert registry.has(UserEntity, UserDTO) is True

    def test_has_returns_false_for_unregistered(self) -> None:
        """has() returns False for unregistered mappings."""
        registry = MappingRegistry()
        assert registry.has(UserEntity, UserDTO) is False

    def test_get_returns_none_for_missing(self) -> None:
        """get() returns None for unregistered mappings."""
        registry = MappingRegistry()
        assert registry.get(UserEntity, UserDTO) is None

    def test_duplicate_registration_raises(self) -> None:
        """Registering the same pair twice raises ValueError."""
        registry = MappingRegistry()
        registry.register(UserEntity, UserDTO, user_to_dto)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(UserEntity, UserDTO, user_to_dto)

    def test_unregister(self) -> None:
        """Unregister removes a registered mapping."""
        registry = MappingRegistry()
        registry.register(UserEntity, UserDTO, user_to_dto)
        registry.unregister(UserEntity, UserDTO)
        assert registry.has(UserEntity, UserDTO) is False

    def test_unregister_missing_raises(self) -> None:
        """Unregistering a non-existent mapping raises KeyError."""
        registry = MappingRegistry()
        with pytest.raises(KeyError, match="No mapping"):
            registry.unregister(UserEntity, UserDTO)


class TestObjectMapper:
    """Tests for ObjectMapperImpl."""

    @pytest.fixture
    def mapper(self) -> ObjectMapperImpl:
        m = ObjectMapperImpl()
        m.register(UserEntity, UserDTO, user_to_dto)
        return m

    def test_map_converts_object(self, mapper: ObjectMapperImpl) -> None:
        """map() converts source to destination type."""
        user = UserEntity(id=1, name="Alice", email="alice@test.com")
        dto = mapper.map(user, UserDTO)
        assert dto.id == 1
        assert dto.display_name == "Alice"

    def test_map_raises_for_unregistered(self, mapper: ObjectMapperImpl) -> None:
        """map() raises MappingNotFoundError for unregistered type pairs."""
        from quadkit.mapping.exceptions import MappingNotFoundError
        user_dto = UserDTO(id=1, display_name="Alice")
        with pytest.raises(MappingNotFoundError, match="No mapper registered"):
            mapper.map(user_dto, UserEntity)

    def test_map_many(self, mapper: ObjectMapperImpl) -> None:
        """map_many() converts a list of objects."""
        users = [
            UserEntity(id=1, name="Alice", email="a@test.com"),
            UserEntity(id=2, name="Bob", email="b@test.com"),
        ]
        dtos = mapper.map_many(users, UserDTO)
        assert len(dtos) == 2
        assert dtos[0].display_name == "Alice"
        assert dtos[1].display_name == "Bob"

    def test_registry_property(self, mapper: ObjectMapperImpl) -> None:
        """registry property gives access to the underlying registry."""
        assert isinstance(mapper.registry, MappingRegistry)
