"""Unified Authorization Service for Quadkit.

This service consolidates RBAC (Role-Based Access Control) logic, combining
the best features of permission management, role hierarchies, and ABAC
(Attribute-Based Access Control) policies.

It serves as the single source of truth for all authorization decisions
in a Quadkit application.

Example:
    Checking authorization::

        from quadkit.auth.authz import AuthorizationService

        auth_service = AuthorizationService()

        # Define roles with inheritance
        auth_service.set_roles({
            "admin": {"permissions": ["*"]},
            "editor": {"inherits": ["viewer"], "permissions": ["articles.write"]},
            "viewer": {"permissions": ["articles.read"]},
        })

        # Authorize a user action
        result = await auth_service.authorize(user, "articles", "read")
        if result.is_ok():
            # User can read articles
            pass

    Using with dependency injection::

        from quadkit.di import inject

        class ArticleController(Controller):
            @inject
            def __init__(self, auth: AuthorizationService):
                self.auth = auth

            async def check_permission(self, user, resource: str, action: str) -> bool:
                result = await self.auth.authorize(user, resource, action)
                return result.is_ok()

See Also:
    - :class:`quadkit.auth.policies.engine.PolicyEngine`: ABAC policy engine.
    - :class:`quadkit.auth.types.RoleDefinition`: Role definition model.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.auth.authz._check_mixin import _AuthCheckMixin
from quadkit.auth.authz._parsers import (
    ListValueParser,
    NoneValueParser,
    StringValueParser,
    ValueParser,
    ValueParserRegistry,
)
from quadkit.auth.policies.engine import PolicyEngine
from quadkit.auth.types import RoleDefinition
from quadkit.contracts.exceptions import DependencyError, UnresolvableDependencyError
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.audit import AuditLoggerProtocol


# Use local types if available, otherwise define minimal protocols
@runtime_checkable
class UserProtocol(Protocol):
    roles: list[str]
    permissions: list[str]


logger = get_logger(__name__)


class AuthorizationService(_AuthCheckMixin):
    """Central service for all authorization checks."""

    def __init__(
        self,
        permission_cache_ttl: float = 300.0,
        *,
        max_cache_entries: int = 10000,
        audit_logger: AuditLoggerProtocol | None = None,
    ) -> None:
        """Initialize a new authorization service instance.

        Args:
            permission_cache_ttl: TTL in seconds for the per-user permission
                cache.  Defaults to 300 seconds (5 minutes).
            max_cache_entries: Maximum number of entries in the permission cache.
                When the cache reaches this size the oldest entry (by insertion
                order) is evicted before adding a new one.  Defaults to 10 000.
            audit_logger: Optional :class:`~quadkit.contracts.audit.AuditLoggerProtocol`
                used to record authorization decisions (granted / denied).
                No audit entries are written when *None*.
        """
        self._lock = asyncio.Lock()
        self._roles: dict[str, Any] = {}
        self._schemas: dict[str, Any] = {}
        self._policy_engine: Any | None = None
        self._delegation_manager: Any | None = None
        self._value_parsers = ValueParserRegistry()
        self._role_flatten_cache: dict[frozenset[str], tuple[float, set[str]]] = {}
        self._permission_cache: dict[str, tuple[float, set[str]]] = {}
        self._permission_cache_ttl = permission_cache_ttl
        self._max_cache_entries = max_cache_entries
        self._audit_logger: AuditLoggerProtocol | None = audit_logger

    def set_policies(self, policies: list[Any]) -> None:
        """Set the ABAC policies and initialize the engine."""
        self._policy_engine = PolicyEngine(policies)
        logger.info("✓ ABAC Policy Engine configured with %d policies", len(policies))

    def set_roles(self, roles: dict[str, RoleDefinition | dict[str, Any]]) -> None:
        """Set the global role definitions (usually from config/seed)."""
        for name, role in roles.items():
            self.register_role(name, role)
        logger.info("✓ RBAC Roles configured with %d definitions", len(self._roles))

    def __repr__(self) -> str:
        """Return developer-friendly string representation."""
        return f"AuthorizationService(roles={len(self._roles)}, schemas={len(self._schemas)})"

    def register_role(self, name: str, role: RoleDefinition | dict[str, Any]) -> None:
        """Register a role definition."""
        # OPT-AUTH-1: Invalidate cache when roles change
        self._role_flatten_cache.clear()

        if isinstance(role, dict):
            role_def = RoleDefinition(
                name=name,
                description=role.get("description", ""),
                permissions=self._parse_list(role.get("permissions", [])),
                inherits=self._parse_list(role.get("inherits", [])),
            )
        else:
            role_def = role

        self._roles[name] = role_def
        # Invalidate caches
        self._role_flatten_cache.clear()
        self._permission_cache.clear()
        logger.debug("Registered role: %s (inherits: %s)", name, role_def.inherits)

    def get_role(self, name: str) -> Any | None:
        return self._roles.get(name)

    async def sync_from_db(self, container: Any) -> None:
        """Load roles from database and merge with existing (YAML) roles."""
        # Dynamic import to avoid circular deps
        from quadkit.contracts.data import DatabaseProviderProtocol

        # GenericRepository is a concrete class from quadkit-sql.
        # We resolve it dynamically to avoid top-level sibling dependencies.

        # We assume a standard Role entity exists or use a generic dict approach
        # For now, strict typing is relaxed to allow flexible adoption

        db = await container.resolve(DatabaseProviderProtocol)
        if db:
            # Try to query a standard roles table if it exists
            try:
                # 1. Try 'roles' first (modern standard)
                try:
                    generic_repository = await container.resolve(
                        "GenericRepository",
                    )
                except (
                    DependencyError,
                    UnresolvableDependencyError,
                    KeyError,
                    AttributeError,
                ):
                    # GenericRepository not registered — skip DB role sync
                    logger.debug(
                        "GenericRepository not found in container; skipping DB role sync",
                    )
                    return

                repo = generic_repository(db, "roles", dict)
                db_roles = await repo.find_many()
            except Exception:  # noqa: BLE001 — any 'roles' probe failure falls back to 'admin_roles'
                # 2. Fallback to 'admin_roles' (legacy)
                try:
                    repo = generic_repository(db, "admin_roles", dict)
                    db_roles = await repo.find_many()
                except Exception as e:  # noqa: BLE001 — role sync degrades to empty, never crashes boot
                    logger.debug(
                        "Table 'admin_roles' not found or inaccessible: %s",
                        e,
                    )
                    db_roles = []

            for role in db_roles:
                # DB takes priority over YAML if same name
                if isinstance(role, dict):
                    name = role.get("name")
                    if name:
                        self.register_role(name, role)
                else:
                    name = getattr(role, "name", None)
                    if name:
                        self.register_role(name, role)

            if db_roles:
                logger.info(
                    "✓ RBAC Roles synced from database (%d roles)",
                    len(db_roles),
                )

    def create_role(
        self,
        name: str,
        permissions: list[str] | None = None,
        inherits: list[str] | None = None,
    ) -> None:
        """Create or update a role definition."""

        self.register_role(
            name,
            RoleDefinition(
                name=name,
                permissions=permissions or [],
                inherits=inherits or [],
            ),
        )

    def add_role_permission(self, role_name: str, permission: str) -> None:
        """Add a permission to an existing role."""
        role = self._roles.get(role_name)
        if not role:
            self.create_role(role_name, [permission])
            return

        # Handle dict or object
        if isinstance(role, dict):
            perms = role.get("permissions")
            if isinstance(perms, list):
                perms = set(perms)
                role["permissions"] = perms
            elif isinstance(perms, set):
                pass
            else:
                role["permissions"] = set()
            role["permissions"].add(permission)
        elif hasattr(role, "permissions"):
            # If object has mutable permissions set/list
            if isinstance(role.permissions, list):
                if permission not in role.permissions:
                    role.permissions.append(permission)
            elif isinstance(role.permissions, set):
                role.permissions.add(permission)

        # Invalidate caches
        self._role_flatten_cache.clear()
        self._permission_cache.clear()

    def get_role_permissions(self, role: str) -> set[str]:
        """Get all permissions for a role, including inherited ones."""
        effective_roles = self._flatten_roles({role})
        return self._get_user_permissions(effective_roles)

    def remove_role(self, name: str) -> None:
        """Remove a role definition and invalidate dependent caches.

        Missing roles are a no-op.  In-memory merges mean a removed role
        can reappear if DB-synced again; callers persist the deletion.

        Args:
            name: Role name to remove.
        """
        self._roles.pop(name, None)
        self._role_flatten_cache.clear()
        self._permission_cache.clear()
        logger.debug("Removed role: %s", name)

    def invalidate_user(self, user_id: str) -> None:
        """Invalidate the permission cache for a specific user."""
        self._permission_cache.pop(user_id, None)
        logger.debug("Invalidated permission cache for user: %s", user_id)


def __getattr__(name: str) -> Any:
    if name == "authorization_service":
        raise AttributeError(
            "authorization_service is now async. Use the container to resolve AuthorizationService.",
        )
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = [
    "AuthorizationService",
    "ListValueParser",
    "NoneValueParser",
    "StringValueParser",
    "UserProtocol",
    "ValueParser",
    "ValueParserRegistry",
    "logger",
]
