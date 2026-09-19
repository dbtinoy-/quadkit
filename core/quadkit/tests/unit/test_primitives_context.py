"""Tests for primitives/context.py — ContextKey and ContextVarRegistry."""

from __future__ import annotations

import contextvars

import pytest

from quadkit.primitives.context import (
    TENANT_ID,
    USER_ID,
    ContextKey,
    ContextVarRegistry,
    create_default_context,
    get_request_context,
    request_scope,
)


class TestContextKey:
    """Tests for ContextKey dataclass."""

    def test_context_key_creation(self) -> None:
        """ContextKey creates with name and optional default."""
        key = ContextKey[str]("user_id")
        assert key.name == "user_id"
        assert key.default is None

    def test_context_key_with_default(self) -> None:
        """ContextKey accepts default value."""
        key = ContextKey[str]("env", default="production")
        assert key.name == "env"
        assert key.default == "production"

    def test_context_key_with_int_default(self) -> None:
        """ContextKey works with integer defaults."""
        key = ContextKey[int]("timeout", default=30)
        assert key.name == "timeout"
        assert key.default == 30

    def test_context_key_is_frozen(self) -> None:
        """ContextKey is frozen (immutable)."""
        key = ContextKey[str]("key")
        with pytest.raises(AttributeError):
            key.name = "new_key"

    def test_context_key_is_hashable(self) -> None:
        """ContextKey can be used in sets/dicts."""
        key1 = ContextKey[str]("a")
        key2 = ContextKey[str]("a")
        key3 = ContextKey[str]("b")

        assert {key1, key2} == {key1}  # key1 == key2
        assert key3 not in {key1}


class TestContextVarRegistry:
    """Tests for ContextVarRegistry class."""

    def test_registry_creation(self) -> None:
        """ContextVarRegistry initializes correctly."""
        registry = ContextVarRegistry()
        assert registry.name == "ContextVarRegistry"
        assert registry.allow_overwrite is False

    def test_register_key_creates_context_var(self) -> None:
        """register_key creates a ContextVar for the key."""
        registry = ContextVarRegistry()
        key = ContextKey[str]("request_id")

        registry.register_key(key)
        assert registry.has("request_id")

    def test_register_key_idempotent(self) -> None:
        """register_key can be called multiple times safely."""
        registry = ContextVarRegistry()
        key = ContextKey[str]("request_id")

        registry.register_key(key)
        registry.register_key(key)  # Should not raise
        assert registry.has("request_id")

    def test_get_typed_returns_default(self) -> None:
        """get_typed returns the key's default when not set."""
        registry = ContextVarRegistry()
        key = ContextKey[str]("env", default="dev")

        result = registry.get_typed(key)
        assert result == "dev"

    def test_get_typed_with_override_default(self) -> None:
        """get_typed uses override default when key not set."""
        registry = ContextVarRegistry()
        key = ContextKey[str]("env", default="dev")

        result = registry.get_typed(key, default="prod")
        assert result == "prod"

    def test_set_typed_and_get_typed_roundtrip(self) -> None:
        """set_typed and get_typed work together."""
        registry = ContextVarRegistry()
        key = ContextKey[str]("user")
        registry.register_key(key)

        token = registry.set_typed(key, "alice")
        try:
            result = registry.get_typed(key)
            assert result == "alice"
        finally:
            registry.reset_typed(key, token)

    def test_set_typed_returns_token(self) -> None:
        """set_typed returns a token for reset."""
        registry = ContextVarRegistry()
        key = ContextKey[str]("trace_id")
        registry.register_key(key)

        token = registry.set_typed(key, "abc-123")
        assert token is not None

    def test_reset_typed_restores_default(self) -> None:
        """reset_typed restores the value to default."""
        registry = ContextVarRegistry()
        key = ContextKey[str]("trace_id", default="default-trace")
        registry.register_key(key)

        token = registry.set_typed(key, "custom-trace")
        registry.reset_typed(key, token)

        result = registry.get_typed(key)
        assert result == "default-trace"

    def test_get_returns_context_var(self) -> None:
        """get returns the ContextVar directly."""
        registry = ContextVarRegistry()
        key = ContextKey[int]("count", default=0)

        registry.register_key(key)
        var = registry.get("count")
        assert isinstance(var, contextvars.ContextVar)

    def test_validate_rejects_non_context_var(self) -> None:
        """_validate raises TypeError for non-ContextVar."""
        registry = ContextVarRegistry()

        with pytest.raises(TypeError, match="Expected ContextVar"):
            registry.register("not_a_var", "string_value")

    def test_unregister_removes_context_var(self) -> None:
        """unregister removes the registered key."""
        registry = ContextVarRegistry()
        key = ContextKey[str]("temp")

        registry.register_key(key)
        assert registry.has("temp")

        registry.unregister("temp")
        assert not registry.has("temp")

    def test_keys_returns_registered_key_names(self) -> None:
        """keys returns registered key names."""
        registry = ContextVarRegistry()
        key1 = ContextKey[str]("key1")
        key2 = ContextKey[str]("key2")

        registry.register_key(key1)
        registry.register_key(key2)

        assert set(registry.keys()) == {"key1", "key2"}

    def test_values_returns_context_vars(self) -> None:
        """values returns the ContextVar instances."""
        registry = ContextVarRegistry()
        key = ContextKey[str]("test_key")

        registry.register_key(key)
        vars_list = list(registry.values())

        assert len(vars_list) == 1
        assert isinstance(vars_list[0], contextvars.ContextVar)


def test_request_scope_sets_user_and_tenant_ids() -> None:
    ctx = create_default_context()

    with request_scope(
        ctx.registry,
        request_id="req-1",
        user_id="user-1",
        tenant_id="tenant-1",
    ):
        current = get_request_context(ctx.registry)
        assert current is not None
        assert current.user_id == "user-1"
        assert current.tenant_id == "tenant-1"
        assert ctx.get(USER_ID) == "user-1"
        assert ctx.get(TENANT_ID) == "tenant-1"
