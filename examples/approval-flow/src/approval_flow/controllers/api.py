"""Convention followed: **Controller pattern** — stateless HTTP adapters; services return ``Result[T, E]``; failures map to RFC-9457 ``ProblemDetail``.

Browser API for the focused Quadkit workflow demo.

Error paths return ``Err(...)`` instead of 200-with-``error`` dicts; the web
pipeline renders ProblemDetail bodies:

- ``Err(ValidationError)`` → 422 (framework default)
- ``Err(StateError)``      → 409 (StateError extends the contracts
  ``ConflictError``, which the framework maps to 409 out of the box)
"""

from __future__ import annotations

from typing import Any

from approval_flow.services.flow import ApprovalFlowService
from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.result import Err, Result
from quadkit.web import Controller, get, post
from quadkit.workflow.state import StateError


class ApprovalFlowApiController(Controller):
    """Expose state-machine controls without leaking workflow internals."""

    prefix = "/api/workflow"

    def __init__(self, service: ApprovalFlowService | None = None) -> None:
        self._service = service

    @get("")
    async def snapshot(self) -> dict[str, Any]:
        """Return the current workflow state, available events, and history."""
        return self._service.snapshot()

    @post("/request")
    async def request(
        self, body: dict[str, Any]
    ) -> Result[dict[str, Any], ValidationError]:
        """Create a new approval request from title, amount, and owner."""
        try:
            return await self._service.create_request(
                str(body.get("title", "")),
                int(body.get("amount", 0)),
                str(body.get("owner", "Requester")),
            )
        except (TypeError, ValueError) as exc:
            return Err(ValidationError(str(exc)))

    @post("/transition")
    async def transition(
        self, body: dict[str, Any]
    ) -> Result[dict[str, Any], StateError | ValidationError]:
        """Advance the workflow by applying an event as the given actor."""
        try:
            return await self._service.transition(
                str(body.get("event", "")), str(body.get("actor", "operator"))
            )
        except StateError as exc:  # illegal transition for the current state
            return Err(exc)
        except (TypeError, ValueError) as exc:
            return Err(ValidationError(str(exc)))

    @post("/policy")
    async def policy(self, body: dict[str, Any]) -> dict[str, Any]:
        """Preview approval-chain outcome without mutating workflow state."""
        return await self._service.policy_preview(
            manager_approved=body.get("manager_approved") is not False,
            finance_approved=body.get("finance_approved") is not False,
        )

    @post("/retry")
    async def retry(
        self, body: dict[str, Any]
    ) -> Result[dict[str, Any], StateError | ValidationError]:
        """Retry a rejected request by re-entering manager review."""
        return await self.transition(
            {"event": "retry", "actor": body.get("actor", "operator")}
        )


__all__ = ["ApprovalFlowApiController"]
