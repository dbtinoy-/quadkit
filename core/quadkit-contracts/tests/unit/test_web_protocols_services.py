"""CRUD service and connection-manager protocols."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.web.protocols import (
    BackgroundTaskRunnerProtocol,
    ConnectionManagerProtocol,
    CORSPolicyProtocol,
    CRUDServiceProtocol,
    CSRFProtectionProtocol,
    ExceptionFilterProtocol,
    HTTPApplicationProtocol,
    HttpRequestLoggerProtocol,
    RequestProtocol,
    ResponseProtocol,
    WebMiddlewareProtocol,
)



class TestCRUDServiceProtocol:
    """Tests for CRUDServiceProtocol."""

    @pytest.mark.asyncio
    async def test_has_list_items_method(self) -> None:
        """Test protocol has list_items async method."""

        class Service:
            async def list_items(
                self, limit: int = 20, offset: int = 0, **filters: Any
            ):
                return []

        service = Service()
        assert hasattr(service, "list_items")

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Service:
            async def list_items(self, limit: int = 20, offset: int = 0, **filters: Any):
                return []

            async def get(self, item_id: Any):
                return None

            async def create(self, data: dict[str, Any]):
                return {}

            async def update(self, item_id: Any, data: dict[str, Any]):
                return None

            async def delete(self, item_id: Any):
                return False

        assert isinstance(Service(), CRUDServiceProtocol)


class TestConnectionManagerProtocol:
    """Tests for ConnectionManagerProtocol."""

    @pytest.mark.asyncio
    async def test_has_add_remove_broadcast_methods(self) -> None:
        """Test protocol has add, remove, broadcast methods."""

        class Manager:
            async def add(self, connection: Any) -> None:
                pass

            async def remove(self, connection: Any) -> None:
                pass

            async def broadcast(self, message: Any, exclude: Any = None) -> None:
                pass

            @property
            def count(self) -> int:
                return 0

        manager = Manager()
        assert isinstance(manager, ConnectionManagerProtocol)
        assert manager.count == 0

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Manager:
            async def add(self, connection: Any) -> None:
                pass

            async def remove(self, connection: Any) -> None:
                pass

            async def broadcast(self, message: Any, exclude: Any = None) -> None:
                pass

            @property
            def count(self) -> int:
                return 0

        assert isinstance(Manager(), ConnectionManagerProtocol)
