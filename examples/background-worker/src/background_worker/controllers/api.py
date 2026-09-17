"""Convention followed: **Controller pattern** — stateless HTTP adapters.
This controller has no fallible path (submit always accepts, stats always
totals), so its handlers return plain dicts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.web import Controller, body, get, post

if TYPE_CHECKING:
    from background_worker.services.worker import TaskQueue


class WorkController(Controller):
    """HTTP facet over the work queue: submit and observe."""

    prefix = "/"

    def __init__(self, queue: TaskQueue | None = None) -> None:
        self._queue = queue

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe this demo's surface (the hub mounts it at ``/examples/<slug>/``)."""
        return {
            "demo": "background-worker",
            "summary": "Long-running work off the request path, with counters.",
            "endpoints": ["POST /tasks", "GET /stats"],
        }

    @post("/tasks", status_code=202)
    async def submit(self, payload: dict = body()) -> dict[str, Any]:
        """Accept a unit of work for off-request processing."""
        self._queue.submit(payload)
        return {"accepted": True, "pending": self._queue.pending()}

    @get("/stats")
    async def stats(self) -> dict[str, Any]:
        """Return queue counters: enqueued, processed, failed, pending."""
        return {
            "enqueued": self._queue.enqueued,
            "processed": self._queue.processed,
            "failed": self._queue.failed,
            "pending": self._queue.pending(),
        }


__all__ = ["WorkController"]
