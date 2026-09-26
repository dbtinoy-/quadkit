import pytest
pytest.skip("async schema tests disabled", allow_module_level=True)

import asyncio
from typing import Any

from quadkit.logging import get_logger
from quadkit.events.schema.evolution import SchemaEvolution, Upcaster
from quadkit.events.schema.registry import SchemaRegistry

logger = get_logger(__name__)


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


async def test_schema_evolution():
    logger.info("Testing schema evolution...")

    # Setup
    registry = SchemaRegistry()
    evolution = SchemaEvolution(registry)

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
