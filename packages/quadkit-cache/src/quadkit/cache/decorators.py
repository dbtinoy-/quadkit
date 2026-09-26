from __future__ import annotations

from collections.abc import Callable
import functools
from typing import TYPE_CHECKING, Any, TypeVar

from quadkit.logging import get_logger
from quadkit.result import Ok
from quadkit.serialization import dumps_str

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache import CacheBackendProtocol

from quadkit.cache.backends import _compute_hash

logger = get_logger(__name__)
F = TypeVar("F", bound=Callable[..., Any])

# Cache envelope keys.  Stored alongside serialised domain objects so the
# decorator can reconstruct the original Python types on retrieval — but
# only for types registered in the type registry (deny-by-default: a cache
# payload may originate from a shared, attacker-influenced store).
_KEY_MODULE = "__lx_module__"
_KEY_CLASS = "__lx_class__"
_KEY_DATA = "__lx_data__"
_KEY_RESULT = "__lx_result__"
_KEY_VALUE = "__lx_value__"


def _is_domain_model(obj: Any) -> bool:
    """Return True if *obj* supports the model_dump / model_validate protocol.

    This intentionally uses duck-typing rather than an isinstance check so that
    both :class:`quadkit.domain.DomainModel` subclasses **and** Pydantic
    ``BaseModel`` subclasses (which implement the same interface) are handled
    correctly.  Any object that exposes ``model_dump`` on the instance and
    ``model_validate`` as a classmethod qualifies.

    Args:
        obj: The value to inspect.

    Returns:
        ``True`` if *obj* can be serialised via ``model_dump`` and
        reconstructed via ``model_validate``.
    """
    return (
        hasattr(obj, "model_dump")
        and callable(getattr(obj, "model_dump", None))
        and hasattr(type(obj), "model_validate")
        and callable(getattr(type(obj), "model_validate", None))
    )


def _serialize(value: Any) -> Any:
    """Prepare *value* for JSON-safe cache storage.

    Domain models are serialised to a type-tagged envelope so they can be
    faithfully reconstructed on retrieval.  Lists are serialised element-wise.
    All other values are returned unchanged (they must be JSON-serialisable).

    Args:
        value: The value to prepare for storage.

    Returns:
        A JSON-serialisable representation of *value*.
    """
    if _is_domain_model(value):
        cls = type(value)
        return {
            _KEY_MODULE: cls.__module__,
            _KEY_CLASS: cls.__qualname__,
            _KEY_DATA: value.model_dump(),
        }
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def _deserialize(value: Any) -> Any:
    """Reconstruct *value* from a cache-retrieved payload.

    Type tags are resolved against the registered type registry — never
    imported from cache data. An unregistered tag yields a warning and the
    raw payload, matching the fail-closed policy for untrusted cache input.

    Args:
        value: A JSON-decoded cache payload.

    Returns:
        The original value, with registered domain models reconstructed
        where possible; unregistered envelopes degrade to their raw data.
    """
    if isinstance(value, dict) and _KEY_MODULE in value and _KEY_CLASS in value:
        from quadkit.cache.serialization.type_registry import DEFAULT_REGISTRY

        model_cls = DEFAULT_REGISTRY.get(value[_KEY_MODULE], value[_KEY_CLASS])
        if model_cls is None:
            logger.warning(
                "cache_deserialize_unregistered_type",
                module=value.get(_KEY_MODULE),
                cls=value.get(_KEY_CLASS),
                hint="register the model class in the type registry to enable reconstruction",
            )
            return value.get(_KEY_DATA, value)
        try:
            return model_cls.model_validate(value[_KEY_DATA])
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "cache_deserialize_failed",
                module=value.get(_KEY_MODULE),
                cls=value.get(_KEY_CLASS),
                error=str(exc),
            )
            return value.get(_KEY_DATA, value)
    if isinstance(value, list):
        return [_deserialize(item) for item in value]
    return value


