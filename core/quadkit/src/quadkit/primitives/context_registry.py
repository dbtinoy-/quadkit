"""Context variable registry for the Quadkit Framework.

Injectable storage backend managing ``contextvars.ContextVar`` instances
keyed by name; consumed by :class:`quadkit.primitives.context.Context`.
"""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING, Any, TypeVar, cast

from quadkit.primitives.registry import Registry

if TYPE_CHECKING:
    from quadkit.primitives.context_keys import ContextKey

T = TypeVar("T")


class ContextVarRegistry(Registry[str, contextvars.ContextVar[Any]]):
    """Manages ``contextvars.ContextVar`` instances keyed by name."""

    def __init__(self, name: str = "ContextVarRegistry") -> None:
        super().__init__(name=name, allow_overwrite=False)

    def _validate(self, key: str, value: object) -> None:
        """Validate a candidate registration value.

        Typed as ``object`` (a widening override) so the defensive
        isinstance guard stays statically reachable.
        """
        if not isinstance(value, contextvars.ContextVar):
            msg = f"Expected ContextVar, got {type(value).__name__} for key '{key}'"
            raise TypeError(msg)

    # -- registration ------------------------------------------------------

    def register_key(self, key: ContextKey[Any]) -> None:
        """Create and register a ``ContextVar`` for *key* (idempotent)."""
        if not self.has(key.name):
            var: contextvars.ContextVar[Any] = contextvars.ContextVar(
                key.name, default=key.default
            )
            self.register(key.name, var)

    # -- typed accessors ---------------------------------------------------

    def get_typed(self, key: ContextKey[T], default: T | None = None) -> T | None:
        """Read the current value for a typed key."""
        effective = default if default is not None else key.default
        return cast("T | None", self._read(key.name, effective))

    def set_typed(self, key: ContextKey[T], value: T) -> contextvars.Token[T | None]:
        """Write a value for a typed key; returns a reset token."""
        return self._write(key.name, value)

    def reset_typed(
        self,
        key: ContextKey[T],
        token: contextvars.Token[T | None],
    ) -> None:
        """Reset a typed key using a token from ``set_typed``."""
        self._reset(key.name, token)

    # -- string-keyed accessors (dynamic / runtime keys) -------------------

    def get_value(self, key: str, default: Any = None) -> Any:
        """Read the current value by string key."""
        return self._read(key, default)

    def set_value(self, key: str, value: Any) -> contextvars.Token[Any]:
        """Write a value by string key; returns a reset token."""
        return self._write(key, value)

    def reset_value(self, key: str, token: contextvars.Token[Any]) -> None:
        """Reset a context variable by string key."""
        self._reset(key, token)

    # -- introspection -----------------------------------------------------

    def resolve_var(self, key: ContextKey[T]) -> contextvars.ContextVar[T | None]:
        """Return the underlying ``ContextVar`` (advanced use)."""
        if not self.has(key.name):
            raise KeyError(f"Context key '{key.name}' is not registered.")
        # has() checked above: resolve() keeps the non-Optional return type.
        return self.resolve(key.name)

    def snapshot(self) -> dict[str, Any]:
        """Return a dict of all non-``None`` context values."""
        result: dict[str, Any] = {}
        for name, var in self.items():
            try:
                val = var.get()
                if val is not None:
                    result[name] = val
            except LookupError:
                pass
        return result

    # -- private helpers ---------------------------------------------------

    def _read(self, key: str, default: Any) -> Any:
        if not self.has(key):
            return default
        var = self.resolve(key)
        try:
            val = var.get()
            return val if val is not None else default
        except LookupError:
            return default

    def _write(self, key: str, value: Any) -> contextvars.Token[Any]:
        if not self.has(key):
            msg = (
                f"Context key '{key}' is not registered. "
                "Register a ContextKey before setting values."
            )
            raise RuntimeError(msg)
        return self.resolve(key).set(value)

    def _reset(self, key: str, token: contextvars.Token[Any]) -> None:
        if self.has(key):
            self.resolve(key).reset(token)


__all__ = [
    "ContextVarRegistry",
]
