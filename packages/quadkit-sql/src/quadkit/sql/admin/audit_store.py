"""SqlAdminAuditLogStore — SQL-backed admin audit log store.

Lives in quadkit-sql where SQLAlchemy AsyncSession is available.
Registration is opt-in: the store is only wired when the application
explicitly registers it via the extra_providers extension point.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from quadkit.contracts.admin.audit_entry import AuditEntry, AuditOutcome
from quadkit.di.decorators import inject
from quadkit.logging import get_logger
from quadkit.serialization import dumps_str

logger = get_logger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    admin_user_id TEXT NOT NULL,
    action      TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    outcome     TEXT NOT NULL,
    before_state JSONB,
    after_state  JSONB,
    correlation_id TEXT,
    request_id  TEXT,
    request_ip  TEXT,
    metadata    JSONB
)
"""

_INSERT_SQL = """
INSERT INTO admin_audit_logs
    (created_at, admin_user_id, action, resource_type, resource_id,
     outcome, before_state, after_state, correlation_id, request_id,
     request_ip, metadata)
VALUES
    (:created_at, :admin_user_id, :action, :resource_type, :resource_id,
     :outcome, :before_state, :after_state, :correlation_id, :request_id,
     :request_ip, :metadata)
"""


@inject
class SqlAdminAuditLogStore:
    """Implements AdminAuditLoggerProtocol backed by a SQL table.

    Accepts an AsyncSession injected by the DI container.  The store does
    not own the session: it executes on whatever transaction scope the
    caller has (per-request vs. singleton is determined by how the
    session is registered), and it does not commit — commit semantics
    belong to the session owner (e.g. the request pipeline or unit of
    work).  For transactional audit entries, defer writes to the UoW's
    commit via :class:`~the optional provider module`.

    Usage (opt-in at app level): register a provider that binds
    ``AdminAuditLoggerProtocol`` to this store with an injected session,
    then call ``await store.create_table()`` once at startup.
    """

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def create_table(self) -> None:
        """Create the audit log table if it does not already exist.

        Call once at application startup before accepting requests.
        """
        await self._session.execute(text(_CREATE_TABLE_SQL))
        logger.info("admin.audit_table_ensured")

    async def write(self, entry: AuditEntry) -> None:
        """Persist a fully-structured AuditEntry."""
        params: dict[str, Any] = {
            "created_at": datetime.now(UTC),
            "admin_user_id": entry.admin_user_id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "outcome": entry.outcome
            if isinstance(entry.outcome, str)
            else entry.outcome.value,
            "before_state": dumps_str(entry.before) if entry.before else None,
            "after_state": dumps_str(entry.after) if entry.after else None,
            "correlation_id": entry.correlation_id,
            "request_id": entry.request_id,
            "request_ip": entry.request_ip,
            "metadata": dumps_str(entry.metadata) if entry.metadata else None,
        }
        await self._session.execute(text(_INSERT_SQL), params)
        logger.debug(
            "admin.audit_written",
            action=entry.action,
            resource_type=entry.resource_type,
            outcome=params["outcome"],
        )

    async def log(
        self,
        action: str,
        resource_type: str,
        resource_id: Any,
        user_id: Any,
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """High-level log method — builds an AuditEntry and calls write()."""
        entry = AuditEntry(
            admin_user_id=str(user_id) if user_id is not None else "",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            outcome=AuditOutcome.SUCCESS,
            before=changes or {},
            after={},
            metadata=metadata or {},
        )
        await self.write(entry)


__all__ = ["SqlAdminAuditLogStore"]
