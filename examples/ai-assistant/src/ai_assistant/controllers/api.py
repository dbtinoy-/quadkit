"""Convention followed: **Controller pattern** — stateless HTTP adapters;
expected failures are ``Err(domain error)`` values rendered as RFC-9457
``ProblemDetail`` by the Result bridge (``ValidationError`` → 422 is a
built-in mapping; no registration needed).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions import ValidationError
from quadkit.result import Err, Ok, Result
from quadkit.web import Controller, body, get, post

if TYPE_CHECKING:
    from ai_assistant.services.client import AssistantClient


class ChatController(Controller):
    """One route: turn a user message (plus history) into an answer."""

    prefix = "/"

    def __init__(self, assistant: AssistantClient | None = None) -> None:
        self._assistant = assistant

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe this demo's surface (the hub mounts it at ``/examples/<slug>/``)."""
        return {
            "demo": "ai-assistant",
            "summary": "External-integration seam: chat completions behind a protocol.",
            "endpoints": ["POST /chat"],
        }

    @post("/chat", status_code=201)
    async def chat(
        self, payload: dict = body()
    ) -> Result[dict[str, Any], ValidationError]:
        """Answer a chat message; a blank message is a 422 problem."""
        message = str(payload.get("message", "")).strip()
        if not message:
            return Err(ValidationError("message is required"))
        history = list(payload.get("history") or [])
        answer = await self._assistant.complete(
            [*history, {"role": "user", "content": message}]
        )
        return Ok({"answer": answer})


__all__ = ["ChatController"]
