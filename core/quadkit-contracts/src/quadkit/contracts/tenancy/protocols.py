"""Tenancy protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result
    from quadkit.contracts.tenancy.commands import (
        CreateTenantCommand,
        UpdateTenantCommand,
    )
    from quadkit.contracts.tenancy.errors import TenantError
    from quadkit.contracts.tenancy.types import TenantInfo, TenantResolutionContext


@runtime_checkable
class TenantResolverProtocol(Protocol):
    """Resolves tenant identity from request context.

    Implementations are tried in priority order by
    :class:`~quadkit.tenancy.resolution.chain.CompositeResolver`.
    Lower ``priority`` value = tried first = higher trust level.

    Attributes:
        name: Unique resolver name (e.g. ``"header"``, ``"jwt_claim"``).
        priority: Ordering weight; lower = tried first.
    """

    name: str
    priority: int

    async def resolve(self, context: TenantResolutionContext) -> str | None:
        """Attempt to resolve the tenant identifier from the given context.

        Args:
            context: Immutable snapshot of request data.

        Returns:
            The resolved ``tenant_id`` string, or ``None`` if this resolver
            cannot determine the tenant from the provided context.
        """
        ...


@runtime_checkable
class TenantProviderProtocol(Protocol):
    """Storage-agnostic tenant CRUD operations.

    Applications may supply their own implementation by binding a class to
    this protocol in the DI container.  The default implementations are
    :class:`~quadkit.tenancy.stores.memory.InMemoryTenantProvider` (for
    testing/dev) and ``SQLTenantProvider`` (when
    ``quadkit-tenancy[sql]`` is installed).
    """

    async def get_tenant(self, tenant_id: str) -> TenantInfo | None:
        """Retrieve a tenant by its unique identifier.

        Args:
            tenant_id: The unique tenant identifier.

        Returns:
            The :class:`~quadkit.contracts.tenancy.types.TenantInfo` record,
            or ``None`` if no tenant with that ID exists.
        """
        ...

    async def get_tenant_by_slug(self, slug: str) -> TenantInfo | None:
        """Retrieve a tenant by its URL-safe slug.

        Args:
            slug: The tenant slug (e.g. ``acme-corp``).

        Returns:
            The matching :class:`~quadkit.contracts.tenancy.types.TenantInfo`,
            or ``None`` if not found.
        """
        ...

    async def list_tenants(self, *, active_only: bool = True) -> list[TenantInfo]:
        """List tenants, optionally filtering to active ones only.

        Args:
            active_only: When ``True`` (default), return only tenants with
                ``status == ACTIVE``.

        Returns:
            List of matching :class:`~quadkit.contracts.tenancy.types.TenantInfo`
            records.
        """
        ...

    async def create_tenant(
        self, command: CreateTenantCommand
    ) -> Result[TenantInfo, TenantError]:
        """Persist a new tenant record.

        Args:
            command: :class:`~quadkit.contracts.tenancy.commands.CreateTenantCommand`
                with the new tenant's attributes.

        Returns:
            ``Ok(TenantInfo)`` on success, ``Err(TenantError)`` on failure.
        """
        ...

    async def update_tenant(
        self,
        tenant_id: str,
        command: UpdateTenantCommand,
    ) -> Result[TenantInfo, TenantError]:
        """Update mutable fields on an existing tenant record.

        Args:
            tenant_id: Identifier of the tenant to update.
            command: :class:`~quadkit.contracts.tenancy.commands.UpdateTenantCommand`
                with the fields to apply.

        Returns:
            ``Ok(TenantInfo)`` with the updated record, or ``Err(TenantError)``.
        """
        ...

    async def deactivate_tenant(self, tenant_id: str) -> Result[None, TenantError]:
        """Mark a tenant as inactive.

        Args:
            tenant_id: Identifier of the tenant to deactivate.

        Returns:
            ``Ok(None)`` on success, ``Err(TenantError)`` on failure.
        """
        ...

    async def activate_tenant(self, tenant_id: str) -> Result[None, TenantError]:
        """Mark a tenant as active.

        Args:
            tenant_id: Identifier of the tenant to activate.

        Returns:
            ``Ok(None)`` on success, ``Err(TenantError)`` on failure.
        """
        ...

    async def suspend_tenant(
        self,
        tenant_id: str,
        reason: str | None = None,
    ) -> Result[None, TenantError]:
        """Mark a tenant as suspended.

        Args:
            tenant_id: Identifier of the tenant to suspend.
            reason: Optional human-readable reason for the suspension.

        Returns:
            ``Ok(None)`` on success, ``Err(TenantError)`` on failure.
        """
        ...


@runtime_checkable
class TenantMembershipProtocol(Protocol):
    """Verifies whether an authenticated caller belongs to a tenant.

    Implemented by the application (e.g. over a ``tenant_memberships``
    table, a ``users.tenant_id`` column, or an external identity service).
    The framework does not ship an implementation; the app binds one in
    the DI container.  Membership caching is delegated to the implementer.

    See Also:
        ``docs/superpowers/specs/2026-08-16-security-tenancy-design.md`` §3.1
        for the required sign-off and the deferred schema-provisioning option
        (framework-managed ``tenant_memberships`` table).
    """

    async def user_belongs_to_tenant(self, user_id: str, tenant_id: str) -> bool:
        """Return ``True`` when *user_id* may act under *tenant_id*."""
        ...


@runtime_checkable
class TenantConfigProviderProtocol(Protocol):
    """Per-tenant configuration key-value store.

    Provides a low-level get/set interface.  The higher-level
    :class:`~quadkit.tenancy.config_overrides.service.TenantConfigService`
    adds default fallback and event emission on top of this protocol.
    """

    async def get_config(self, tenant_id: str, key: str) -> Any | None:
        """Retrieve a single configuration value for a tenant.

        Args:
            tenant_id: The tenant whose configuration is queried.
            key: The configuration key.

        Returns:
            The stored value, or ``None`` if the key is not set for this tenant.
        """
        ...

    async def get_all_config(self, tenant_id: str) -> dict[str, Any]:
        """Retrieve all configuration entries for a tenant.

        Args:
            tenant_id: The tenant whose configuration is retrieved.

        Returns:
            A dictionary of all key-value pairs for the tenant.
            Returns an empty dict if no overrides are set.
        """
        ...

    async def set_config(self, tenant_id: str, key: str, value: Any) -> None:
        """Set a configuration value for a tenant.

        Args:
            tenant_id: The tenant whose configuration is updated.
            key: The configuration key.
            value: The new value (must be JSON-serialisable).
        """
        ...


@runtime_checkable
class TenantIsolationStrategyProtocol(Protocol):
    """Pluggable data isolation strategy.

    Implementations provide the mechanics of isolating tenant data at the
    database layer (row-level, schema-per-tenant, or database-per-tenant).

    Attributes:
        name: Strategy identifier used by the registry
            (``"row_level"``, ``"schema"``, ``"database"``).
    """

    name: str

    async def apply_isolation(self, tenant_id: str, context: dict[str, Any]) -> None:
        """Apply tenant isolation to the given execution context.

        For row-level isolation this is a no-op; for schema isolation this sets
        the ``search_path`` in *context*.

        Args:
            tenant_id: The active tenant.
            context: Mutable execution context dict to annotate.
        """
        ...

    async def remove_isolation(self, tenant_id: str) -> None:
        """Remove any active isolation for the tenant.

        Args:
            tenant_id: The tenant whose isolation context to tear down.
        """
        ...

    async def provision_isolation(self, tenant_id: str) -> Result[None, TenantError]:
        """Provision isolation resources for a newly created tenant.

        For row-level isolation this is a no-op.  For schema isolation this
        creates the schema.

        Args:
            tenant_id: The newly created tenant.

        Returns:
            ``Ok(None)`` on success, ``Err(TenantError)`` on failure.
        """
        ...

    async def deprovision_isolation(self, tenant_id: str) -> Result[None, TenantError]:
        """Tear down isolation resources for a deactivated tenant.

        Args:
            tenant_id: The tenant being deactivated.

        Returns:
            ``Ok(None)`` on success, ``Err(TenantError)`` on failure.
        """
        ...


__all__ = [
    "TenantConfigProviderProtocol",
    "TenantIsolationStrategyProtocol",
    "TenantMembershipProtocol",
    "TenantProviderProtocol",
    "TenantResolverProtocol",
]
