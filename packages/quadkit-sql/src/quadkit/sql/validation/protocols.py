"""Runtime protocol validation utilities.

Validates that objects actually implement protocol methods at runtime,
preventing AttributeError from incomplete implementations.
"""

from __future__ import annotations

from collections.abc import Callable
import inspect
from typing import Any, TypeVar

from quadkit.contracts.exceptions import ConfigurationError
from quadkit.logging import get_logger

logger = get_logger(__name__)


T = TypeVar("T")
P = TypeVar("P")


class ProtocolValidationError(ConfigurationError):
    """Raised when object doesn't implement protocol."""

    _code: str = "QK_ERR_SQL_036"

    def __init__(
        self,
        protocol: Any,
        obj: object,
        missing_methods: list[str],
    ) -> None:
        """Initialize protocol validation error.

        Args:
            protocol: Protocol class that wasn't satisfied.
            obj: Object that failed validation.
            missing_methods: List of missing method names.
        """
        self.protocol = protocol
        self.obj = obj
        self.missing_methods = missing_methods

        obj_type = type(obj).__name__
        protocol_name = protocol.__name__
        methods = ", ".join(missing_methods)

        super().__init__(
            f"{obj_type} doesn't implement {protocol_name}. Missing methods: {methods}",
            details={
                "protocol": protocol_name,
                "object_type": obj_type,
                "missing_methods": missing_methods,
            },
        )


def validate_protocol(
    obj: object,
    protocol: Any,
    *,
    raise_on_error: bool = True,
) -> bool:
    """Validate that object implements protocol.

    Args:
        obj: Object to validate.
        protocol: Protocol class to check against.
        raise_on_error: If True, raise exception on failure.
            If False, return False on failure.

    Returns:
        True if object implements protocol.

    Raises:
        ProtocolValidationError: If object doesn't implement protocol
            and raise_on_error=True.

    Example:
        >>> from quadkit.contracts.infra.cache import CacheProtocol
        >>> class MyCache:
        ...     async def get(self, key: str) -> Any: ...
        ...     async def set(self, key: str, value: Any) -> None: ...
        >>>
        >>> cache = MyCache()
        >>> validate_protocol(cache, CacheProtocol)  # Raises if invalid
        True
    """
    # Get protocol methods
    protocol_methods = _get_protocol_methods(protocol)

    # Check each method exists on object
    missing_methods: list[str] = []
    for method_name, method_info in protocol_methods.items():
        if not hasattr(obj, method_name):
            missing_methods.append(method_name)
            continue

        # Check method signature matches
        obj_method = getattr(obj, method_name)
        if not callable(obj_method):
            missing_methods.append(f"{method_name} (not callable)")
            continue

        # Validate signature matches protocol
        if not _signatures_compatible(obj_method, method_info):
            missing_methods.append(f"{method_name} (wrong signature)")

    if missing_methods:
        if raise_on_error:
            raise ProtocolValidationError(protocol, obj, missing_methods)
        return False

    logger.debug(
        "Protocol validation passed",
        extra={
            "protocol": protocol.__name__,
            "object_type": type(obj).__name__,
        },
    )
    return True


def _get_protocol_methods(protocol: Any) -> dict[str, inspect.Signature]:
    """Extract methods from protocol class.

    Args:
        protocol: Protocol class.

    Returns:
        Dict mapping method name to signature.
    """
    methods: dict[str, inspect.Signature] = {}

    for name in dir(protocol):
        # Skip private/special methods
        if name.startswith("_"):
            continue

        attr = getattr(protocol, name)

        # Only include callable methods
        if callable(attr):
            sig = inspect.signature(attr)
            methods[name] = sig

    return methods


