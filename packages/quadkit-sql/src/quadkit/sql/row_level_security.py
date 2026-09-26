"""Row-level security (RLS) policy for ``SQLRepository``.

Enforces ownership / tenant isolation at the query layer so that
individual repository callers cannot accidentally return rows belonging
to a different principal.

Design goals
------------
* **Fail-secure**: if a repository has a policy attached but the current
  execution context carries no active scope *and* no admin bypass is in
  effect, every SELECT / UPDATE / DELETE raises ``NoSecurityPolicyError``
  rather than silently returning rows.
* **Opt-in at repo level**: repositories that existed before QK-008 keep
  working unchanged — the policy only activates when a repository is
  constructed with ``rls_policy=<RowLevelSecurityPolicy>``.
* **Composable**: the policy is declared by listing which columns to scope
  on; the framework does not hard-code ``user_id`` or ``tenant_id``.
* **Bypass with audit**: ``async with repo.with_admin_scope(reason="…")``
  skips the predicate and emits a structured log event so ops can review
  cross-user/cross-tenant reads.
* **Context-var isolation**: each async Task / coroutine scope gets its
  own independent policy state via ``contextvars.ContextVar``.

Usage
-----
::

    from quadkit.sql.row_level_security import RowLevelSecurityPolicy, ScopeColumn

    policy = RowLevelSecurityPolicy(columns=[ScopeColumn(name="user_id")])

    class PetRepository(SQLRepository[Pet, str]):
        def __init__(self, provider, rls_policy):
            super().__init__(
                provider,
                table_name="pets",
                key_field="id",
                rls_policy=rls_policy,
            )
        ...

    # Per-request usage:
    with policy.activate(user_id="abc-123"):
        pets = await repo.find_many()          # WHERE user_id = 'abc-123'

    # Admin bypass (logs an audit event):
    async with repo.with_admin_scope(reason="support-export-ticket-42"):
        all_pets = await repo.find_many()      # no RLS WHERE clause appended
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import contextvars
from dataclasses import dataclass, field
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Public error
# ---------------------------------------------------------------------------


class NoSecurityPolicyError(Exception):
    """Raised when a repository with an RLS policy is queried without an
    active scope *and* no admin bypass is in effect.

    Attributes:
        table: The table that was queried.
        operation: The SQL operation attempted (``SELECT``, ``UPDATE``, etc.).
    """

    def __init__(self, table: str, operation: str) -> None:
        super().__init__(
            f"Row-level security violation: attempted {operation} on table "
            f"'{table}' without an active scope predicate. "
            f"Either activate a scope via RowLevelSecurityPolicy.activate() "
            f"or use repository.with_admin_scope(reason=...) for an explicit bypass."
        )
        self.table = table
        self.operation = operation


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScopeColumn:
    """Declares a single column that participates in the RLS predicate.

    Args:
        name: Column name in the database (e.g. ``"user_id"``).
    """

    name: str

    def where_fragment(self, param_index: int = 0) -> tuple[str, str]:
        """Return ``(sql_fragment, placeholder_name)`` for this column.

        The fragment uses a named placeholder so it can be appended as a
        raw SQL ``WHERE`` clause segment.

        Args:
            param_index: Numeric suffix for the placeholder name to avoid
                collisions when multiple scope columns are present.

        Returns:
            A 2-tuple of (``"col_name = ?"``), placeholder_key).
        """
        placeholder = f"__rls_{self.name}_{param_index}"
        return (f"{self.name} = ?", placeholder)


@dataclass(frozen=True)
class ActiveScope:
    """The resolved scope values for a single execution context.

    Created by :meth:`RowLevelSecurityPolicy.activate` and stored in the
    context-var.  The ``values`` dict maps ``ScopeColumn.name`` → value.
    """

    values: dict[str, Any] = field(default_factory=dict)

    def to_sql_fragments(self) -> tuple[list[str], list[Any]]:
        """Expand the scope into parallel lists of SQL fragments and params.

        Returns:
            ``(where_parts, params)`` where *where_parts* is a list of
            ``"col = ?"`` strings and *params* is the corresponding list of
            bind values.
        """
        parts: list[str] = []
        params: list[Any] = []
        for col_name, value in self.values.items():
            parts.append(f"{col_name} = ?")
            params.append(value)
        return parts, params


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class RowLevelSecurityPolicy:
    """Carries the column declarations and manages the context-var scope.

    Args:
        columns: One or more :class:`ScopeColumn` instances that define
            which columns are used as the scope predicate.

    The policy instance is typically a **singleton per repository class**
    registered in the DI container::

        container.register(
            RowLevelSecurityPolicy,
            lambda: RowLevelSecurityPolicy(columns=[ScopeColumn("user_id")]),
            lifetime="singleton",
        )
    """

    def __init__(self, columns: list[ScopeColumn]) -> None:
        if not columns:
            raise ValueError("RowLevelSecurityPolicy requires at least one ScopeColumn")
        self._columns = columns
        # Each policy instance owns its own context-var so independent
        # policies on different repositories don't bleed state.
        self._ctx_var: contextvars.ContextVar[ActiveScope | None] = (
            contextvars.ContextVar(
                f"rls_scope_{id(self)}",
                default=None,
            )
        )
        # Admin-bypass flag is a separate context-var so nesting works correctly.
        self._admin_var: contextvars.ContextVar[bool] = contextvars.ContextVar(
            f"rls_admin_{id(self)}",
            default=False,
        )

    @property
    def columns(self) -> list[ScopeColumn]:
        """The scope columns declared for this policy."""
        return list(self._columns)

    # ------------------------------------------------------------------
    # Scope activation (normal path)
    # ------------------------------------------------------------------

    @contextmanager
    def activate(self, **values: Any) -> Generator[None, None, None]:
        """Activate a scope for the duration of the ``with`` block.

        Pass one keyword argument per :class:`ScopeColumn`, mapping
        the column name to the principal's value::

            with policy.activate(user_id="abc-123"):
                rows = await repo.find_many()

        Args:
            **values: Column-name → value mapping.  Every column declared
                in the policy must be provided.

        Raises:
            ValueError: If a required column is missing from *values*.
        """
        declared = {col.name for col in self._columns}
        provided = set(values.keys())
        missing = declared - provided
        if missing:
            raise ValueError(
                f"RowLevelSecurityPolicy.activate() is missing values for "
                f"columns: {sorted(missing)}"
            )
        scope = ActiveScope(values={k: v for k, v in values.items() if k in declared})
        token = self._ctx_var.set(scope)
        try:
            yield
        finally:
            self._ctx_var.reset(token)

    # ------------------------------------------------------------------
    # Admin bypass (audit path)
    # ------------------------------------------------------------------

    @contextmanager
    def admin_bypass(self, *, reason: str, table: str) -> Generator[None, None, None]:
        """Bypass the RLS predicate for the duration of the ``with`` block.

        Emits a structured WARNING log event so the bypass is auditable.
        The *reason* string is mandatory — it will appear in the log record.

        Args:
            reason: Human-readable justification for the bypass (e.g.
                ``"support-export-ticket-42"``).
            table: The table being accessed (used in the audit log).

        Yields:
            ``None`` — the body runs with RLS bypassed.
        """
        logger.warning(
            "rls.admin_bypass table=%s reason=%r",
            table,
            reason,
            extra={
                "event": "rls.admin_bypass",
                "table": table,
                "reason": reason,
            },
        )
        token = self._admin_var.set(True)
        try:
            yield
        finally:
            self._admin_var.reset(token)

    # ------------------------------------------------------------------
    # Query-time helpers
    # ------------------------------------------------------------------

    def is_admin_bypass_active(self) -> bool:
        """Return ``True`` if an admin bypass is currently in effect."""
        return self._admin_var.get()

    def current_scope(self) -> ActiveScope | None:
        """Return the currently active :class:`ActiveScope`, or ``None``."""
        return self._ctx_var.get()

    def require_scope(self, *, table: str, operation: str) -> ActiveScope:
        """Return the active scope, or raise :exc:`NoSecurityPolicyError`.

        Called by repository mixins before issuing any SELECT / UPDATE /
        DELETE.  Admin bypass suppresses the check.

        Args:
            table: Table name (for the error message).
            operation: SQL operation name (``"SELECT"``, etc.).

        Returns:
            The active :class:`ActiveScope`.

        Raises:
            NoSecurityPolicyError: If no scope is active and no admin
                bypass is in effect.
        """
        if self.is_admin_bypass_active():
            # Return an empty scope — the mixin will skip injecting any WHERE.
            return ActiveScope(values={})

        scope = self.current_scope()
        if scope is None:
            raise NoSecurityPolicyError(table=table, operation=operation)
        return scope


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "ActiveScope",
    "NoSecurityPolicyError",
    "RowLevelSecurityPolicy",
    "ScopeColumn",
]
