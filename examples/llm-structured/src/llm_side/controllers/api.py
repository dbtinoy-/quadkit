"""Convention followed: **Controller pattern** — thin HTTP shell delegating to
``TicketExtractionService`` and returning ``Result`` values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions import ValidationError
from quadkit.result import Result
from quadkit.web import Controller, body, get, post

if TYPE_CHECKING:
    from llm_side.services.extractor import TicketExtractionService


class TicketExtractionController(Controller):
    """Describe the demo, extract structured ticket briefs, and report stats."""

    prefix = "/"

    def __init__(self, service: TicketExtractionService | None = None) -> None:
        self._service = service

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe the LLM Structured Output demo surface."""
        return {
            "demo": "llm-structured",
            "summary": "Structured DomainModel extraction, LLMCache, and cost tracking on quadkit-ai-llm.",
            "endpoints": ["POST /extract", "GET /stats"],
        }

    @post("/extract")
    async def extract(
        self, payload: dict[str, Any] = body()
    ) -> Result[dict[str, Any], ValidationError]:
        """Extract a validated ``TicketBrief`` from ``{"text": "..."}``."""
        assert self._service is not None
        text = str(payload.get("text", "")) if isinstance(payload, dict) else ""
        return await self._service.extract(text)

    @get("/stats")
    async def stats(self) -> dict[str, Any]:
        """Return ``LLMCache`` hit/miss counters and cumulative USD cost."""
        assert self._service is not None
        return self._service.stats()


__all__ = ["TicketExtractionController"]