def cacheable(
    ttl: int | None = 300,
    key_prefix: str = "",
    skip_on_error: bool = True,
) -> Callable[[F], F]:
    """Cache the return value of an async method using the injected CacheBackend.

    The decorator resolves the cache backend from ``self._cache`` on the target
    instance. The cache key is derived from the method name, prefix, and a
    SHA-256 hash of the serialized arguments.

    Supports methods that return ``Result[T, E]``:
    - ``Ok(value)`` results are cached; the inner value is unwrapped, serialised,
      and re-wrapped in ``Ok`` on retrieval.
    - ``Err(...)`` results are **never** cached — errors propagate on every call.

    Supports domain model return values (or ``Result``-wrapped domain models):
    - Domain models are serialised to a type-tagged JSON envelope and
      reconstructed via ``model_validate`` on retrieval, preserving type
      identity across the JSON round-trip.
    - Reconstruction is **deny-by-default**: type tags are only resolved
      against the registered type registry
      (:data:`~quadkit.cache.serialization.type_registry.DEFAULT_REGISTRY`);
      a payload naming an unregistered type degrades to its raw data.

    Args:
        ttl: Time-to-live in seconds. ``None`` disables expiry.
        key_prefix: Optional prefix prepended to the generated cache key.
        skip_on_error: When ``True``, cache misses on backend errors gracefully
            fall through to the original method. When ``False``, errors propagate.

    Returns:
        Decorator that wraps an async method with cache-aside logic.

    Example::

        from quadkit.cache.serialization.type_registry import DEFAULT_REGISTRY

        DEFAULT_REGISTRY.register(User)

        class UserService:
            def __init__(self, cache: CacheBackendProtocol) -> None:
                self._cache = cache

            @cacheable(ttl=60, key_prefix="users")
            async def get_user(self, user_id: str) -> Result[User, DomainError]:
                return await self._repo.find(user_id)
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            cache: CacheBackendProtocol | None = getattr(self, "_cache", None)
            if cache is None:
                return await fn(self, *args, **kwargs)

            # Build cache key — handle non-serializable args gracefully
            try:
                raw_key = dumps_str({"args": args, "kwargs": kwargs})
            except Exception as exc:
                if not skip_on_error:
                    raise
                logger.warning(
                    "cache_key_build_failed", method=fn.__qualname__, error=str(exc)
                )
                return await fn(self, *args, **kwargs)

            cache_key = f"{key_prefix}:{fn.__qualname__}:{_compute_hash(raw_key, 'sha256')[:16]}"

            # -- Cache read --------------------------------------------------
            try:
                cached = await cache.get(cache_key)
                # Backends that return Result[T | None, CacheError] are
                # unwrapped here so hit/miss logic is backend-agnostic.
                if hasattr(cached, "is_ok"):
                    cached = cached.unwrap() if cached.is_ok() else None  # type: ignore[assignment]

                if cached is not None:
                    if isinstance(cached, dict) and cached.get(_KEY_RESULT):
                        # Re-wrap a previously cached Result Ok value and
                        # reconstruct any domain model stored inside.
                        return Ok(_deserialize(cached[_KEY_VALUE]))
                    return _deserialize(cached)
            except Exception as exc:
                if not skip_on_error:
                    raise
                logger.warning("cache_get_failed", key=cache_key, error=str(exc))

            # -- Execute the original method ---------------------------------
            result = await fn(self, *args, **kwargs)

            # -- Cache write -------------------------------------------------
            try:
                is_result = hasattr(result, "is_ok")
                if is_result:
                    if result.is_err():
                        # Errors are never cached.
                        return result
                    # Store the inner Ok value in a Result envelope so the
                    # reader knows to re-wrap it on retrieval.
                    cache_value = {
                        _KEY_RESULT: True,
                        _KEY_VALUE: _serialize(result.unwrap()),
                    }
                else:
                    cache_value = _serialize(result)
                await cache.set(cache_key, cache_value, ttl=ttl)
            except Exception as exc:
                if not skip_on_error:
                    raise
                logger.warning("cache_set_failed", key=cache_key, error=str(exc))

            return result

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["cacheable"]
