"""Audit mixin for repositories"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.audit import AuditEntry
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.audit import AuditLoggerProtocol
    from quadkit.sql.context import DbContext

logger = get_logger(__name__)


class AuditRepositoryMixin:
    """
    Mixin to add audit capabilities to repositories

    Automatically logs all changes made through the repository.
    """

    def __init__(
        self,
        *args: Any,
        audit_logger: AuditLoggerProtocol | None = None,
        db_ctx: DbContext | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.audit_logger = audit_logger
        self._db_ctx = db_ctx

    def _get_current_user(self) -> str | None:
        """Get the current user ID for audit logging."""
        if self._db_ctx is not None:
            return self._db_ctx.user_id
        return None

    async def _log_change(
        self,
        entity: Any,
        action: str,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
    ) -> None:
        """Log a change to the audit log"""
        if not self.audit_logger:
            return

        try:
            entity_id = getattr(entity, self.key_field, None)  # type: ignore[attr-defined]
            if entity_id is None:
                return

            entry = AuditEntry(
                action=action,
                actor_id=self._get_current_user() or "",
                resource_type=self.table_name,  # type: ignore[attr-defined]
                resource_id=str(entity_id),
                old_values=old_values,
                new_values=new_values,
                source="sql",
            )

            await self.audit_logger.log(entry)

        except Exception:  # noqa: BLE001 — audit logging must gracefully degrade without failing primary operation
            # Don't fail the operation if audit logging fails
            logger.exception("Audit logging failed")

    async def create(self, entity: Any) -> Any:
        """Create with audit logging"""
        old_values: dict[str, Any] = {}
        result = await super().create(entity)  # type: ignore[misc]
        new_values = self._entity_to_dict(entity)  # type: ignore[attr-defined]  # type: ignore[attr-defined]
        await self._log_change(entity, "INSERT", old_values, new_values)
        return result

    async def update(self, entity: Any) -> Any:
        """Update with audit logging"""
        # Get current state
        entity_id = getattr(entity, self.key_field, None)  # type: ignore[attr-defined]
        existing = await self.find_by_id(entity_id) if entity_id else None  # type: ignore[attr-defined]
        old_values = self._entity_to_dict(existing) if existing else {}  # type: ignore[attr-defined]

        result = await super().update(entity)  # type: ignore[misc]
        new_values: dict[str, Any] = self._entity_to_dict(entity)  # type: ignore[attr-defined]  # type: ignore[attr-defined]
        await self._log_change(entity, "UPDATE", old_values, new_values)
        return result

    async def delete(self, key: Any) -> Any:
        """Delete with audit logging"""
        # Get current state
        existing = await self.find_by_id(key)  # type: ignore[attr-defined]
        old_values = self._entity_to_dict(existing) if existing else {}  # type: ignore[attr-defined]
        new_values: dict[str, Any] = {}

        result = await super().delete(key)  # type: ignore[misc]
        if result and existing:
            await self._log_change(existing, "DELETE", old_values, new_values)
        # Debug: ensure delete result is returned as expected
        logger.debug("AuditRepositoryMixin.delete result=%s", result)
        return result
