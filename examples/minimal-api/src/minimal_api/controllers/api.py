"""Convention followed: **Controller pattern** — stateless HTTP adapters.
The provider constructs the controller at boot with its dependencies and
rebinds it in the container; handlers stay trivial. This demo has no
fallible domain logic, so its handlers return plain dicts; the moment a
handler can fail it returns ``Result[T, E]`` and the failure renders as
RFC-9457 ``ProblemDetail`` (see the other starter templates for that
shape).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.web import Controller, body, get, post

if TYPE_CHECKING:
    from minimal_api.config import MinimalApiConfig


class HelloController(Controller):
    """Two routes: a configured greeting and an echo. That is the whole service."""

    prefix = "/"

    def __init__(self, config: MinimalApiConfig | None = None) -> None:
        self._config = config

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe this demo's surface (the hub mounts it at ``/examples/<slug>/``)."""
        return {
            "demo": "minimal-api",
            "summary": "Smallest Quadkit web service: one GET, one POST.",
            "endpoints": ["GET /hello", "POST /echo"],
        }

    @get("/hello")
    async def hello(self) -> dict[str, Any]:
        """Return the greeting configured in ``minimal_api.greeting``."""
        return {"message": self._config.greeting if self._config else "hello, quadkit"}

    @post("/echo", status_code=201)
    async def echo(self, payload: dict = body()) -> dict[str, Any]:
        """Echo the submitted JSON body back under ``you_sent``."""
        return {"you_sent": payload}


__all__ = ["HelloController"]
