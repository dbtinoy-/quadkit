"""Convention followed: **Service pattern** — domain state and rules behind
a service class, returning ``Result[T, E]`` for expected failures; no HTTP
knowledge lives here.

In-memory notes, partitioned by tenant id, for the Multi-Tenant Notes
demo. Every store operation is keyed by tenant, so cross-tenant reads are
impossible by construction (not by convention). Swap this for a
tenant-scoped repository in production.
"""

from __future__ import annotations

import itertools
from typing import Any

from quadkit.contracts.exceptions import ConflictError
from quadkit.result import Err, Ok, Result


class MissingTenantError(Exception):
    """Raised when a request carries no ``X-Tenant-Id`` header."""


class NotesStore:
    """Tenant-partitioned in-memory notes."""

    def __init__(self, max_notes_per_tenant: int = 0) -> None:
        self._ids = itertools.count(1)
        self._notes: dict[str, dict[int, dict[str, Any]]] = {}
        self.max_notes_per_tenant = max_notes_per_tenant

    def create(self, tenant: str, text: str) -> Result[dict[str, Any], ConflictError]:
        """Create a note for ``tenant``; a configured cap may refuse."""
        bucket = self._notes.setdefault(tenant, {})
        if self.max_notes_per_tenant and len(bucket) >= self.max_notes_per_tenant:
            return Err(
                ConflictError(
                    f"tenant '{tenant}' reached its note cap "
                    f"({self.max_notes_per_tenant})"
                )
            )
        note = {"id": next(self._ids), "text": text}
        bucket[note["id"]] = note
        return Ok(note)

    def list(self, tenant: str) -> list[dict[str, Any]]:
        """Return the tenant's notes (insertion order)."""
        return list(self._notes.get(tenant, {}).values())

    def get(self, tenant: str, note_id: int) -> dict[str, Any] | None:
        """Return one of the tenant's notes, or ``None`` — never another tenant's."""
        return self._notes.get(tenant, {}).get(note_id)


__all__ = ["MissingTenantError", "NotesStore"]