def _signatures_compatible(
    obj_method: Callable[..., Any],
    protocol_sig: inspect.Signature,
) -> bool:
    """Check if method signature is compatible with protocol.

    Args:
        obj_method: Method from object being validated.
        protocol_sig: Expected signature from protocol.

    Returns:
        True if signatures are compatible.
    """
    try:
        obj_sig = inspect.signature(obj_method)
    except (ValueError, TypeError):
        return False

    # Compare parameter counts (excluding self)
    obj_params = list(filter(lambda p: p.name != "self", obj_sig.parameters.values()))
    protocol_params = list(
        filter(lambda p: p.name != "self", protocol_sig.parameters.values()),
    )

    if len(obj_params) != len(protocol_params):
        return False

    # Perform sophisticated type checking
    for obj_param, protocol_param in zip(obj_params, protocol_params, strict=False):
        # Check parameter names match
        if obj_param.name != protocol_param.name:
            return False

        # Check parameter types are compatible
        if not _types_compatible(obj_param.annotation, protocol_param.annotation):
            return False

    return True


def _types_compatible(obj_type: Any, protocol_type: Any) -> bool:
    """Check if object type is compatible with protocol type.

    Args:
        obj_type: Type annotation from object method
        protocol_type: Type annotation from protocol method

    Returns:
        True if types are compatible
    """
    # Handle Any type (always compatible)
    if protocol_type is Any or obj_type is Any:
        return True

    # Handle None/default types
    if obj_type is inspect.Parameter.empty or protocol_type is inspect.Parameter.empty:
        return True

    # Direct type equality
    if obj_type == protocol_type:
        return True

    # Handle Union types (including Optional)
    try:
        # Check if obj_type is a subtype of protocol_type
        import typing

        if hasattr(typing, "get_origin"):
            obj_origin = typing.get_origin(obj_type)
            protocol_origin = typing.get_origin(protocol_type)

            # Both are generic types
            if obj_origin and protocol_origin:
                if obj_origin != protocol_origin:
                    return False

                obj_args = typing.get_args(obj_type)
                protocol_args = typing.get_args(protocol_type)

                # Check each type argument
                for obj_arg, protocol_arg in zip(obj_args, protocol_args, strict=False):
                    if not _types_compatible(obj_arg, protocol_arg):
                        return False
                return True

            # Protocol expects Union, object provides specific type
            if protocol_origin and protocol_origin in (typing.Union, typing.Optional):
                protocol_args = typing.get_args(protocol_type)
                return any(_types_compatible(obj_type, arg) for arg in protocol_args)

    except (AttributeError, TypeError):
        # Fallback for older Python versions or complex types
        pass

    # Check inheritance relationship
    try:
        # For classes, check if obj_type is a subclass of protocol_type
        if inspect.isclass(obj_type) and inspect.isclass(protocol_type):
            return issubclass(obj_type, protocol_type)
    except TypeError:
        pass

    # String-based comparison for forward references and complex types
    try:
        obj_str = str(obj_type)
        protocol_str = str(protocol_type)

        # Handle forward references (strings)
        if obj_str == protocol_str:
            return True

        # Handle typing module aliases
        if obj_str.replace("typing.", "") == protocol_str.replace("typing.", ""):
            return True

    except (AttributeError, TypeError, ValueError):
        pass

    # Conservative fallback: assume compatible if we can't determine incompatibility
    return True


def ensure_protocol(
    protocol: Any,
) -> Callable[[type[T]], type[T]]:
    """Decorator to validate protocol implementation at instantiation.

    Args:
        protocol: Protocol class to validate against.

    Returns:
        Decorator function.

    Example:
        >>> from quadkit.contracts.infra.cache import CacheProtocol
        >>> @ensure_protocol(CacheProtocol)
        ... class RedisCache:
        ...     async def get(self, key: str) -> Any: ...
        ...     async def set(self, key: str, value: Any) -> None: ...
        ...     # Missing delete() and clear()!
        >>>
        >>> cache = RedisCache()  # Raises ProtocolValidationError
    """

    def decorator(cls: type[T]) -> type[T]:
        original_init = cls.__init__

        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            # Call original __init__
            original_init(self, *args, **kwargs)

            # Validate protocol
            validate_protocol(self, protocol)

        # Use object.__setattr__ to bypass mypy's method assignment check
        object.__setattr__(cls, "__init__", new_init)
        return cls

    return decorator
