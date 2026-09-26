"""Injectable db-layer context.

Replaces the former ``functions.py`` module whose free getter / setter
functions accessed module-level ``ContextVar`` globals (service-locator
anti-pattern).

Composition-root example::

    from quadkit.primitives.context import create_default_context
    from quadkit.sql.context import create_db_context, REQUEST_ID

    core_ctx  = create_default_context()
    db_ctx    = create_db_context(core_ctx=core_ctx)
    handler   = MyHandler(db_ctx=db_ctx)          # inject

    token = db_ctx.set(REQUEST_ID, "abc-123")
    assert db_ctx.request_id == "abc-123"
    db_ctx.reset(REQUEST_ID, token)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from quadkit.primitives.context import ContextKey, ContextVarRegistry
from quadkit.sql.context.keys import (
    DB_KEYS,
    RATE_LIMIT_LIMIT,
    RATE_LIMIT_REMAINING,
    RATE_LIMIT_RESET,
    REQUEST_ID,
    TENANT_ID,
    USER,
    USER_ID,
)

if TYPE_CHECKING:
    import contextvars

    from quadkit.primitives.context import Context

T = TypeVar("T")


class DbContext:
    """Typed, injectable context for the database layer.

    Wraps an injected ``ContextVarRegistry`` and exposes both generic
    ``get`` / ``set`` access via ``ContextKey`` and read-only
    convenience properties for well-known db keys.

    An optional ``core_ctx`` reference lets ``RequestContextManager``
    bridge values into the core framework context on enter and properly
    restore them on exit.
    """

    def __init__(
        self,
        registry: ContextVarRegistry,
        *,
        core_ctx: Context | None = None,
    ) -> None:
        self._registry = registry
        self._core_ctx = core_ctx

    # -- wiring ----------------------------------------------------------------

    @property
    def registry(self) -> ContextVarRegistry:
        """The underlying registry (for advanced use / wiring)."""
        return self._registry

    @property
    def core_ctx(self) -> Context | None:
        """Optional core ``Context`` used for bridging values."""
        return self._core_ctx

    # -- generic typed operations ----------------------------------------------

    def get(self, key: ContextKey[T], default: T | None = None) -> T | None:
        """Read the current value for *key*, returning *default* when unset."""
        return self._registry.get_typed(key, default)

    def set(
        self,
        key: ContextKey[T],
        value: T,
    ) -> contextvars.Token[T | None]:
        """Write *value* for *key* and return a reset token."""
        return self._registry.set_typed(key, value)

    def reset(
        self,
        key: ContextKey[T],
        token: contextvars.Token[T | None],
    ) -> None:
        """Restore the previous value of *key* using a token from ``set``."""
        self._registry.reset_typed(key, token)

    # -- DatabaseContextProtocol implementation (tenant bridge) --------------

    def set_tenant_from_scope(
        self, scope: dict[str, Any]
    ) -> contextvars.Token[str | None] | None:
        """Set the tenant from the bridge payload or a full ASGI scope.

        Accepts the current bridge payload ``{"tenant_id": "..."}``, or a
        full ASGI scope carrying ``scope["state"]["tenant"]`` (a
        ``TenantInfo``-like object).  Returns ``None`` when no tenant is
        present; otherwise writes ``TENANT_ID`` and returns the reset token.

        Args:
            scope: Bridge payload dict or ASGI scope dict.

        Returns:
            A ``contextvars.Token`` for ``reset_tenant``, or ``None``.
        """
        tenant_id: Any = scope.get("tenant_id")
        if tenant_id is None:
            state = scope.get("state", {}) if isinstance(scope, dict) else {}
            tenant = state.get("tenant")
            if tenant is not None:
                tenant_id = getattr(tenant, "tenant_id", None)
        if tenant_id is None:
            return None
        return self.set(TENANT_ID, tenant_id)

    def reset_tenant(self, token: contextvars.Token[str | None] | None) -> None:
        """Reset the tenant context using a token from ``set_tenant_from_scope``.

        Args:
            token: Token returned by ``set_tenant_from_scope``.
        """
        if token is not None:
            self.reset(TENANT_ID, token)

    # -- convenience read-only properties -------------------------------------

    @property
    def request_id(self) -> str | None:
        """Current request ID."""
        return self.get(REQUEST_ID)

    @property
    def user_id(self) -> str | None:
        """Current user ID."""
        return self.get(USER_ID)

    @property
    def tenant_id(self) -> str | None:
        """Current tenant ID."""
        return self.get(TENANT_ID)

    @property
    def user(self) -> Any | None:
        """Current user object."""
        return self.get(USER)

    @property
    def rate_limit_remaining(self) -> int | None:
        """Remaining rate-limit quota for this request."""
        return self.get(RATE_LIMIT_REMAINING)

    @property
    def rate_limit_limit(self) -> int | None:
        """Maximum rate-limit quota per window."""
        return self.get(RATE_LIMIT_LIMIT)

    @property
    def rate_limit_reset(self) -> int | None:
        """Unix timestamp when the rate-limit window resets."""
        return self.get(RATE_LIMIT_RESET)

    # -- introspection ---------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of all non-``None`` db context values."""
        return self._registry.snapshot()


# -- Factory -------------------------------------------------------------------


def create_db_context(
    *,
    core_ctx: Context | None = None,
    extra_keys: tuple[ContextKey[Any], ...] = (),
) -> DbContext:
    """Create a ``DbContext`` with all standard db keys registered.

    Call **once** in your composition root::

        db_ctx = create_db_context(core_ctx=app_ctx)
        handler = MyHandler(db_ctx=db_ctx)

    Args:
        core_ctx: Optional core ``Context`` instance.  When provided,
            ``RequestContextManager`` will bridge ``request_id``,
            ``user_id`` and ``tenant_id`` into it on enter and restore
            them on exit.
        extra_keys: Additional ``ContextKey`` instances to register beyond
            the standard ``DB_KEYS``.
    """
    registry = ContextVarRegistry(name="DbContextVarRegistry")
    for key in DB_KEYS:
        registry.register_key(key)
    for key in extra_keys:
        registry.register_key(key)
    return DbContext(registry, core_ctx=core_ctx)


__all__ = [
    "DbContext",
    "create_db_context",
]
