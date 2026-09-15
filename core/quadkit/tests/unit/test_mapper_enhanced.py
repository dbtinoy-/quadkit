"""Tests for enhanced ObjectMapperImpl — auto_map, auto_map_many, register_two_way, map_or_auto."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.mapping.core.mapper import ObjectMapperImpl, _extract_fields

# ---------------------------------------------------------------------------
# Test types
# ---------------------------------------------------------------------------


@dataclass
class UserEntity:
    name: str
    email: str
    age: int


@dataclass
class UserDTO:
    name: str
    email: str


@dataclass
class UserResponse:
    name: str
    email: str
    age: int


# ===========================================================================
# auto_map
# ===========================================================================


class TestAutoMap:
    """Tests for auto_map — automatic field-name matching."""

    def test_dataclass_to_dataclass(self) -> None:
        mapper = ObjectMapperImpl()
        entity = UserEntity(name="Alice", email="a@b.com", age=30)
        dto = mapper.auto_map(entity, UserDTO)
        assert isinstance(dto, UserDTO)
        assert dto.name == "Alice"
        assert dto.email == "a@b.com"

    def test_extra_fields_ignored(self) -> None:
        mapper = ObjectMapperImpl()
        entity = UserEntity(name="Bob", email="b@c.com", age=25)
        # UserDTO has no 'age' field — it should be ignored
        dto = mapper.auto_map(entity, UserDTO)
        assert dto.name == "Bob"
        assert not hasattr(dto, "age")

    def test_dict_source(self) -> None:
        mapper = ObjectMapperImpl()
        data = {"name": "Charlie", "email": "c@d.com", "extra": True}
        dto = mapper.auto_map(data, UserDTO)
        assert dto.name == "Charlie"
        assert dto.email == "c@d.com"

    def test_full_field_match(self) -> None:
        mapper = ObjectMapperImpl()
        entity = UserEntity(name="Dave", email="d@e.com", age=40)
        response = mapper.auto_map(entity, UserResponse)
        assert response.name == "Dave"
        assert response.age == 40


# ===========================================================================
# auto_map_many
# ===========================================================================


class TestAutoMapMany:
    """Tests for auto_map_many — bulk auto mapping."""

    def test_maps_list(self) -> None:
        mapper = ObjectMapperImpl()
        entities = [
            UserEntity(name="A", email="a@x.com", age=20),
            UserEntity(name="B", email="b@x.com", age=30),
        ]
        dtos = mapper.auto_map_many(entities, UserDTO)
        assert len(dtos) == 2
        assert dtos[0].name == "A"
        assert dtos[1].name == "B"

    def test_empty_list(self) -> None:
        mapper = ObjectMapperImpl()
        assert mapper.auto_map_many([], UserDTO) == []


# ===========================================================================
# register_two_way
# ===========================================================================


class TestRegisterTwoWay:
    """Tests for register_two_way — bidirectional mappings."""

    def test_both_directions_registered(self) -> None:
        mapper = ObjectMapperImpl()
        mapper.register_two_way(
            UserEntity,
            UserDTO,
            a_to_b=lambda e: UserDTO(name=e.name, email=e.email),
            b_to_a=lambda d: UserEntity(name=d.name, email=d.email, age=0),
        )
        assert mapper.registry.has(UserEntity, UserDTO)
        assert mapper.registry.has(UserDTO, UserEntity)

    def test_map_a_to_b(self) -> None:
        mapper = ObjectMapperImpl()
        mapper.register_two_way(
            UserEntity,
            UserDTO,
            a_to_b=lambda e: UserDTO(name=e.name, email=e.email),
            b_to_a=lambda d: UserEntity(name=d.name, email=d.email, age=0),
        )
        dto = mapper.map(UserEntity(name="X", email="x@y.com", age=10), UserDTO)
        assert dto.name == "X"
        assert dto.email == "x@y.com"

    def test_map_b_to_a(self) -> None:
        mapper = ObjectMapperImpl()
        mapper.register_two_way(
            UserEntity,
            UserDTO,
            a_to_b=lambda e: UserDTO(name=e.name, email=e.email),
            b_to_a=lambda d: UserEntity(name=d.name, email=d.email, age=0),
        )
        entity = mapper.map(UserDTO(name="Y", email="y@z.com"), UserEntity)
        assert entity.name == "Y"
        assert entity.age == 0


# ===========================================================================
# map_or_auto
# ===========================================================================


class TestMapOrAuto:
    """Tests for map_or_auto — registered fallback to auto."""

    def test_uses_registered_when_available(self) -> None:
        mapper = ObjectMapperImpl()
        mapper.register(
            UserEntity,
            UserDTO,
            lambda e: UserDTO(name=e.name.upper(), email=e.email),
        )
        dto = mapper.map_or_auto(
            UserEntity(name="alice", email="a@b.com", age=1), UserDTO,
        )
        assert dto.name == "ALICE"  # custom mapper uppercased it

    def test_falls_back_to_auto(self) -> None:
        mapper = ObjectMapperImpl()
        # No registered mapping — should auto_map
        dto = mapper.map_or_auto(
            UserEntity(name="alice", email="a@b.com", age=1), UserDTO,
        )
        assert dto.name == "alice"  # auto_map preserves original
        assert dto.email == "a@b.com"


# ===========================================================================
# _extract_fields helper
# ===========================================================================


class TestExtractFields:
    """Tests for _extract_fields utility."""

    def test_from_dataclass(self) -> None:
        fields = _extract_fields(UserEntity(name="A", email="b", age=1))
        assert fields == {"name": "A", "email": "b", "age": 1}

    def test_from_dict(self) -> None:
        fields = _extract_fields({"x": 1, "y": 2})
        assert fields == {"x": 1, "y": 2}

    def test_from_plain_object(self) -> None:
        class Obj:
            def __init__(self) -> None:
                self.a = 10

        fields = _extract_fields(Obj())
        assert fields == {"a": 10}
