"""Feature tour: CQRS endpoints dispatch through protocol buses.

`CQRSController` subclasses don't call services directly — they hand
commands to `dispatch_command` and queries to `dispatch_query`, and the
work travels over whatever `CommandBusProtocol` / `QueryBusProtocol`
implementation the app wires in. The framework ships the dispatch
points; the bus itself is yours (in-memory, outbox, remote — anything
with `dispatch`/`execute`). Here two tiny type-keyed buses keep notes
in a dict, are registered as DI singletons, and are injected into the
controller by constructor, exactly like any other service. A controller
built without buses fails loudly with the registration hint.
"""

import itertools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest
from starlette.requests import Request

from quadkit import Application, Provider
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.testing import WebTestBed
from quadkit.web import CQRSController, JSONResponse, WebModule, get, post
from quadkit.web.config.top_level import SecurityConfig, WebConfig

Store = dict[str, dict[str, str]]
Handler = Callable[[Any], Awaitable[Any]]


@dataclass(frozen=True)
class AddNote:
    text: str


@dataclass(frozen=True)
class FindNote:
    note_id: str


class _TypeKeyedBus:
    """Handlers keyed by message type; `seen` proves dispatch happened."""

    def __init__(self) -> None:
        self._handlers: dict[type, Handler] = {}
        self.seen: list[str] = []

    def register(self, message_type: type, handler: Handler) -> None:
        self._handlers[message_type] = handler


class InMemoryCommandBus(_TypeKeyedBus):
    """Satisfies `CommandBusProtocol`: `dispatch` routes the command."""

    async def dispatch(self, command: Any) -> Any:
        self.seen.append(type(command).__name__)
        return await self._handlers[type(command)](command)


class InMemoryQueryBus(_TypeKeyedBus):
    """Satisfies `QueryBusProtocol`: `execute` routes the query."""

    async def execute(self, query: Any) -> Any:
        self.seen.append(type(query).__name__)
        return await self._handlers[type(query)](query)


class NotesController(CQRSController):
    def __init__(
        self, command_bus: InMemoryCommandBus, query_bus: InMemoryQueryBus
    ) -> None:
        super().__init__(command_bus=command_bus, query_bus=query_bus)

    @post("/notes")
    async def add(self, request: Request) -> JSONResponse:
        data = await request.json()
        created = await self.dispatch_command(AddNote(text=data["text"]))
        return JSONResponse(created, status_code=201)

    @get("/notes/{note_id}")
    async def find(self, note_id: str) -> dict[str, str]:
        return await self.dispatch_query(FindNote(note_id=note_id))


class NotesBusProvider(Provider):
    """Both buses are singletons: one registry each per app lifetime."""

    def __init__(
        self, command_bus: InMemoryCommandBus, query_bus: InMemoryQueryBus
    ) -> None:
        super().__init__(name="notes-bus")
        self._command_bus = command_bus
        self._query_bus = query_bus

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(InMemoryCommandBus, self._command_bus)
        container.singleton(InMemoryQueryBus, self._query_bus)


def build() -> tuple[Application, InMemoryCommandBus, InMemoryQueryBus]:
    store: Store = {}
    ids = itertools.count(1)
    command_bus, query_bus = InMemoryCommandBus(), InMemoryQueryBus()

    async def add_note(command: AddNote) -> dict[str, str]:
        note_id = str(next(ids))
        store[note_id] = {"id": note_id, "text": command.text}
        return store[note_id]

    async def find_note(query: FindNote) -> dict[str, str]:
        return store[query.note_id]

    command_bus.register(AddNote, add_note)
    query_bus.register(FindNote, find_note)

    app = Application()
    app.add_provider(NotesBusProvider(command_bus, query_bus))
    app.add_module(
        WebModule.configure(
            controllers=[NotesController],
            web_config=WebConfig(security=SecurityConfig(enable_csrf=False)),
        )
    )
    return app, command_bus, query_bus


@pytest.mark.asyncio
async def test_command_then_query_travel_the_buses() -> None:
    app, command_bus, query_bus = build()
    async with WebTestBed(app) as bed:
        created = bed.post("/notes", json={"text": "ship it"})
        assert created.status_code == 201
        assert created.json == {"id": "1", "text": "ship it"}

        fetched = bed.get("/notes/1")
        assert fetched.status_code == 200
        assert fetched.json["text"] == "ship it"

    # The endpoint logic ran nowhere near the controller.
    assert command_bus.seen == ["AddNote"]
    assert query_bus.seen == ["FindNote"]


@pytest.mark.asyncio
async def test_missing_bus_fails_with_the_registration_hint() -> None:
    class BareController(CQRSController):
        pass

    with pytest.raises(RuntimeError, match="no CommandBusProtocol configured"):
        await BareController().dispatch_command(AddNote(text="nowhere to go"))

    with pytest.raises(RuntimeError, match="no QueryBusProtocol configured"):
        await BareController().dispatch_query(FindNote(note_id="1"))
