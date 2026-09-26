"""Query scopes — reusable query modifiers.

QueryScopes are composable query fragments that can be automatically
applied to repositories, similar to Laravel's Query Scopes.

Example:
    class ActiveScope(QueryScope):
        def apply(self, query):
            return query.where("is_active", Operator.EQ, True)

    class TenantScope(QueryScope):
        def __init__(self, tenant_id: str):
            self.tenant_id = tenant_id
        def apply(self, query):
            return query.where("tenant_id", Operator.EQ, self.tenant_id)

    # On a repository:
    class UserRepository(SQLRepository):
        __scopes__ = [ActiveScope()]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.sql.query import AsyncQueryBuilder


class QueryScope(ABC):
    """Abstract base for reusable query modifiers."""

    @abstractmethod
    def apply(self, query: AsyncQueryBuilder) -> AsyncQueryBuilder:
        """Apply this scope to a query builder.

        Args:
            query: The query builder to modify.

        Returns:
            The modified query builder.
        """


class ActiveScope(QueryScope):
    """Filters to only active (non-deleted) records."""

    def __init__(
        self,
        active_column: str = "is_active",
        deleted_column: str | None = "deleted_at",
    ) -> None:
        self.active_column = active_column
        self.deleted_column = deleted_column

    def apply(self, query: AsyncQueryBuilder) -> AsyncQueryBuilder:
        from quadkit.sql.query.operators import Operator

        query = query.where(self.active_column, Operator.EQ, True)
        if self.deleted_column:
            query = query.where(
                self.deleted_column,
                Operator.IS_NULL,
                None,
            )
        return query


class TenantScope(QueryScope):
    """Scopes queries to a specific tenant.

    .. warning::
        Opt-in per repository: the scope only applies where declared in
        ``__scopes__``. A repository over a tenant-owned table that neither
        declares :class:`TenantScope` nor is built with
        ``multi_tenant=True`` has **no** tenant filter and will read/write
        across tenants. Prefer ``multi_tenant=True`` for tenant-owned
        repositories — it auto-scopes every query and raises
        ``TenantScopingError`` (fail-closed) when no ambient tenant is set.
    """

    def __init__(self, tenant_id: str, column: str = "tenant_id") -> None:
        self.tenant_id = tenant_id
        self.column = column

    def apply(self, query: AsyncQueryBuilder) -> AsyncQueryBuilder:
        from quadkit.sql.query.operators import Operator

        return query.where(self.column, Operator.EQ, self.tenant_id)


class SoftDeleteScope(QueryScope):
    """Excludes soft-deleted records."""

    def __init__(self, column: str = "deleted_at") -> None:
        self.column = column

    def apply(self, query: AsyncQueryBuilder) -> AsyncQueryBuilder:
        from quadkit.sql.query.operators import Operator

        return query.where(self.column, Operator.IS_NULL, None)


class OrderingScope(QueryScope):
    """Applies default ordering."""

    def __init__(self, column: str, desc: bool = False) -> None:
        self.column = column
        self.desc = desc

    def apply(self, query: AsyncQueryBuilder) -> AsyncQueryBuilder:
        return query.order_by(self.column, desc=self.desc)
