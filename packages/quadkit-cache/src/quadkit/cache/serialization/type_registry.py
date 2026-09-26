"""Registered type registry for @cacheable domain-model reconstruction.

The registry is the authorization boundary for type-tagged cache payloads:
a ``(module, qualname)`` tag is only ever resolved against classes that were
explicitly registered at boot time — never imported from cache data.
"""

from __future__ import annotations

from typing import Any


class TypeRegistry:
    """Map ``(module, qualname)`` tags to model classes.

    Registration validates that the class exposes a ``model_validate``
    classmethod (fail fast at registration, not at gadget time).

    Note:
        Cache data is untrusted input. An unregistered tag is never
        imported; it is refused by lookup.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._models: dict[tuple[str, str], type[Any]] = {}

    def register(self, model_cls: type) -> None:
        """Register a model class for reconstruction.

        Args:
            model_cls: Class exposing a ``model_validate`` classmethod.

        Raises:
            TypeError: If the class does not expose ``model_validate``.
        """
        if not callable(getattr(model_cls, "model_validate", None)):
            raise TypeError(
                f"{model_cls.__module__}.{model_cls.__qualname__} must expose "
                "a model_validate classmethod to be cache-reconstructible",
            )
        self._models[(model_cls.__module__, model_cls.__qualname__)] = model_cls

    def get(self, module: str, qualname: str) -> type[Any] | None:
        """Return the registered class for a tag, or None when unregistered.

        Args:
            module: Module name of the type tag.
            qualname: Qualified name of the type tag.

        Returns:
            The registered class, or None.
        """
        return self._models.get((module, qualname))

    def clear(self) -> None:
        """Remove all registrations (test isolation)."""
        self._models.clear()


DEFAULT_REGISTRY = TypeRegistry()

__all__ = ["DEFAULT_REGISTRY", "TypeRegistry"]
