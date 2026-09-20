"""Feature tour: CRUD endpoints without handler code.

Implement `CRUDServiceProtocol` — five async methods returning `Result`s —
and hand the service to a `GenericController` subclass. List/get/create/
update/delete routes appear at the controller's `prefix`, complete with
pagination keys, 201/204 statuses, 404 translation, and the framework's
`Result` → HTTP mapping already inside.
"""

from typing import Any

import pytest

from quadkit import Application, DomainError, Ok, Provider, Result
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.testing import WebTestBed
from quadkit.web import GenericController, WebModule
from quadkit.web.config.top_level import SecurityConfig, WebConfig

Store = dict[str, dict[str, Any]]


class NoteService:
    """In-memory CRUD service — the protocol is the only contract."""

    def __init__(self) -> None:
        self._rows: Store = {}
        self._next = 0

    async def list_items(
        self, limit: int = 20, offset: int = 0, **filters: Any
    ) -> Result[list[dict[str, Any]], DomainError]:
        rows = list(self._rows.values())
        return Ok(rows[offset : offset + limit])

    async def get(self, item_id: Any) -> Result[dict[str, Any] | None, DomainError]:
        return Ok(self._rows.get(str(item_id)))

    async def create(self, data: dict[str, Any]) -> Result[dict[str, Any], DomainError]:
        self._next += 1
        row = {"id": str(self._next), **data}
        self._rows[row["id"]] = row
        return Ok(row)

    async def update(
        self, item_id: Any, data: dict[str, Any]
    ) -> Result[dict[str, Any] | None, DomainError]:
        row = self._rows.get(str(item_id))
        if row is None:
            return Ok(None)
        row.update(data)
        return Ok(row)

    async def delete(self, item_id: Any) -> Result[bool, DomainError]:
        return Ok(self._rows.pop(str(item_id), None) is not None)


class NotesController(GenericController[dict[str, Any]]):
    prefix = "/notes"

    def __init__(self, service: NoteService) -> None:
        super().__init__(service, resource_name="note")


class NotesProvider(Provider):
    """Registration is explicit: one singleton per app lifetime."""

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(NoteService, NoteService())


def create_app() -> Application:
    app = Application()
    app.add_provider(NotesProvider())
    app.add_module(
        WebModule.configure(
            controllers=[NotesController],
            web_config=WebConfig(security=SecurityConfig(enable_csrf=False)),
        )
    )
    return app


@pytest.mark.asyncio
async def test_full_crud_roundtrip_without_handlers() -> None:
    async with WebTestBed(create_app()) as bed:
        created = bed.post("/notes/", json={"title": "ship wave 3"})
        assert created.status_code == 201
        assert created.json["id"] == "1"

        fetched = bed.get("/notes/1")
        assert fetched.status_code == 200
        assert fetched.json["title"] == "ship wave 3"

        updated = bed.put("/notes/1", json={"title": "shipped"})
        assert updated.status_code == 200
        assert updated.json["title"] == "shipped"

        listed = bed.get("/notes/")
        assert listed.status_code == 200
        assert listed.json["total"] == 1
        assert [row["title"] for row in listed.json["items"]] == ["shipped"]

        assert bed.delete("/notes/1").status_code == 204
        assert bed.get("/notes/1").status_code == 404
