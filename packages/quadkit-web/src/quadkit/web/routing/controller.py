"""Web controllers and routing utilities."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar

from quadkit.contracts.exceptions.domain import DomainError
from quadkit.contracts.web.protocols import CRUDServiceProtocol
from quadkit.logging import get_logger
from quadkit.result import Ok, Result
from quadkit.web.exceptions import (
    NotFoundError,
)
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.decorators import (
    delete,
    get,
    head,
    options,
    patch,
    post,
    put,
)
from quadkit.web.transport.responses import json_response

T = TypeVar("T")
R = TypeVar("R", bound=Callable[..., Any])


class GenericController(Controller, Generic[T]):
    """Generic controller with common CRUD patterns for any service.

    Returns ``Result[T, DomainError]`` from all action methods.  The
    ``ResponseSerializer`` in the request pipeline automatically maps:

    - ``Ok(value)``  → 200 JSON response (201 for ``create_item``).
    - ``Err(error)`` → HTTP error via ``ResultResponseMapper``.

    Use ``@error_status`` to control the HTTP status code a domain error
    maps to; the decorator registers the mapping, using the decorated
    controller as the decoration target::

        from quadkit.web import error_status

        @error_status(ItemNotFound, 404)
        class ItemsController(Controller): ...
    """

    def __init__(
        self,
        service: CRUDServiceProtocol[T],
        resource_name: str | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self._resource_name = resource_name or self._get_default_resource_name()
        self._logger = get_logger(self.__class__.__name__)

    def _get_default_resource_name(self) -> str:
        """Get default resource name from class name."""
        return (
            self.__class__.__name__.lower().replace("controller", "").replace("v1", "")
        )

    @property
    def resource_name(self) -> str:
        """Get the resource name for permissions and error messages."""
        return self._resource_name

    @property
    def logger(self) -> Any:
        """Get the logger for this controller."""
        return self._logger

    @get("/")
    async def list_items(
        self,
        limit: int = 20,
        offset: int = 0,
        **filters: Any,
    ) -> Result[dict[str, Any], DomainError]:
        """List items with pagination.

        Returns a ``Result`` whose ``Ok`` payload is a dict with keys
        ``items``, ``limit``, ``offset``, and ``total``.
        """
        result = await self.service.list_items(limit=limit, offset=offset, **filters)
        if not result.is_ok():
            return result  # type: ignore[return-value]
        items = result.unwrap()
        return Ok(
            {
                "items": items,
                "limit": limit,
                "offset": offset,
                "total": len(items),
            }
        )

    @get("/{item_id}")
    async def get_item(self, item_id: str) -> Result[T, DomainError]:
        """Get single item by ID."""
        result = await self.service.get(item_id)
        if not result.is_ok():
            return result  # type: ignore[return-value]
        item = result.unwrap()
        if not item:
            raise NotFoundError(f"{self.resource_name.title()} not found")
        return Ok(item)

    @post("/")
    async def create_item(self, data: dict[str, Any]) -> Any:
        """Create new item (returns 201 on success)."""
        result = await self.service.create(data)
        if not result.is_ok():
            return result
        return json_response(result.unwrap(), status_code=201)

    @put("/{item_id}")
    async def update_item(
        self, item_id: str, data: dict[str, Any]
    ) -> Result[T, DomainError]:
        """Update existing item."""
        result = await self.service.update(item_id, data)
        if not result.is_ok():
            return result  # type: ignore[return-value]
        item = result.unwrap()
        if not item:
            raise NotFoundError(f"{self.resource_name.title()} not found")
        return Ok(item)

    @delete("/{item_id}")
    async def delete_item(self, item_id: str) -> Any:
        """Delete item (returns 204 on success)."""
        result = await self.service.delete(item_id)
        if not result.is_ok():
            return result
        if not result.unwrap():
            raise NotFoundError(f"{self.resource_name.title()} not found")
        return json_response({}, status_code=204)


__all__ = [
    "CRUDServiceProtocol",
    "Controller",
    "GenericController",
    "T",
    "delete",
    "get",
    "head",
    "options",
    "patch",
    "post",
    "put",
]
