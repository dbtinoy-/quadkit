"""Convention followed: **Controller pattern** — stateless HTTP adapters; services return ``Result[T, E]``; failures map to RFC-9457 ``ProblemDetail``.

JSON controls for the Events Timeline / Replay Lab."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.result import Err, Result
from quadkit.web import Controller, get, post
from timeline_lab.services.timeline import TimelineService


class TimelineApiController(Controller):
    """Expose event publication, history, replay, and readiness controls."""

    prefix = "/api/events"

    def __init__(self, service: TimelineService | None = None) -> None:
        self._service = service

    @property
    def service(self) -> TimelineService:
        """Return the boot-wired service or fail clearly if misconfigured."""
        if self._service is None:
            raise RuntimeError("TimelineLabProvider has not wired the controller")
        return self._service

    @get("")
    async def timeline(self) -> dict[str, Any]:
        """Return the current event-store history and delivery observations."""
        return await self.service.history()

    @get("/health")
    async def health(self) -> dict[str, Any]:
        """Return offline readiness details."""
        return await self.service.health()

    @post("/publish")
    async def publish(
        self, body: dict[str, Any]
    ) -> Result[dict[str, Any], ValidationError]:
        """Append and publish one of the lab's three event actions."""
        try:
            return await self.service.publish(
                action=str(body.get("action", "")),
                note=str(body.get("note", "")),
                actor=str(body.get("actor", "")),
            )
        except ValueError as exc:
            return Err(ValidationError(str(exc)))

    @post("/replay")
    async def replay(self) -> dict[str, Any]:
        """Replay the stored event history without appending new events."""
        return await self.service.replay()


__all__ = ["TimelineApiController"]
