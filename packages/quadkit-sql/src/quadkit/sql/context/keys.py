"""Db-layer context keys.

Pure frozen data constants — zero side-effects at import time.
Actual ``ContextVar`` instances are created by the
``create_db_context`` factory in the composition root.
"""

from __future__ import annotations

from typing import Any

from quadkit.primitives.context import ContextKey

# -- Request-scoped keys -------------------------------------------------------

REQUEST_ID: ContextKey[str] = ContextKey("quadkit_db.request_id")
TENANT_ID: ContextKey[str] = ContextKey("quadkit_db.tenant_id")
USER_ID: ContextKey[str] = ContextKey("quadkit_db.user_id")
USER: ContextKey[Any] = ContextKey("quadkit_db.user")

# -- Rate-limit keys -----------------------------------------------------------

RATE_LIMIT_REMAINING: ContextKey[int] = ContextKey(
    "quadkit_db.rate_limit_remaining",
)
RATE_LIMIT_LIMIT: ContextKey[int] = ContextKey(
    "quadkit_db.rate_limit_limit",
)
RATE_LIMIT_RESET: ContextKey[int] = ContextKey(
    "quadkit_db.rate_limit_reset",
)

# -- Aggregate (used by the factory) -------------------------------------------

DB_KEYS: tuple[ContextKey[Any], ...] = (
    REQUEST_ID,
    TENANT_ID,
    USER_ID,
    USER,
    RATE_LIMIT_REMAINING,
    RATE_LIMIT_LIMIT,
    RATE_LIMIT_RESET,
)

__all__ = [
    "DB_KEYS",
    "RATE_LIMIT_LIMIT",
    "RATE_LIMIT_REMAINING",
    "RATE_LIMIT_RESET",
    "REQUEST_ID",
    "TENANT_ID",
    "USER",
    "USER_ID",
]
