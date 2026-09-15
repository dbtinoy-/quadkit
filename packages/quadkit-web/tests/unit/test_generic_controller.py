"""Tests for GenericController."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from quadkit.contracts.web.protocols import CRUDServiceProtocol
from quadkit.result import Ok, Err
from quadkit.contracts.exceptions.domain import DomainError
from quadkit.web.routing.controller import GenericController


class DummyItem:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name


class ItemNotFound(DomainError):
    pass


class MockCRUDService:
    async def list_items(
        self, limit: int = 20, offset: int = 0, **filters
    ):
        items = [DummyItem("1", "item1"), DummyItem("2", "item2")]
        return Ok(items[offset : offset + limit])

    async def get(self, item_id):
        if item_id == "1":
            return Ok(DummyItem("1", "item1"))
        return Ok(None)

    async def create(self, data):
        return Ok(DummyItem("new", data.get("name", "unnamed")))

    async def update(self, item_id, data):
        if item_id == "1":
            return Ok(DummyItem(item_id, data.get("name", "updated")))
        return Ok(None)

    async def delete(self, item_id):
        if item_id == "1":
            return Ok(True)
        return Ok(False)


class TestGenericController:
    """Tests for GenericController class."""

    def test_init_with_service(self):
        service = MockCRUDService()
        controller = GenericController(service=service)

        assert controller.service is service

    def test_default_resource_name(self):
        service = MockCRUDService()
        controller = GenericController(service=service)

        assert controller.resource_name == "generic"

    def test_custom_resource_name(self):
        service = MockCRUDService()
        controller = GenericController(service=service, resource_name="user")

        assert controller.resource_name == "user"

    def test_resource_name_from_class_name(self):
        service = MockCRUDService()

        class UserController(GenericController):
            pass

        controller = UserController(service=service)
        assert controller.resource_name == "user"

    def test_resource_name_removes_controller_suffix(self):
        service = MockCRUDService()

        class ItemController(GenericController):
            pass

        controller = ItemController(service=service)
        assert controller.resource_name == "item"

    def test_resource_name_removes_v1(self):
        service = MockCRUDService()

        class UserV1Controller(GenericController):
            pass

        controller = UserV1Controller(service=service)
        # v1 should be removed, so "userv1" becomes "user"
        assert controller.resource_name == "user"

    def test_has_logger(self):
        service = MockCRUDService()
        controller = GenericController(service=service)

        assert controller.logger is not None

    @pytest.mark.asyncio
    async def test_list_items_returns_result(self):
        service = MockCRUDService()
        controller = GenericController(service=service)

        result = await controller.list_items(limit=10, offset=0)

        assert hasattr(result, "is_ok")
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_list_items_returns_paginated_results(self):
        service = MockCRUDService()
        controller = GenericController(service=service)

        result = await controller.list_items(limit=10, offset=0)

        assert result.is_ok()
        data = result.unwrap()
        assert "items" in data
        assert "limit" in data
        assert "offset" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_get_item_found(self):
        service = MockCRUDService()
        controller = GenericController(service=service)

        result = await controller.get_item("1")

        assert result.is_ok()
        item = result.unwrap()
        assert item.id == "1"

    @pytest.mark.asyncio
    async def test_get_item_not_found_raises_not_found_error(self):
        from quadkit.web.exceptions import NotFoundError

        service = MockCRUDService()
        controller = GenericController(service=service)

        with pytest.raises(NotFoundError):
            await controller.get_item("999")

    @pytest.mark.asyncio
    async def test_create_item_success(self):
        service = MockCRUDService()
        controller = GenericController(service=service)

        result = await controller.create_item({"name": "new item"})

        # create_item returns a JSONResponse, not Result
        assert result is not None
        assert hasattr(result, "status_code")

    @pytest.mark.asyncio
    async def test_update_item_found(self):
        service = MockCRUDService()
        controller = GenericController(service=service)

        result = await controller.update_item("1", {"name": "updated name"})

        assert result.is_ok()
        item = result.unwrap()
        assert item.name == "updated name"

    @pytest.mark.asyncio
    async def test_update_item_not_found_raises_not_found_error(self):
        from quadkit.web.exceptions import NotFoundError

        service = MockCRUDService()
        controller = GenericController(service=service)

        with pytest.raises(NotFoundError):
            await controller.update_item("999", {"name": "updated"})

    @pytest.mark.asyncio
    async def test_delete_item_success(self):
        service = MockCRUDService()
        controller = GenericController(service=service)

        result = await controller.delete_item("1")

        # delete_item returns a JSONResponse, not Result
        assert result is not None
        assert hasattr(result, "status_code")

    @pytest.mark.asyncio
    async def test_delete_item_not_found_raises_not_found_error(self):
        from quadkit.web.exceptions import NotFoundError

        service = MockCRUDService()
        controller = GenericController(service=service)

        with pytest.raises(NotFoundError):
            await controller.delete_item("999")

    def test_controller_is_controller_subclass(self):
        from quadkit.web.routing.controllers import Controller

        service = MockCRUDService()
        controller = GenericController(service=service)

        assert isinstance(controller, Controller)

    def test_inherits_from_controller(self):
        from quadkit.web.routing.controllers import Controller as BaseController

        assert issubclass(GenericController, BaseController)


class TestGenericControllerWithMockService:
    """Tests for GenericController with fully mocked service."""

    @pytest.mark.asyncio
    async def test_list_items_returns_error_from_service(self):
        mock_service = MagicMock(spec=CRUDServiceProtocol)
        mock_service.list_items = AsyncMock(
            return_value=Err(DomainError("Database error"))
        )

        controller = GenericController(service=mock_service)
        result = await controller.list_items()

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_get_item_returns_error_from_service(self):
        mock_service = MagicMock(spec=CRUDServiceProtocol)
        mock_service.get = AsyncMock(return_value=Err(DomainError("Not found")))

        controller = GenericController(service=mock_service)
        result = await controller.get_item("1")

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_create_item_returns_error_from_service(self):
        mock_service = MagicMock(spec=CRUDServiceProtocol)
        mock_service.create = AsyncMock(
            return_value=Err(DomainError("Validation failed"))
        )

        controller = GenericController(service=mock_service)
        result = await controller.create_item({"name": "test"})

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_update_item_returns_error_from_service(self):
        mock_service = MagicMock(spec=CRUDServiceProtocol)
        mock_service.update = AsyncMock(
            return_value=Err(DomainError("Update failed"))
        )

        controller = GenericController(service=mock_service)
        result = await controller.update_item("1", {"name": "test"})

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_delete_item_returns_error_from_service(self):
        mock_service = MagicMock(spec=CRUDServiceProtocol)
        mock_service.delete = AsyncMock(
            return_value=Err(DomainError("Delete failed"))
        )

        controller = GenericController(service=mock_service)
        result = await controller.delete_item("1")

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_list_items_passes_filters_to_service(self):
        mock_service = MagicMock(spec=CRUDServiceProtocol)
        mock_service.list_items = AsyncMock(return_value=Ok([]))

        controller = GenericController(service=mock_service)
        await controller.list_items(limit=10, offset=5, status="active")

        mock_service.list_items.assert_called_once_with(
            limit=10, offset=5, status="active"
        )

    @pytest.mark.asyncio
    async def test_get_item_passes_id_to_service(self):
        mock_service = MagicMock(spec=CRUDServiceProtocol)
        mock_service.get = AsyncMock(return_value=Ok(DummyItem("123", "test")))

        controller = GenericController(service=mock_service)
        await controller.get_item("123")

        mock_service.get.assert_called_once_with("123")

    @pytest.mark.asyncio
    async def test_create_item_passes_data_to_service(self):
        mock_service = MagicMock(spec=CRUDServiceProtocol)
        mock_service.create = AsyncMock(return_value=Ok(DummyItem("1", "test")))

        controller = GenericController(service=mock_service)
        await controller.create_item({"name": "test", "email": "test@example.com"})

        mock_service.create.assert_called_once_with(
            {"name": "test", "email": "test@example.com"}
        )
