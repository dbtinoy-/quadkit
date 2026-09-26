"""Async request context manager for the database layer.

Sets db-layer context variables for the duration of a request and
optionally bridges values into the core ``Context``.  All state is
properly restored on exit — including bridged core values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from quadkit.logging import get_logger
from quadkit.sql.context.keys import (
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

    from quadkit.primitives.context import ContextKey
    from quadkit.sql.context.db_context import DbContext

logger = get_logger(__name__)

# Db keys whose values should be bridged into the core Context.
# Maps (db ContextKey → core key name).
_CORE_BRIDGE: tuple[tuple[ContextKey[Any], str], ...] = (
    (REQUEST_ID, "request_id"),
    (USER_ID, "user_id"),
    (TENANT_ID, "tenant_id"),
)


class RequestContextManager:
    """Async context manager that sets request-scoped db context variables
    and restores them on exit.

    All dependencies are injected via a ``DbContext`` instance::

        db_ctx = create_db_context(core_ctx=core_ctx)

        async with RequestContextManager(db_ctx, request_id="abc-123"):
            assert db_ctx.request_id == "abc-123"
        # values are restored here

    Core-context bridging
    ~~~~~~~~~~~~~~~~~~~~~
    When ``db_ctx.core_ctx`` is not ``None``, the manager will
    automatically propagate ``request_id``, ``user_id`` and
    ``tenant_id`` into the core context on enter and reset them
    on exit.
    """

    def __init__(
        self,
        db_ctx: DbContext,
        *,
        request_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        user: Any | None = None,
        rate_limit_remaining: int | None = None,
        rate_limit_limit: int | None = None,
        rate_limit_reset: int | None = None,
    ) -> None:
        self._db_ctx = db_ctx

        # Collect non-None db entries
        self._entries: list[tuple[ContextKey[Any], Any]] = []
        if request_id is not None:
            self._entries.append((REQUEST_ID, request_id))
        if user_id is not None:
            self._entries.append((USER_ID, user_id))
        if tenant_id is not None:
            self._entries.append((TENANT_ID, tenant_id))
        if user is not None:
            self._entries.append((USER, user))
        if rate_limit_remaining is not None:
            self._entries.append((RATE_LIMIT_REMAINING, rate_limit_remaining))
        if rate_limit_limit is not None:
            self._entries.append((RATE_LIMIT_LIMIT, rate_limit_limit))
        if rate_limit_reset is not None:
            self._entries.append((RATE_LIMIT_RESET, rate_limit_reset))

        # Pre-build bridge entries so __aenter__ stays simple
        entry_keys = {k for k, _ in self._entries}
        self._bridge_entries: list[tuple[str, Any]] = [
            (core_name, next(v for k, v in self._entries if k is db_key))
            for db_key, core_name in _CORE_BRIDGE
            if db_key in entry_keys
        ]

        # For logging
        self._request_id = request_id
        self._user_id = user_id
        self._tenant_id = tenant_id

        # Tokens populated on __aenter__
        self._db_tokens: list[tuple[ContextKey[Any], contextvars.Token[Any]]] = []
        self._core_tokens: list[tuple[str, contextvars.Token[Any]]] = []

    async def __aenter__(self) -> Self:
        # 1. Set db-layer context vars
        for key, value in self._entries:
            token = self._db_ctx.set(key, value)
            self._db_tokens.append((key, token))

        # 2. Bridge selected values into core context
        core = self._db_ctx.core_ctx
        if core is not None:
            for core_name, value in self._bridge_entries:
                if core.has(core_name):
                    token = core.set_dynamic(core_name, value)
                    self._core_tokens.append((core_name, token))

        logger.debug(
            "Db request context initialized",
            extra={
                "request_id": self._request_id,
                "user_id": self._user_id,
                "tenant_id": self._tenant_id,
            },
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        # 1. Reset core-context tokens (LIFO)
        core = self._db_ctx.core_ctx
        if core is not None:
            for name, token in reversed(self._core_tokens):
                try:
                    core.reset_dynamic(name, token)
                except (RuntimeError, ValueError) as exc:
                    logger.debug(
                        "Failed to reset core context key %s: %s",
                        name,
                        exc,
                        exc_info=True,
                    )
            self._core_tokens.clear()

        # 2. Reset db-context tokens (LIFO)
        for key, token in reversed(self._db_tokens):
            try:
                self._db_ctx.reset(key, token)
            except (RuntimeError, ValueError) as exc:
                logger.debug(
                    "Failed to reset db context key %s: %s",
                    key.name,
                    exc,
                    exc_info=True,
                )
        self._db_tokens.clear()

        logger.debug("Db request context cleaned up")


__all__ = [
    "RequestContextManager",
]
