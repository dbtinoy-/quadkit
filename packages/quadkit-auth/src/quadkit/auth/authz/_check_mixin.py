"""Authorization check mixin for AuthorizationService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.audit import AuditEntry, AuditLoggerProtocol
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from quadkit.auth.authz._parsers import ValueParserRegistry
    from quadkit.auth.exceptions import AuthorizationError

logger = get_logger(__name__)


class _AuthCheckMixin:
    """Mixin providing authorization check methods for AuthorizationService."""

    # Type annotations for attributes provided by AuthorizationService.__init__.
    # Declared here so type checkers understand the mixin's assumptions.
    _roles: dict[str, Any]
    _policy_engine: Any | None
    _permission_cache: dict[str, tuple[float, set[str]]]
    _permission_cache_ttl: float
    _max_cache_entries: int
    _audit_logger: AuditLoggerProtocol | None
    _role_flatten_cache: dict[frozenset[str], tuple[float, set[str]]]
    _value_parsers: ValueParserRegistry

    def _parse_list(self, val: Any) -> list[str]:
        """Parse a value into a list of strings using the registry."""
        return self._value_parsers.parse(val)

    async def check_access(
        self,
        user: Any,
        allowed_roles: set[str],
        resource: str | None = None,
        action: str | None = None,
    ) -> bool:
        """Core access check combining roles, inheritance, and permission patterns."""
        if "*" in allowed_roles:
            return True

        if not user:
            return False

        # Gather user roles
        user_roles = set()

        if hasattr(user, "roles") and user.roles:
            user_roles.update(self._parse_list(user.roles))
        if hasattr(user, "role") and user.role:
            user_roles.add(str(user.role))
        # Check superuser/admin bypass
        if (
            getattr(user, "is_superuser", False)
            or "admin" in user_roles
            or "superuser" in user_roles
        ):
            return True

        # 1. Direct role check
        if bool(user_roles & allowed_roles):
            return True

        # 2. Inheritance check
        effective_roles = self._flatten_roles(user_roles)
        if bool(effective_roles & allowed_roles):
            return True

        # 3. Permission Pattern check (if resource/action provided)
        if resource and action:
            # 1. Gather context for ABAC evaluation
            context = {
                "user": user,
                "resource": resource,
                "action": action,
                "resource_id": resource.rsplit(":", maxsplit=1)[-1]
                if ":" in resource
                else None,
                "request": getattr(user, "_request_metadata", {}),
                "delegations": getattr(user, "delegations", []),
            }

            # 2. ABAC Policy evaluation
            if hasattr(self, "_policy_engine") and self._policy_engine:
                from quadkit.auth.policies.types import (
                    AuthorizationRequest,
                    DecisionOutcome,
                )

                # Principal identity e.g., "user:123"
                principal = f"user:{getattr(user, 'user_id', 'unknown')}"

                req = AuthorizationRequest(
                    principal=principal,
                    action=action,
                    resource=resource,
                    context=context,
                )

                abac_decision = self._policy_engine.evaluate(req)
                if abac_decision.decision == DecisionOutcome.DENY:
                    logger.info("ABAC: Access DENIED by policy for %s", principal)
                    return False
                if abac_decision.decision == DecisionOutcome.ALLOW:
                    logger.info("ABAC: Access ALLOWED by policy for %s", principal)
                    return True

            # 3. Permission Pattern check (Fallback if no ABAC policy matched)
            user_id = getattr(user, "user_id", None) or getattr(user, "id", None)
            now = ambient_clock.monotonic()

            user_perms = None
            if user_id:
                cache_entry = self._permission_cache.get(str(user_id))
                if cache_entry:
                    expiry, cached_perms = cache_entry
                    if expiry > now:
                        user_perms = cached_perms

            if user_perms is None:
                user_perms = self._get_user_permissions(effective_roles)
                # Mix in direct user permissions
                if hasattr(user, "permissions") and user.permissions:
                    user_perms.update(self._parse_list(user.permissions))

                if user_id:
                    # Bounded cache: evict the oldest entry (by insertion order)
                    # when the cache is at capacity.  Python 3.7+ dicts preserve
                    # insertion order, so ``next(iter(...))`` is always the entry
                    # that was added earliest.  The effective eviction policy is
                    # FIFO (first-in, first-out), not true recency-based LRU.
                    # ``max_cache_entries`` (default 10 000) caps memory usage.
                    if len(self._permission_cache) >= self._max_cache_entries:
                        oldest_key = next(iter(self._permission_cache))
                        del self._permission_cache[oldest_key]
                    self._permission_cache[str(user_id)] = (
                        now + self._permission_cache_ttl,
                        user_perms,
                    )

            required_perm = f"{resource}.{action}"
            if self._has_permission(user_perms, required_perm):
                return True

            # 4. Permission Delegation check
            delegations = context.get("delegations")
            # Also check user.delegations if injected there
            if not delegations and hasattr(user, "delegations"):
                delegations = user.delegations

            if delegations:
                for delegation in delegations:
                    # Match Action and Resource
                    if (
                        action in delegation.permissions
                        or "*" in delegation.permissions
                    ) and self._has_permission(set(delegation.resources), resource):
                        logger.info(
                            "Access ALLOWED via delegation %s (from %s)",
                            delegation.delegation_id,
                            delegation.delegator_id,
                        )
                        return True

        return False

    def has_any_role(self, user: Any, roles: list[str]) -> bool:
        """Check if user has any of the given roles."""
        if not user:
            return False

        user_roles = set()
        user_roles_attr = (
            user.get("roles")
            if isinstance(user, dict)
            else getattr(user, "roles", None)
        )
        if user_roles_attr:
            user_roles.update(self._parse_list(user_roles_attr))
        user_role_attr = (
            user.get("role") if isinstance(user, dict) else getattr(user, "role", None)
        )
        if user_role_attr:
            user_roles.add(str(user_role_attr))

        # Check superuser/admin bypass
        is_super = (
            user.get("is_superuser", False)
            if isinstance(user, dict)
            else getattr(user, "is_superuser", False)
        )
        if is_super or "admin" in user_roles or "superuser" in user_roles:
            return True

        effective_roles = self._flatten_roles(user_roles)
        return bool(effective_roles.intersection(roles))

    def has_any_permission(self, user: Any, permissions: list[str]) -> bool:
        """Return True if user has at least one of the given permissions."""
        if not user:
            return False

        user_roles = set()
        user_roles_attr = (
            user.get("roles")
            if isinstance(user, dict)
            else getattr(user, "roles", None)
        )
        if user_roles_attr:
            user_roles.update(self._parse_list(user_roles_attr))
        user_role_attr = (
            user.get("role") if isinstance(user, dict) else getattr(user, "role", None)
        )
        if user_role_attr:
            user_roles.add(str(user_role_attr))

        # Check superuser/admin bypass
        is_super = (
            user.get("is_superuser", False)
            if isinstance(user, dict)
            else getattr(user, "is_superuser", False)
        )
        if is_super or "admin" in user_roles or "superuser" in user_roles:
            return True

        effective_roles = self._flatten_roles(user_roles)
        user_perms = self._get_user_permissions(effective_roles)

        user_perms_attr = (
            user.get("permissions")
            if isinstance(user, dict)
            else getattr(user, "permissions", None)
        )
        if user_perms_attr:
            user_perms.update(self._parse_list(user_perms_attr))

        for req_perm in permissions:
            if self._has_permission(user_perms, req_perm):
                return True

        return False

    async def can(self, user: Any, action: str, resource: str) -> bool:
        """Convenience alias: return True if user can perform action on resource.

        Delegates to :meth:`authorize` and unwraps the result, returning
        ``False`` on ``Err`` (i.e. if the authorization check itself fails).
        """
        result = await self.authorize(user, action, resource)
        return result.unwrap_or(False)

    async def can_view(self, user: Any, resource: str, record: Any = None) -> bool:
        """Grant view when the user holds ``<resource>.view`` (record ignored for now)."""
        return self.has_any_permission(user, [f"{resource}.view"])

    async def can_create(self, user: Any, resource: str) -> bool:
        """Grant create when the user holds ``<resource>.create``."""
        return self.has_any_permission(user, [f"{resource}.create"])

    async def can_update(self, user: Any, resource: str, record: Any = None) -> bool:
        """Grant update when the user holds ``<resource>.update`` (record ignored for now)."""
        return self.has_any_permission(user, [f"{resource}.update"])

    async def can_delete(self, user: Any, resource: str, record: Any = None) -> bool:
        """Grant delete when the user holds ``<resource>.delete`` (record ignored for now)."""
        return self.has_any_permission(user, [f"{resource}.delete"])

    async def can_execute_action(
        self, user: Any, resource: str, action: str, record: Any | None = None
    ) -> bool:
        """Grant action execution when the user holds ``<resource>.<action>``."""
        return self.has_any_permission(user, [f"{resource}.{action}"])

    async def authorize(
        self, user: Any, action: str, resource: Any
    ) -> Result[bool, AuthorizationError]:
        """Check whether *user* is allowed to perform *action* on *resource*.

        This is the primary authorization method.  Satisfies the
        :class:`~quadkit.contracts.auth.guard.AuthorizerProtocol` protocol (note:
        the contracts protocol declares ``-> bool``; this implementation
        returns ``Result[bool, AuthorizationError]`` to make failures
        explicit.  Use :meth:`can` when a plain ``bool`` is required).

        ``Ok(True)``  — access granted.
        ``Ok(False)`` — access denied.
        ``Err(AuthorizationError)`` — the authorization check itself failed
            (e.g. policy engine error); callers should treat this as denied.

        Args:
            user: Authenticated user object.
            action: Action identifier (e.g. ``"read"``).
            resource: Target resource; coerced to :class:`str` for matching.

        Returns:
            ``Result[bool, AuthorizationError]``
        """
        granted = await self.check_access(user, set(), str(resource), action)

        if self._audit_logger is not None:
            actor_id = str(
                getattr(user, "user_id", None) or getattr(user, "id", None) or "unknown"
            )
            await self._audit_logger.log(
                AuditEntry(
                    action="authz.decision",
                    actor_id=actor_id,
                    resource_type=type(resource).__name__,
                    resource_id=str(resource),
                    outcome="granted" if granted else "denied",
                    metadata={"authz_action": action},
                )
            )

        return Ok(granted)

    # --- Internal Helpers ---

    def _get_effective_roles(self, user_roles: set[str]) -> set[str]:
        """Resolve all roles including inherited ones."""
        effective = set(user_roles)
        to_process = list(user_roles)
        processed = set()

        while to_process:
            role_name = to_process.pop()
            if role_name in processed:
                continue
            processed.add(role_name)

            role_def = self._roles.get(role_name)
            if role_def:
                inherits = getattr(role_def, "inherits", [])
                if not inherits and isinstance(role_def, dict):
                    inherits = role_def.get("inherits", [])

                for parent in inherits:
                    effective.add(parent)
                    to_process.append(parent)
        return effective

    def _get_user_permissions(self, effective_roles: set[str]) -> set[str]:
        """Flatten all permissions from effective roles."""
        permissions = set()
        for role_name in effective_roles:
            role_def = self._roles.get(role_name)
            if role_def is not None:
                perms = []
                if hasattr(role_def, "permissions"):
                    perms = role_def.permissions
                elif isinstance(role_def, dict):
                    perms = role_def.get("permissions", [])

                if perms:
                    permissions.update(perms)
        return permissions

    def _has_permission(self, user_permissions: set[str], required: str) -> bool:
        """Check if required permission matches any user permission patterns.

        Supports bidirectional wildcard matching:
        1. User has wildcard: user='admin.*', required='admin.users' -> True
        2. Requirement has wildcard: user='community.list', required='community.*' -> True
        """
        if "*" in user_permissions:
            return True

        if required in user_permissions:
            return True

        # Helper to check if a pattern matches a string
        def matches(pattern: str, string: str) -> bool:
            if "*" not in pattern:
                return pattern == string
            parts = pattern.split("*")
            # For simplicity, we only support a single wildcard for now (standard for the framework)
            prefix, suffix = parts[0], parts[1] if len(parts) > 1 else ""
            return string.startswith(prefix) and string.endswith(suffix)

        # Check if any user permission pattern matches the required string
        for user_perm in user_permissions:
            if "*" in user_perm and matches(user_perm, required):
                return True

        # Check if the required string is a pattern that matches any user permission
        if "*" in required:
            for user_perm in user_permissions:
                if matches(required, user_perm):
                    return True

        return False

    def _flatten_roles(self, role_names: set[str]) -> set[str]:
        """Recursively collect all parent roles for the given set of role names.

        This helper walks the role inheritance graph stored in ``self._roles`` and
        returns a set containing the original roles plus any roles they inherit
        from, directly or indirectly.

        Results are memoized for performance.
        """
        # OPT-AUTH-1: Use memoization cache
        cache_key = frozenset(role_names)
        now = ambient_clock.monotonic()

        if cache_key in self._role_flatten_cache:
            expiry, cached_roles = self._role_flatten_cache[cache_key]
            if expiry > now:
                return cached_roles

        result: set[str] = set(role_names)
        to_process: list[str] = list(role_names)
        while to_process:
            name = to_process.pop()
            role_def = self._roles.get(name)
            if not role_def:
                continue
            # ``inherits`` may be an attribute or a dict key depending on the role type
            inherits = (
                getattr(role_def, "inherits", None)
                if hasattr(role_def, "inherits")
                else None
            )
            if inherits is None:
                inherits = (
                    role_def.get("inherits", []) if isinstance(role_def, dict) else []
                )
            for parent in inherits:
                if parent not in result:
                    result.add(parent)
                    to_process.append(parent)

        self._role_flatten_cache[cache_key] = (now + self._permission_cache_ttl, result)
        return result


__all__ = ["_AuthCheckMixin"]
