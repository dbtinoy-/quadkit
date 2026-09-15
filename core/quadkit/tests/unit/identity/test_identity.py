from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from quadkit.primitives import clock as ambient_clock
from quadkit.identity import ambient as identity_ambient
from quadkit.testing.clock import FixedClock
from quadkit.identity.config import IdentityConfig
from quadkit.identity.di.provider import IdentityProvider
from quadkit.identity.generator import (
    PrefixedIdGenerator,
    UlidGenerator,
    Uuid4Generator,
    Uuid7Generator,
)
from quadkit.contracts.core.identity import IdGeneratorProtocol, IdStrategy


class TestGenerators:
    def test_uuid4_generator_emits_uuid_string(self) -> None:
        generator = Uuid4Generator()
        assert generator.strategy is IdStrategy.UUID4
        assert UUID(generator.generate())

    def test_uuid7_generator_is_time_ordered(self) -> None:
        fixed_clock = FixedClock()
        with ambient_clock.use(fixed_clock):
            generator = Uuid7Generator()
            first = generator.generate()
            fixed_clock.advance(1)
            second = generator.generate()
            assert first < second

    def test_ulid_generator_is_time_ordered(self) -> None:
        fixed_clock = FixedClock()
        with ambient_clock.use(fixed_clock):
            generator = UlidGenerator()
            first = generator.generate()
            fixed_clock.advance(1)
            second = generator.generate()
            assert len(first) == 26
            assert first < second

    def test_prefixed_generator_uses_entity_prefix(self) -> None:
        fixed_clock = FixedClock()
        with ambient_clock.use(fixed_clock):
            generator = PrefixedIdGenerator(
                prefix_map={"user": "usr"},
            )
            value = generator.generate_for("user")
            assert value.startswith("usr_")
            assert len(value.split("_", 1)[1]) == 26

    def test_prefixed_generator_falls_back_to_entity_prefix(self) -> None:
        fixed_clock = FixedClock()
        with ambient_clock.use(fixed_clock):
            generator = PrefixedIdGenerator()
            value = generator.generate_for("widget")
            assert value.startswith("wid_")


class TestIdGeneratorProtocol:
    def test_uuid4_generator_satisfies_protocol(self) -> None:
        assert isinstance(Uuid4Generator(), IdGeneratorProtocol)


class TestIdentityProvider:
    def test_no_clock_dependency(self) -> None:
        provider = IdentityProvider()
        assert provider.dependencies == ()

    @pytest.mark.asyncio
    async def test_registers_generator_protocol(self) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        provider = IdentityProvider(config=IdentityConfig(strategy=IdStrategy.UUID4))
        await provider.register(container)

        call_targets = [call.args[0] for call in container.singleton.call_args_list]
        assert IdGeneratorProtocol in call_targets
        assert Uuid4Generator in call_targets

    @pytest.mark.asyncio
    async def test_boot_updates_ambient(self) -> None:
        @dataclass
        class StubGenerator:
            strategy: IdStrategy = IdStrategy.UUID4

            def generate(self) -> str:
                return "booted"

            def generate_for(self, entity_type: str) -> str:
                return f"{entity_type}-booted"

        original = identity_ambient._ambient.get()
        try:
            container = MagicMock()
            container.resolve = AsyncMock(return_value=StubGenerator())

            provider = IdentityProvider()
            await provider.boot(container)

            assert identity_ambient.generate_for("user") == "user-booted"
        finally:
            identity_ambient.install(original)
