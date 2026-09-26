"""Dict-backed session storage for the demo's cookie sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from quadkit.contracts.auth import SessionRepositoryProtocol
from quadkit.primitives import clock


@dataclass
class InMemorySessionRepository(SessionRepositoryProtocol):
    """Process-local session store implementing the storage contract.

    Rows expire by ``expires_at`` and deactivate via ``active=False``.
    Not thread-safe by design: single event loop, single process.
    """

    _rows: dict[str, dict] = field(default_factory=dict)

    async def insert(self, payload: dict) -> None:
        row = dict(payload)
        row.setdefault("active", True)
        row.setdefault("created_at", clock.now())
        row.setdefault("last_active_at", row["created_at"])
        self._rows[row["session_id"]] = row

    async def find_active(self, session_id: str) -> dict | None:
        row = self._rows.get(session_id)
        if row is None or not row.get("active"):
            return None
        if row.get("expires_at") and row["expires_at"] <= clock.now():
            return None
        return row

    async def find_active_by_user(self, user_id: str, cutoff: datetime) -> list[dict]:
        active = [
            row
            for row in self._rows.values()
            if row.get("user_id") == user_id
            and row.get("active")
            and row.get("expires_at")
            and row["expires_at"] > cutoff
        ]
        return sorted(
            active,
            key=lambda r: r.get("last_active_at") or r["created_at"],
            reverse=True,
        )

    async def revoke(self, session_id: str) -> None:
        row = self._rows.get(session_id)
        if row is not None:
            row["active"] = False

    async def revoke_all(self, user_id: str) -> None:
        for row in self._rows.values():
            if row.get("user_id") == user_id:
                row["active"] = False

    async def update_activity(self, session_id: str, now: datetime) -> None:
        row = self._rows.get(session_id)
        if row is not None:
            row["last_active_at"] = now


__all__ = ["InMemorySessionRepository"]
