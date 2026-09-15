"""Tests for ContextVarRegistry and ContextKey."""

from __future__ import annotations

import contextvars
import dataclasses

import pytest

from quadkit.primitives.context_keys import (
    CORRELATION_ID,
    DEFAULT_KEYS,
    REQUEST_ID,
    TENANT_ID,
    TRACE_FLAGS,
    ContextKey,
)
from quadkit.primitives.context_registry import ContextVarRegistry


@pytest.fixture
def registry() -> ContextVarRegistry:
    return ContextVarRegistry()


class TestContextKey:
    def test_frozen_data(self) -> None:
        key = ContextKey("foo", default="bar")
        assert key.name == "foo"
        assert key.default == "bar"
        with pytest.raises(dataclasses.FrozenInstanceError):
            key.name = "other"  # type: ignore[misc]

    def test_default_none(self) -> None:
        assert ContextKey("plain").default is None


class TestWellKnownKeys:
    def test_trace_flags_default(self) -> None:
        assert TRACE_FLAGS.default == "01"

    def test_default_keys_members(self) -> None:
        assert REQUEST_ID in DEFAULT_KEYS
        assert TENANT_ID in DEFAULT_KEYS
        assert CORRELATION_ID in DEFAULT_KEYS
        assert len(DEFAULT_KEYS) == 11

    def test_names_are_unique(self) -> None:
        names = [k.name for k in DEFAULT_KEYS]
        assert len(names) == len(set(names))


class TestRegistration:
    def test_register_key_creates_var(self, registry: ContextVarRegistry) -> None:
        registry.register_key(REQUEST_ID)
        assert registry.has("request_id")

    def test_register_key_idempotent(self, registry: ContextVarRegistry) -> None:
        registry.register_key(REQUEST_ID)
        registry.register_key(REQUEST_ID)  # no error
        assert registry.has("request_id")

    def test_reject_non_contextvar(self, registry: ContextVarRegistry) -> None:
        with pytest.raises(TypeError, match="Expected ContextVar"):
            registry.register("bad", "not-a-var")  # type: ignore[arg-type]

    def test_no_overwrite(self, registry: ContextVarRegistry) -> None:
        var1 = contextvars.ContextVar("dup", default=None)
        var2 = contextvars.ContextVar("dup", default=None)
        registry.register("dup", var1)
        from quadkit.contracts.exceptions import RegistryAlreadyExistsError

        with pytest.raises(RegistryAlreadyExistsError):
            registry.register("dup", var2)  # type: ignore[arg-type]


class TestTypedAccessors:
    def test_get_typed_default_when_unset(self, registry: ContextVarRegistry) -> None:
        registry.register_key(REQUEST_ID)
        assert registry.get_typed(REQUEST_ID) is None

    def test_get_typed_explicit_default_when_key_default_none(self, registry: ContextVarRegistry) -> None:
        # REQUEST_ID has no key default → the ContextVar's own default is
        # None → the explicit default is surfaced.
        registry.register_key(REQUEST_ID)
        assert registry.get_typed(REQUEST_ID, default="explicit") == "explicit"

    def test_key_default_surfaces_when_var_unset(self, registry: ContextVarRegistry) -> None:
        key = ContextKey("k", default="key-default")
        registry.register_key(key)
        # The var was created with the key's default, so get() returns it.
        assert registry.get_typed(key) == "key-default"

    def test_set_and_get_typed(self, registry: ContextVarRegistry) -> None:
        registry.register_key(REQUEST_ID)
        token = registry.set_typed(REQUEST_ID, "req-123")
        assert registry.get_typed(REQUEST_ID) == "req-123"
        registry.reset_typed(REQUEST_ID, token)
        assert registry.get_typed(REQUEST_ID) is None

    def test_reset_guard_noop_for_unregistered_key(self, registry: ContextVarRegistry) -> None:
        var = contextvars.ContextVar("standalone", default=None)
        token = var.set(7)
        # _reset guards on has() — unregistered key must not raise.
        registry._reset("never-registered", token)  # noqa: SLF001

    def test_set_value_string_key(self, registry: ContextVarRegistry) -> None:
        registry.register("dyn", contextvars.ContextVar("dyn", default=None))
        token = registry.set_value("dyn", 1)
        assert registry.get_value("dyn") == 1
        registry.reset_value("dyn", token)
        assert registry.get_value("dyn") is None

    def test_set_unregistered_raises(self, registry: ContextVarRegistry) -> None:
        with pytest.raises(RuntimeError, match="not registered"):
            registry.set_value("missing", 1)

    def test_get_unregistered_returns_default(self, registry: ContextVarRegistry) -> None:
        assert registry.get_value("missing") is None
        assert registry.get_value("missing", default="dflt") == "dflt"


class TestSnapshotAndResolve:
    def test_snapshot_skips_none_and_unset(self, registry: ContextVarRegistry) -> None:
        registry.register_key(REQUEST_ID)
        registry.register_key(TENANT_ID)
        registry.set_typed(REQUEST_ID, "r-1")
        # TENANT_ID remains unset (None)
        assert registry.snapshot() == {"request_id": "r-1"}

    def test_snapshot_includes_values(self, registry: ContextVarRegistry) -> None:
        registry.register_key(REQUEST_ID)
        registry.register_key(TENANT_ID)
        registry.set_typed(REQUEST_ID, "r-1")
        registry.set_typed(TENANT_ID, "t-1")
        snap = registry.snapshot()
        assert snap == {"request_id": "r-1", "tenant_id": "t-1"}

    def test_resolve_var_registered(self, registry: ContextVarRegistry) -> None:
        registry.register_key(REQUEST_ID)
        var = registry.resolve_var(REQUEST_ID)
        assert isinstance(var, contextvars.ContextVar)

    def test_resolve_var_unregistered_raises(self, registry: ContextVarRegistry) -> None:
        with pytest.raises(KeyError, match="not registered"):
            registry.resolve_var(REQUEST_ID)


class TestContextIsolation:
    def test_values_isolated_across_contexts(self, registry: ContextVarRegistry) -> None:
        registry.register_key(REQUEST_ID)

        ctx_a = contextvars.copy_context()

        def in_a() -> str | None:
            registry.set_typed(REQUEST_ID, "in-a")
            return registry.get_typed(REQUEST_ID)  # type: ignore[return-value]

        result_a = ctx_a.run(in_a)
        assert result_a == "in-a"
        # Outside the context the value is back to default.
        assert registry.get_typed(REQUEST_ID) is None
