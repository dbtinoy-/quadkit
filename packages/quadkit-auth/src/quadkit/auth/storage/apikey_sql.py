"""SQL-backed implementation of APIKeyRepositoryProtocol.

This is the only module in ``quadkit-auth`` allowed to issue raw SQL for
API key persistence.  All callers depend on the ``APIKeyRepositoryProtocol`` protocol
from ``quadkit-contracts`` — never on this concrete class directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol

logger = get_logger(__name__)


class APIKeySqlRepository:
    """SQL-backed repository for API key persistence.

    Wraps a ``DatabaseProviderProtocol`` and implements the ``APIKeyRepositoryProtocol``
    protocol so it can be injected wherever that protocol is required.

    All raw SQL lives here; nothing outside this module constructs queries for
    the ``api_keys`` table.
    """

    _TABLE = "api_keys"

    def __init__(self, db_provider: DatabaseProviderProtocol) -> None:
        """Initialise with a resolved database provider.

        Args:
            db_provider: Framework database provider that exposes
                ``execute_insert``, ``execute_query``, and ``execute_sql``.
        """
        self._db = db_provider

    async def insert(self, payload: dict[str, Any]) -> str:
        """Persist a new API key row and return the generated key_id.

        Args:
            payload: Field/value mapping (name, key_hash, prefix, user_id,
                scopes, expires_at, …).  When the payload carries no ``id``,
                one is generated here so rows are addressable by the
                returned key id (mirrors the in-memory repository contract).

        Returns:
            The opaque key identifier for the new row.
        """
        row = dict(payload)
        row.setdefault("id", str(uuid.uuid4()))
        await self._db.execute_insert(self._TABLE, row)
        return str(row["id"])

    async def find_by_prefix(self, prefix: str) -> list[dict[str, Any]]:
        """Return all active (non-revoked) rows matching the display prefix.

        Args:
            prefix: Short display prefix used for fast pre-filtering.

        Returns:
            List of row dicts; empty when nothing matches.
        """
        sql = f"SELECT * FROM {self._TABLE} WHERE prefix = ? AND revoked_at IS NULL"  # noqa: S608 — table name is constant class attr "api_keys", never user input
        result = await self._db.execute_query(sql, [prefix])
        return list(result.rows)

    async def update_last_used(self, key_id: str, ip_address: str | None) -> None:
        """Refresh the ``last_used_at`` timestamp and originating IP.

        Args:
            key_id: Target key identifier.
            ip_address: Caller IP, or ``None`` when unavailable.
        """
        sql = (
            f"UPDATE {self._TABLE} "  # noqa: S608 — table name is constant class attr "api_keys", never user input
            "SET last_used_at = CURRENT_TIMESTAMP, last_used_ip = ? "
            "WHERE id = ?"
        )
        await self._db.execute(sql, [ip_address, key_id])

    async def revoke(self, key_id: str) -> None:
        """Mark a key as permanently revoked.

        Args:
            key_id: Target key identifier.
        """
        sql = (
            f"UPDATE {self._TABLE} "  # noqa: S608 — table name is constant class attr "api_keys", never user input
            "SET revoked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?"
        )
        await self._db.execute(sql, [key_id])

    async def find_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Return all active (non-revoked) keys owned by a user.

        Args:
            user_id: Owner identifier.

        Returns:
            List of row dicts; empty when nothing matches.
        """
        sql = f"SELECT * FROM {self._TABLE} WHERE user_id = ? AND revoked_at IS NULL"  # noqa: S608 — table name is constant class attr "api_keys", never user input
        result = await self._db.execute_query(sql, [user_id])
        return list(result.rows)


__all__ = [
    "APIKeySqlRepository",
    "logger",
]
