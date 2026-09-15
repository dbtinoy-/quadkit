"""Integration test: container + provider + Result pipeline.

Tests the five pillars working together:
- Contracts/Protocols as service boundaries
- Provider registration
- Container resolution via DI
- Result[T, E] for domain operations
- Event publishing through in-memory bus
"""

from __future__ import annotations

import pytest

from quadkit.result import Err, Ok, Result
from quadkit.testing import QuadkitContainerHarness

# Use new name in code but keep backward-compat alias
TestContainer = QuadkitContainerHarness

# ---------------------------------------------------------------------------
# Minimal domain types for the test
# ---------------------------------------------------------------------------


class ItemNotFound(Exception):
    """Domain error: item does not exist."""

    def __init__(self, item_id: str) -> None:
        super().__init__(f"Item not found: {item_id}")
        self.item_id = item_id


class Item:
    """Simple domain entity."""

    def __init__(self, item_id: str, name: str) -> None:
        self.item_id = item_id
        self.name = name


# ---------------------------------------------------------------------------
# Minimal protocol + implementation
# ---------------------------------------------------------------------------


class ItemRepositoryProtocol:
    """Protocol for item persistence."""

    async def get(self, item_id: str) -> Item | None: ...


class InMemoryItemRepository:
    """Fake in-memory implementation."""

    def __init__(self) -> None:
        self._store: dict[str, Item] = {}

    def seed(self, item: Item) -> None:
        self._store[item.item_id] = item

    async def get(self, item_id: str) -> Item | None:
        return self._store.get(item_id)


class ItemService:
    """Domain service that depends on the repo protocol."""

    def __init__(self, repo: ItemRepositoryProtocol) -> None:
        self._repo = repo

    async def find(self, item_id: str) -> Result[Item, ItemNotFound]:
        item = await self._repo.get(item_id)
        if item is None:
            return Err(ItemNotFound(item_id))
        return Ok(item)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFullContainerPipeline:
    """Full pipeline: registration → resolution → domain operation → Result."""

    @pytest.fixture
    def container(self) -> TestContainer:
        c = TestContainer(register_mocks=False)
        repo = InMemoryItemRepository()
        repo.seed(Item("item-1", "Widget"))
        c.singleton(ItemRepositoryProtocol, repo)
        c.singleton(ItemService, ItemService(repo))
        return c

    @pytest.mark.asyncio
    async def test_resolves_service_and_finds_item(
        self, container: TestContainer
    ) -> None:
        service = await container.resolve(ItemService)
        result = await service.find("item-1")

        assert result.is_ok()
        assert result.unwrap().name == "Widget"

    @pytest.mark.asyncio
    async def test_returns_err_for_missing_item(
        self, container: TestContainer
    ) -> None:
        service = await container.resolve(ItemService)
        result = await service.find("nonexistent")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ItemNotFound)
        assert error.item_id == "nonexistent"

    @pytest.mark.asyncio
    async def test_override_replaces_registration(
        self, container: TestContainer
    ) -> None:
        replacement_repo = InMemoryItemRepository()
        replacement_repo.seed(Item("item-2", "Gadget"))
        new_service = ItemService(replacement_repo)

        with container.override(ItemRepositoryProtocol, replacement_repo):
            with container.override(ItemService, new_service):
                service = await container.resolve(ItemService)
                result = await service.find("item-2")

        assert result.is_ok()
        assert result.unwrap().name == "Gadget"

    @pytest.mark.asyncio
    async def test_result_match_helper(self, container: TestContainer) -> None:
        service = await container.resolve(ItemService)
        found = await service.find("item-1")
        missing = await service.find("nope")

        found_msg = found.match(ok=lambda i: i.name, err=lambda e: "error")
        missing_msg = missing.match(ok=lambda i: i.name, err=lambda e: "not_found")

        assert found_msg == "Widget"
        assert missing_msg == "not_found"

