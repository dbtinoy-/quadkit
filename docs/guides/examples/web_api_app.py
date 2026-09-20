"""Runnable companion to docs/guides/web-api.md.

The full notes API used by the guide: typed route parameters, query
binding, a validated pydantic request body, and responses derived from
the return value. Run the tests from this directory:

    pytest test_web_api_app.py
"""

from pydantic import BaseModel

from quadkit import Application
from quadkit.web import Controller, WebModule, body, get, path, post, query


class NoteIn(BaseModel):
    """Request body for creating a note; validated before the route runs."""

    title: str
    body: str = ""


_NOTES: dict[int, dict] = {1: {"title": "first", "body": "shipped with the app"}}


class NotesController(Controller):
    @get("/notes/{note_id}")
    async def read_note(self, note_id: int, verbose: bool = False) -> dict:
        """``{note_id}`` binds by name and validates as ``int``.

        Plain keyword arguments bind from the query string by name.
        """
        if note_id not in _NOTES:
            return {}  # kept simple here; real 404s: see error-handling.md
        return {"id": note_id, "verbose": verbose, **_NOTES[note_id]}

    @get("/notes")
    async def list_notes(self, limit: int = 10) -> dict:
        """Query parameters convert to the annotated type (``int``)."""
        items = [{"id": k, **v} for k, v in sorted(_NOTES.items())][:limit]
        return {"count": len(items), "items": items}

    @post("/notes", status_code=201)
    async def create_note(self, payload: NoteIn = body()) -> dict:
        """``body()`` binds the whole request body to a pydantic model."""
        new_id = max(_NOTES, default=0) + 1
        _NOTES[new_id] = payload.model_dump()
        return {"id": new_id, **payload.model_dump()}


def create_app() -> Application:
    """Assemble the application from the web module and one controller."""
    app = Application()
    app.add_modules([WebModule.configure(controllers=[NotesController])])
    return app


app = create_app()
