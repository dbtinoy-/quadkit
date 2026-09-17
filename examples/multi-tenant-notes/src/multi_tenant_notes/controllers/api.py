"""Convention followed: **Controller pattern** — stateless HTTP adapters;
expected failures are ``Err(domain error)`` values rendered as RFC-9457
``ProblemDetail`` by the Result bridge. ``NotFoundError`` → 404 and
``ConflictError`` → 409 are built-in mappings; the demo's own
``MissingTenantError`` (a request-shape fault, not a domain rule) is
registered here → 400.

Note: every name used in handler annotations must be importable at
runtime (no ``TYPE_CHECKING``-only imports) — the request binder resolves
annotations with ``get_type_hints`` to decide which parameters are body,
path, query, or DI.
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request

from multi_tenant_notes.services.notes import MissingTenantError, NotesStore
from quadkit.contracts.exceptions import ConflictError, NotFoundError
from quadkit.result import Err, Ok, Result
from quadkit.web import Controller, body, get, post
from quadkit.web.routing.result_bridge import ResultResponseMapper

# Request-shape fault: no tenant header means the request is malformed
# for this API (400), which is a different contract from domain rules.
ResultResponseMapper.register(MissingTenantError, 400)


def require_tenant(request: Request) -> Result[str, MissingTenantError]:
    """Return the request's tenant id as ``Ok``, or the 400 problem as ``Err``."""
    tenant = request.headers.get("x-tenant-id", "").strip()
    if not tenant:
        return Err(MissingTenantError("X-Tenant-Id header is required"))
    return Ok(tenant)


class NotesController(Controller):
    """Notes CRUD, scoped to the calling tenant by construction."""

    prefix = "/"

    def __init__(self, store: NotesStore | None = None) -> None:
        self._store = store

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe this demo's surface (the hub mounts it at ``/examples/<slug>/``)."""
        return {
            "demo": "multi-tenant-notes",
            "summary": "Per-tenant data isolation keyed on X-Tenant-Id.",
            "endpoints": ["POST /notes", "GET /notes", "GET /notes/{note_id}"],
        }

    @post("/notes", status_code=201)
    async def create(
        self, request: Request, payload: dict = body()
    ) -> Result[dict[str, Any], ConflictError | MissingTenantError]:
        """Create a note in the calling tenant's partition."""
        tenant = require_tenant(request)
        if tenant.is_err():
            return tenant
        return self._store.create(tenant.unwrap(), str(payload.get("text", "")))

    @get("/notes")
    async def list_all(
        self, request: Request
    ) -> Result[dict[str, Any], MissingTenantError]:
        """Return the calling tenant's notes."""
        tenant = require_tenant(request)
        if tenant.is_err():
            return tenant
        return Ok({"notes": self._store.list(tenant.unwrap())})

    @get("/notes/{note_id}")
    async def get_one(
        self, request: Request, note_id: int
    ) -> Result[dict[str, Any], NotFoundError | MissingTenantError]:
        """Return one of the calling tenant's notes — never another tenant's."""
        tenant = require_tenant(request)
        if tenant.is_err():
            return tenant
        note = self._store.get(tenant.unwrap(), note_id)
        if note is None:
            return Err(NotFoundError("note not found"))
        return Ok(note)


__all__ = ["NotesController"]
