"""Row-level security mixin for ``SQLRepository``.

Intercepts ``_apply_rls_to_query`` calls from ``_ReadMixin`` and
``_WriteMixin`` to inject the active scope predicate produced by
``RowLevelSecurityPolicy``.

The mixin is **pure query manipulation** — it does not touch the database
or manage context-var state.  State management lives in
:mod:`quadkit.sql.row_level_security`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.sql.row_level_security import RowLevelSecurityPolicy


class _RLSMixin:
    """Applied to ``SQLRepository`` when an ``rls_policy`` is provided.

    Repositories that do *not* supply ``rls_policy`` at construction time
    inherit only a no-op stub from ``_NoRLSMixin``, preserving full backward
    compatibility.
    """

    # Set by SQLRepository.__init__ after calling super().__init__()
    _rls_policy: RowLevelSecurityPolicy | None

    def _rls_apply(
        self,
        query: str,
        params: list[Any],
        operation: str,
    ) -> tuple[str, list[Any]]:
        """Inject the RLS scope predicate into *query*.

        If no policy is configured, returns the query unchanged.

        Args:
            query: The SQL string built so far (may already contain WHERE).
            params: Bind parameter list to extend in place.
            operation: SQL verb used in error messages (``"SELECT"`` etc.).

        Returns:
            ``(query, params)`` — query is extended with RLS conditions and
            params is extended with the scope values.

        Raises:
            NoSecurityPolicyError: When a policy is set but no scope is
                active and no admin bypass is in effect.
        """
        policy = getattr(self, "_rls_policy", None)
        if policy is None:
            return query, params

        table: str = getattr(self, "table_name", "unknown")
        scope = policy.require_scope(table=table, operation=operation)

        # Admin bypass → scope.values is empty, nothing to append.
        if not scope.values:
            return query, params

        parts, scope_params = scope.to_sql_fragments()
        upper_query = query.upper()
        has_where = " WHERE " in upper_query

        connector = " AND " if has_where else " WHERE "
        query = query + connector + " AND ".join(parts)
        params.extend(scope_params)
        return query, params

    def _rls_validate_insert(self, data: dict[str, Any]) -> None:
        """Validate that insert *data* carries all required scope columns.

        For repositories with an RLS policy, every INSERT must include a
        value for each scope column.  This prevents rows from being written
        without ownership markers.

        Args:
            data: The column→value dict that will be inserted.

        Raises:
            ValueError: If a required scope column is absent or ``None``.
        """
        policy = getattr(self, "_rls_policy", None)
        if policy is None:
            return

        # Admin bypass is allowed to insert without scope columns.
        if policy.is_admin_bypass_active():
            return

        for col in policy.columns:
            if data.get(col.name) is None:
                table: str = getattr(self, "table_name", "unknown")
                raise ValueError(
                    f"INSERT into '{table}' rejected by row-level security: "
                    f"required scope column '{col.name}' is missing or None. "
                    f"Provide a value or use with_admin_scope() for a bypass."
                )

    @asynccontextmanager
    async def with_admin_scope(self, reason: str) -> AsyncGenerator[None, None]:
        """Async context manager that bypasses RLS for the duration of the block.

        Emits a structured WARNING audit log entry (via the policy's own
        ``admin_bypass`` context manager).

        Example::

            async with repo.with_admin_scope(reason="support-ticket-99"):
                rows = await repo.find_many()

        Args:
            reason: Mandatory justification string logged for auditability.

        Yields:
            ``None`` — the body runs with RLS bypassed.

        Raises:
            RuntimeError: If the repository has no RLS policy configured.
        """
        policy = getattr(self, "_rls_policy", None)
        if policy is None:
            raise RuntimeError(
                "with_admin_scope() called on a repository that has no "
                "RowLevelSecurityPolicy configured."
            )
        table: str = getattr(self, "table_name", "unknown")
        with policy.admin_bypass(reason=reason, table=table):
            yield
