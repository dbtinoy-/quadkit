"""Integration tests for the quadkit-mapping provider lifecycle.

Tests the complete DI lifecycle for the mapping subsystem using the real
Container — no external services required.

Flow under test:
  MappingProvider.register() → MappingProvider.boot()
  → resolve ObjectMapperImpl → register a mapping → map() end-to-end
  → MappingProvider.shutdown()
"""

from __future__ import annotations

import dataclasses

import pytest

from quadkit.di.container import Container
from quadkit.mapping.core.mapper import MappingRegistry, ObjectMapperImpl
from quadkit.mapping.di.provider import MappingProvider

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Simple domain fixtures used across tests
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _UserEntity:
    """Source domain model."""

    user_id: str
    full_name: str
    email: str


@dataclasses.dataclass
class _UserDTO:
    """Destination DTO."""

    user_id: str
    full_name: str
    email: str


def _user_to_dto(user: _UserEntity) -> _UserDTO:
    """Mapping function from _UserEntity → _UserDTO."""
    return _UserDTO(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
    )


class TestMappingProviderLifecycle:
    """Full provider lifecycle for the object-mapper subsystem.

    Exercises the register → boot → resolve → map → shutdown sequence
    using the real DI Container, MappingRegistry, and ObjectMapperImpl.
    """

    @pytest.fixture
    async def booted_container(self):
        """Container with MappingProvider fully registered and booted."""
        provider = MappingProvider()
        container = Container()
        await provider.register(container)
        await provider.boot(container)
        yield container
        await provider.shutdown()

    # ------------------------------------------------------------------
    # register phase
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_register_binds_mapping_registry(self) -> None:
        """MappingRegistry singleton is bound after register()."""
        provider = MappingProvider()
        container = Container()

        await provider.register(container)

        registry = await container.resolve(MappingRegistry)

        assert isinstance(registry, MappingRegistry)
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_register_binds_object_mapper(self) -> None:
        """ObjectMapperImpl singleton is bound after register()."""
        provider = MappingProvider()
        container = Container()

        await provider.register(container)

        mapper = await container.resolve(ObjectMapperImpl)

        assert isinstance(mapper, ObjectMapperImpl)
        await provider.shutdown()

    # ------------------------------------------------------------------
    # boot phase
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_boot_completes_without_error(self, booted_container: Container) -> None:
        """boot() completes successfully — no boot-time work is expected."""
        mapper = await booted_container.resolve(ObjectMapperImpl)

        assert mapper is not None

    @pytest.mark.asyncio
    async def test_registry_and_mapper_share_same_registry_instance(
        self, booted_container: Container
    ) -> None:
        """ObjectMapperImpl.registry is the same instance as MappingRegistry."""
        registry = await booted_container.resolve(MappingRegistry)
        mapper = await booted_container.resolve(ObjectMapperImpl)

        assert mapper.registry is registry

    @pytest.mark.asyncio
    async def test_singletons_return_same_instance_on_repeated_resolution(
        self, booted_container: Container
    ) -> None:
        """Resolving ObjectMapperImpl twice returns the same singleton."""
        mapper_a = await booted_container.resolve(ObjectMapperImpl)
        mapper_b = await booted_container.resolve(ObjectMapperImpl)

        assert mapper_a is mapper_b

    # ------------------------------------------------------------------
    # end-to-end mapping
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_map_operation_transforms_entity_to_dto(
        self, booted_container: Container
    ) -> None:
        """Registered mapping function executes correctly end-to-end."""
        mapper = await booted_container.resolve(ObjectMapperImpl)
        mapper.register(_UserEntity, _UserDTO, _user_to_dto)

        entity = _UserEntity(
            user_id="u-001",
            full_name="Alice Nguyen",
            email="alice@example.com",
        )

        dto = mapper.map(entity, _UserDTO)

        assert isinstance(dto, _UserDTO)
        assert dto.user_id == "u-001"
        assert dto.full_name == "Alice Nguyen"
        assert dto.email == "alice@example.com"

    @pytest.mark.asyncio
    async def test_map_many_transforms_a_collection(self, booted_container: Container) -> None:
        """map_many() maps every item in a list end-to-end."""
        mapper = await booted_container.resolve(ObjectMapperImpl)
        mapper.register(_UserEntity, _UserDTO, _user_to_dto)

        entities = [
            _UserEntity(user_id="u-001", full_name="Alice", email="alice@example.com"),
            _UserEntity(user_id="u-002", full_name="Bob", email="bob@example.com"),
        ]

        dtos = mapper.map_many(entities, _UserDTO)

        assert len(dtos) == 2
        assert dtos[0].user_id == "u-001"
        assert dtos[1].user_id == "u-002"

    @pytest.mark.asyncio
    async def test_try_map_returns_ok_result_on_success(self, booted_container: Container) -> None:
        """try_map() returns Ok wrapping the mapped DTO on success."""
        mapper = await booted_container.resolve(ObjectMapperImpl)
        mapper.register(_UserEntity, _UserDTO, _user_to_dto)

        entity = _UserEntity(user_id="u-003", full_name="Carol", email="carol@example.com")

        result = mapper.try_map(entity, _UserDTO)

        assert result.is_ok()
        dto = result.unwrap()
        assert dto.user_id == "u-003"

    @pytest.mark.asyncio
    async def test_mapping_not_found_raises_for_unregistered_pair(
        self, booted_container: Container
    ) -> None:
        """Mapping an unregistered type pair raises MappingNotFoundError."""
        from quadkit.mapping.exceptions import MappingNotFoundError

        mapper = await booted_container.resolve(ObjectMapperImpl)

        @dataclasses.dataclass
        class _Unknown:
            value: int

        with pytest.raises(MappingNotFoundError):
            mapper.map(_Unknown(value=42), _UserDTO)

    # ------------------------------------------------------------------
    # shutdown
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self) -> None:
        """Calling shutdown() twice must not raise."""
        provider = MappingProvider()
        container = Container()
        await provider.register(container)
        await provider.boot(container)

        await provider.shutdown()
        await provider.shutdown()
