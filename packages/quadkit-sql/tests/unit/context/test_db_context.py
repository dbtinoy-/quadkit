"""Tests for the injectable db-layer context (DbContext + factory)."""

from __future__ import annotations

import asyncio
import contextvars

import pytest

from quadkit.primitives.context import ContextKey, create_default_context
from quadkit.sql.context import create_db_context
from quadkit.sql.context.db_context import DbContext
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


@pytest.fixture
def db_ctx() -> DbContext:
    return create_db_context()


class TestFactory:
    def test_registers_all_db_keys(self, db_ctx: DbContext) -> None:
        for key in DB_KEYS:
            assert db_ctx.registry.has(key.name), key.name

    def test_extra_keys_registered(self) -> None:
        custom = ContextKey("quadkit_db.custom")
        ctx = create_db_context(extra_keys=(custom,))
        assert ctx.registry.has(custom.name)

    def test_core_ctx_reference(self) -> None:
        core = create_default_context()
        ctx = create_db_context(core_ctx=core)
        assert ctx.core_ctx is core
        assert create_db_context().core_ctx is None


class TestGenericAccess:
    def test_get_unset_returns_none(self, db_ctx: DbContext) -> None:
        assert db_ctx.get(REQUEST_ID) is None

    def test_get_default_when_unset(self, db_ctx: DbContext) -> None:
        assert db_ctx.get(REQUEST_ID, "fallback") == "fallback"

    def test_set_get_roundtrip_and_token_reset(self, db_ctx: DbContext) -> None:
        token = db_ctx.set(REQUEST_ID, "req-1")
        assert db_ctx.get(REQUEST_ID) == "req-1"
        db_ctx.reset(REQUEST_ID, token)
        assert db_ctx.get(REQUEST_ID) is None

    def test_set_overwrite_restores_original(self, db_ctx: DbContext) -> None:
        db_ctx.set(USER_ID, "u0")
        token = db_ctx.set(USER_ID, "u1")
        assert db_ctx.get(USER_ID) == "u1"
        db_ctx.reset(USER_ID, token)
        assert db_ctx.get(USER_ID) == "u0"

    def test_set_unregistered_key_raises(self, db_ctx: DbContext) -> None:
        stranger = ContextKey("quadkit_db.stranger")
        with pytest.raises(RuntimeError, match="not registered"):
            db_ctx.set(stranger, "x")

    def test_registry_property(self, db_ctx: DbContext) -> None:
        assert isinstance(db_ctx.registry, object)


class TestConvenienceProperties:
    def test_request_id(self, db_ctx: DbContext) -> None:
        token = db_ctx.set(REQUEST_ID, "r-9")
        assert db_ctx.request_id == "r-9"
        db_ctx.reset(REQUEST_ID, token)

    def test_user_id_and_user(self, db_ctx: DbContext) -> None:
        user = {"id": "u-1"}
        db_ctx.set(USER, user)
        assert db_ctx.user is user
        assert db_ctx.user_id is None

    def test_tenant_id(self, db_ctx: DbContext) -> None:
        token = db_ctx.set(TENANT_ID, "acme")
        assert db_ctx.tenant_id == "acme"
        db_ctx.reset(TENANT_ID, token)

    def test_rate_limit_properties(self, db_ctx: DbContext) -> None:
        db_ctx.set(RATE_LIMIT_REMAINING, 42)
        db_ctx.set(RATE_LIMIT_LIMIT, 100)
        db_ctx.set(RATE_LIMIT_RESET, 1700000000)
        assert db_ctx.rate_limit_remaining == 42
        assert db_ctx.rate_limit_limit == 100
        assert db_ctx.rate_limit_reset == 1700000000

    def test_all_none_before_set(self, db_ctx: DbContext) -> None:
        assert db_ctx.request_id is None
        assert db_ctx.user_id is None
        assert db_ctx.tenant_id is None
        assert db_ctx.user is None
        assert db_ctx.rate_limit_remaining is None


class TestTenantBridge:
    def test_scope_with_tenant_id(self, db_ctx: DbContext) -> None:
        token = db_ctx.set_tenant_from_scope({"tenant_id": "acme"})
        assert isinstance(token, contextvars.Token)
        assert db_ctx.tenant_id == "acme"
        db_ctx.reset_tenant(token)
        assert db_ctx.tenant_id is None

    def test_asgi_scope_state_tenant_object(self, db_ctx: DbContext) -> None:
        class _Tenant:
            tenant_id = "globex"

        token = db_ctx.set_tenant_from_scope(
            {"type": "http", "state": {"tenant": _Tenant()}},
        )
        assert db_ctx.tenant_id == "globex"
        db_ctx.reset_tenant(token)

    def test_asgi_scope_state_tenant_without_id(self, db_ctx: DbContext) -> None:
        class _Tenant:
            pass

        assert (
            db_ctx.set_tenant_from_scope({"state": {"tenant": _Tenant()}}) is None
        )

    def test_no_tenant_present(self, db_ctx: DbContext) -> None:
        assert db_ctx.set_tenant_from_scope({}) is None
        assert db_ctx.set_tenant_from_scope({"state": {}}) is None
        assert db_ctx.tenant_id is None

    def test_reset_tenant_none_is_noop(self, db_ctx: DbContext) -> None:
        db_ctx.reset_tenant(None)  # must not raise

    def test_reset_tenant_restores_previous(self, db_ctx: DbContext) -> None:
        db_ctx.set(TENANT_ID, "old")
        token = db_ctx.set_tenant_from_scope({"tenant_id": "new"})
        assert db_ctx.tenant_id == "new"
        db_ctx.reset_tenant(token)
        assert db_ctx.tenant_id == "old"


class TestSnapshot:
    def test_snapshot_empty(self, db_ctx: DbContext) -> None:
        assert db_ctx.snapshot() == {}

    def test_snapshot_non_none_only(self, db_ctx: DbContext) -> None:
        db_ctx.set(REQUEST_ID, "r-1")
        db_ctx.set(TENANT_ID, "acme")
        snap = db_ctx.snapshot()
        assert snap[REQUEST_ID.name] == "r-1"
        assert snap[TENANT_ID.name] == "acme"
        assert USER_ID.name not in snap

    async def test_contextvar_isolation_across_tasks(
        self, db_ctx: DbContext
    ) -> None:
        async def set_in_task() -> str | None:
            db_ctx.set(REQUEST_ID, "task-req")
            await asyncio.sleep(0)
            return db_ctx.request_id

        task_val = await asyncio.create_task(set_in_task())
        assert task_val == "task-req"
        assert db_ctx.request_id is None  # contextvars do not leak across tasks


class TestWiring:
    def test_direct_construction(self) -> None:
        from quadkit.primitives.context import ContextVarRegistry

        registry = ContextVarRegistry(name="manual")
        registry.register_key(REQUEST_ID)
        ctx = DbContext(registry)
        ctx.set(REQUEST_ID, "direct")
        assert ctx.request_id == "direct"

    def test_db_keys_aggregate(self) -> None:
        assert REQUEST_ID in DB_KEYS
        assert TENANT_ID in DB_KEYS
        assert USER in DB_KEYS
        assert len(DB_KEYS) == 7

    def test_key_defaults_are_none(self) -> None:
        for key in DB_KEYS:
            assert key.default is None, key.name
