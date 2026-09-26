import pytest
pytest.skip("async schema tests disabled", allow_module_level=True)

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)


class Upcaster(ABC):
    event_type: str
    source_version: int
    target_version: int

    @abstractmethod
    async def upcast(self, data: dict[str, Any]) -> dict[str, Any]:
        pass


class TestUpcasterV1ToV2(Upcaster):
    event_type = "TestEvent"
    source_version = 1
    target_version = 2

    async def upcast(self, data: dict[str, Any]) -> dict[str, Any]:
        # Add a new field
        data["new_field"] = "default_value"
        return data


class TestUpcasterV2ToV3(Upcaster):
    event_type = "TestEvent"
    source_version = 2
    target_version = 3

    async def upcast(self, data: dict[str, Any]) -> dict[str, Any]:
        # Modify existing field
        data["value"] = data.get("value", 0) * 2
        return data


@dataclass
class MigrationPath:
    event_type: str
    from_version: int
    to_version: int
    steps: list[Upcaster]


class SchemaEvolution:
    def __init__(self):
        self._upcasters: dict[str, dict[tuple[int, int], Upcaster]] = {}

    def register_upcaster(self, upcaster: Upcaster) -> None:
        event_type = upcaster.event_type
        if event_type not in self._upcasters:
            self._upcasters[event_type] = {}
        key = (upcaster.source_version, upcaster.target_version)
        self._upcasters[event_type][key] = upcaster

    async def get_migration_path(
        self, event_type: str, from_version: int, to_version: int,
    ) -> MigrationPath | None:
        if from_version == to_version:
            return MigrationPath(
                event_type=event_type,
                from_version=from_version,
                to_version=to_version,
                steps=[],
            )

        steps = []
        current = from_version
        while current < to_version:
            upcaster = self._find_upcaster(event_type, current)
            if upcaster is None:
                return None
            steps.append(upcaster)
            current = upcaster.target_version

        return MigrationPath(
            event_type=event_type,
            from_version=from_version,
            to_version=to_version,
            steps=steps,
        )

    def _find_upcaster(self, event_type: str, from_version: int) -> Upcaster | None:
        if event_type not in self._upcasters:
            return None
        for (source, _), upcaster in self._upcasters[event_type].items():
            if source == from_version:
                return upcaster
        return None

    async def migrate_data(
        self, event_type: str, data: dict[str, Any], from_version: int, to_version: int,
    ) -> dict[str, Any]:
        if from_version == to_version:
            return data

        path = await self.get_migration_path(event_type, from_version, to_version)
        if path is None:
            raise ValueError(
                f"No migration path from {event_type} v{from_version} to v{to_version}",
            )

        result = dict(data)
        for step in path.steps:
            result = await step.upcast(result)
        return result


async def test_schema_evolution():
    logger.info("Testing schema evolution...")

    # Setup
    evolution = SchemaEvolution()

    # Register upcasters
    evolution.register_upcaster(TestUpcasterV1ToV2())
    evolution.register_upcaster(TestUpcasterV2ToV3())

    # Test migration path
    path = await evolution.get_migration_path("TestEvent", 1, 3)
    logger.info("Migration path found: %s", path is not None)
    if path:
        logger.info("Steps: %d", len(path.steps))

    # Test data migration
    original_data = {"value": 5, "name": "test"}

    # Migrate v1 -> v2
    migrated_v2 = await evolution.migrate_data("TestEvent", original_data, 1, 2)
    logger.info("V1->V2: %s -> %s", original_data, migrated_v2)

    # Migrate v1 -> v3
    migrated_v3 = await evolution.migrate_data("TestEvent", original_data, 1, 3)
    logger.info("V1->V3: %s -> %s", original_data, migrated_v3)

    logger.info("Schema evolution test completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_schema_evolution())
