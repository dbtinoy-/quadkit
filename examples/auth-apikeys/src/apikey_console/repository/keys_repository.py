"""Dict-backed API-key repository for the demo."""
# Repository pattern — implements APIKeyRepositoryProtocol
# from quadkit-contracts. This is the in-memory demo adapter; swap
# for a database-backed implementation in production.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from quadkit.contracts.auth import APIKeyRepositoryProtocol
from quadkit.primitives import clock


def _utc_now() -> datetime:
    return clock.now()


@dataclass
class InMemoryAPIKeyRepository(APIKeyRepositoryProtocol):
    """Process-local API-key store implementing the persistence contract.

    Rows keep ``revoked: bool`` (default False) and whatever payload fields
    the manager supplied (name, key_hash, prefix, user_id, scopes,
    expires_at, created_at, updated_at).
    """

    # Protocol-based design — the class implements the
    # protocol from contracts, not a base class. Framework code resolves
    # APIKeyRepositoryProtocol; this concrete class is registered in
    # the DI container.

    _rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    _seq: int = 0

    async def insert(self, payload: dict[str, Any]) -> str:
        self._seq += 1
        key_id = f"key-{self._seq}"
        row = dict(payload)
        row.setdefault("id", key_id)
        row.setdefault("revoked", False)
        row.setdefault("created_at", _utc_now())
        row.setdefault("updated_at", _utc_now())
        self._rows[key_id] = row
        return key_id

    async def find_by_prefix(self, prefix: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self._rows.values()
            if not row.get("revoked") and row.get("prefix") == prefix
        ]

    async def find_by_user(self, user_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self._rows.values()
            if row.get("user_id") == user_id and not row.get("revoked")
        ]

    async def update_last_used(self, key_id: str, ip_address: str | None) -> None:
        row = self._rows.get(key_id)
        if row is not None:
            row["last_used_at"] = "just-now"
            row["last_used_ip"] = ip_address

    async def revoke(self, key_id: str) -> bool:
        """Mark a key revoked; return False when the id is unknown."""
        row = self._rows.get(key_id)
        if row is None or row.get("revoked"):
            return False
        row["revoked"] = True
        return True


__all__ = ["InMemoryAPIKeyRepository"]
