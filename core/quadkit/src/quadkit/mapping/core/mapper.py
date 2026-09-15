"""Registry-based object mapper for transforming objects between types.

Provides a clean way to convert domain models to DTOs and vice versa,
using registered mapping functions instead of ad-hoc conversion logic.
"""

from __future__ import annotations

import dataclasses
from threading import Lock
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    TypeVar,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from quadkit.logging import get_logger
from quadkit.mapping.exceptions import MappingExecutionError
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core.validation import ValidatorProtocol
    from quadkit.mapping.config import MappingConfig

logger = get_logger(__name__)

S = TypeVar("S")
D = TypeVar("D")


class MappingRegistry:
    """Central registry for object-to-object mapping functions.

    Thread-safe registry using an internal lock for registration/unregistration.
    Read operations remain lock-free.

    Stores mapping functions keyed by (source_type, dest_type) tuples,
    enabling type-safe object transformation without scattered conversion logic.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._mappings: dict[tuple[type, type], Callable[..., Any]] = {}

    def register(
        self,
        source_type: type[S],
        dest_type: type[D],
        mapper_func: Callable[[S], D],
    ) -> None:
        """Register a mapping function from source_type to dest_type.

        Args:
            source_type: The type to map from.
            dest_type: The type to map to.
            mapper_func: A callable that accepts a source instance and returns a dest instance.

        Raises:
            ValueError: If a mapping for this pair is already registered.
        """
        key = (source_type, dest_type)
        with self._lock:
            if key in self._mappings:
                msg = f"Mapping from {source_type.__name__} to {dest_type.__name__} already registered"
                raise ValueError(msg)
            self._mappings[key] = mapper_func
        logger.debug(
            "mapping.registered",
            source=source_type.__name__,
            dest=dest_type.__name__,
        )

    def has(self, source_type: type, dest_type: type) -> bool:
        """Check if a mapping exists for the given type pair.

        Args:
            source_type: The type to map from.
            dest_type: The type to map to.

        Returns:
            True if a mapping is registered for this pair.
        """
        return (source_type, dest_type) in self._mappings

    def get(self, source_type: type, dest_type: type) -> Callable[..., Any] | None:
        """Retrieve the mapping function for a type pair, or None.

        Args:
            source_type: The type to map from.
            dest_type: The type to map to.

        Returns:
            The registered mapper function, or None if not found.
        """
        return self._mappings.get((source_type, dest_type))

    def unregister(self, source_type: type, dest_type: type) -> None:
        """Remove a mapping for the given type pair.

        Args:
            source_type: The type to map from.
            dest_type: The type to map to.

        Raises:
            KeyError: If no mapping exists for this pair.
        """
        key = (source_type, dest_type)
        with self._lock:
            if key not in self._mappings:
                msg = f"No mapping from {source_type.__name__} to {dest_type.__name__}"
                raise KeyError(msg)
            del self._mappings[key]


class ObjectMapperImpl:
    """High-level object mapper that uses a MappingRegistry to transform objects.

    Wraps a MappingRegistry and provides a clean map() API for converting
    between registered type pairs.
    """

    def __init__(
        self,
        registry: MappingRegistry | None = None,
        config: MappingConfig | None = None,
    ) -> None:
        self._registry = registry or MappingRegistry()
        from quadkit.mapping.config import MappingConfig as _MappingConfig

        self._config = config or _MappingConfig()

    @property
    def registry(self) -> MappingRegistry:
        """Access the underlying mapping registry.

        Returns:
            The MappingRegistry instance used by this mapper.
        """
        return self._registry

    def register(
        self,
        source_type: type[S],
        dest_type: type[D],
        mapper_func: Callable[[S], D],
    ) -> None:
        """Register a mapping function (convenience delegation to registry).

        Args:
            source_type: The type to map from.
            dest_type: The type to map to.
            mapper_func: A callable that accepts a source and returns a dest.
        """
        self._registry.register(source_type, dest_type, mapper_func)

    def map(
        self,
        source: S,
        dest_type: type[D],
        *,
        validate: bool = False,
        validator: ValidatorProtocol | None = None,
    ) -> D:
        """Map a source object to the destination type using registered mapping.

        Args:
            source: The source object to transform.
            dest_type: The target type to produce.
            validate: Whether to validate the result after mapping.
            validator: Optional validator to use.

        Returns:
            A new instance of dest_type.

        Raises:
            MappingNotFoundError: If no mapping is registered for this type pair.
            MappingExecutionError: If validation fails.
        """
        source_type = type(source)
        mapper_func = self._registry.get(source_type, dest_type)
        if mapper_func is None:
            from quadkit.mapping.exceptions import MappingNotFoundError

            raise MappingNotFoundError(source_type, dest_type)

        try:
            result = mapper_func(source)
        except MappingExecutionError:
            raise
        except (
            Exception
        ) as exc:  # any non-MappingExecutionError re-raised as domain error
            raise MappingExecutionError(
                f"Mapper from {source_type.__name__!r} to {dest_type.__name__!r} raised an error"
            ) from exc

        if validate:
            self._validate_result(result, validator)

        return cast("D", result)

    def map_many(
        self,
        sources: list[S],
        dest_type: type[D],
        *,
        validate: bool = False,
        validator: ValidatorProtocol | None = None,
    ) -> list[D]:
        """Map a list of source objects to the destination type.

        Args:
            sources: List of source objects.
            dest_type: The target type for each.
            validate: Whether to validate results.
            validator: Optional validator to use.

        Returns:
            List of mapped destination instances.
        """
        return [
            self.map(s, dest_type, validate=validate, validator=validator)
            for s in sources
        ]

    def try_map(
        self,
        source: S,
        dest_type: type[D],
        *,
        validate: bool = False,
        validator: ValidatorProtocol | None = None,
    ) -> Result[D, MappingExecutionError]:
        """Map source to dest_type, returning Result instead of raising.

        Returns:
            ``Ok(result)`` on success, ``Err(MappingExecutionError)`` on failure.
        """
        try:
            return Ok(
                self.map(source, dest_type, validate=validate, validator=validator)
            )
        except MappingExecutionError as exc:
            return Err(exc)
        except (TypeError, AttributeError, ValueError, KeyError) as exc:
            return Err(MappingExecutionError(str(exc)))

    def try_map_many(
        self,
        sources: list[S],
        dest_type: type[D],
        *,
        validate: bool = False,
        validator: ValidatorProtocol | None = None,
    ) -> Result[list[D], MappingExecutionError]:
        """Map list of sources, returning Result instead of raising.

        Returns:
            ``Ok(results)`` on success, ``Err(MappingExecutionError)`` on first failure.
        """
        results: list[D] = []
        for s in sources:
            r = self.try_map(s, dest_type, validate=validate, validator=validator)
            if r.is_err():
                return Err(r.unwrap_err())
            results.append(r.unwrap())
        return Ok(results)

    def auto_map(
        self,
        source: S,
        dest_type: type[D],
        *,
        validate: bool = False,
        validator: ValidatorProtocol | None = None,
    ) -> D:
        """Automatically map *source* to *dest_type* by matching field names.

        Extracts fields from the source (via ``model_dump``, ``asdict``
        or ``vars``) and constructs the destination using matching field
        names.  Extra fields are ignored; missing fields that have
        defaults are skipped.

        Args:
            source: The source object.
            dest_type: The target type to construct.
            validate: Whether to validate the result after mapping.
            validator: Optional validator to use.

        Returns:
            A new instance of *dest_type*.

        Raises:
            MappingExecutionError: If validation fails or strict mode is enabled
                and required fields are missing.
        """
        source_data = _extract_fields(source)

        # Pydantic v2 models report their typed fields via model_fields, not
        # via __init__ type hints (which only expose the synthetic *data* param).
        if hasattr(dest_type, "model_fields"):
            hints = {
                name: field.annotation
                for name, field in dest_type.model_fields.items()  # type: ignore[attr-defined]
            }
        else:
            hints = get_type_hints(dest_type.__init__)
            hints.pop("return", None)

        # perform a deep/nested mapping: if a field value itself appears to be
        # an object and the destination field type is a class with a registered
        # mapping, the mapper will be invoked recursively.
        matched: dict[str, Any] = {}
        for k, v in source_data.items():
            if k not in hints:
                continue
            dest_hint = hints[k]
            # unwrap Annotated if needed
            if get_origin(dest_hint) is Annotated:
                dest_hint = get_args(dest_hint)[0]

            # begin with original value; we may transform it
            value: Any = v

            # if a direct mapping is registered for the value's type → dest_hint,
            # use it. this handles both simple and recursive mappings.
            if self._registry.has(type(value), dest_hint):
                matched[k] = self.map(value, dest_hint)
                continue

            # otherwise, attempt a shallow recursive auto-map for nested objects
            # when the destination hint appears to be a dataclass or similar.
            if (
                value is not None
                and isinstance(dest_hint, type)
                and not isinstance(value, dest_hint)
                and hasattr(dest_hint, "__dataclass_fields__")
            ):
                try:
                    value = self.auto_map(value, dest_hint)
                except Exception as exc:  # noqa: BLE001  # pragma: no cover - best effort
                    logger.debug("auto_map_type_conversion_failed", error=str(exc))

            matched[k] = value

        # Strict mode: check for missing required fields
        if self._config.strict:
            import inspect

            sig = inspect.signature(dest_type.__init__)
            for param_name, param in sig.parameters.items():
                if param_name in ("self", "args", "kwargs"):
                    continue
                if (
                    param_name not in matched
                    and param.default is inspect.Parameter.empty
                ):
                    raise MappingExecutionError(
                        f"Strict mode: required field '{param_name}' missing from source"
                    )

        if hasattr(dest_type, "model_validate"):
            result = dest_type.model_validate(matched)  # type: ignore[attr-defined]
        else:
            result = dest_type(**matched)

        if validate:
            self._validate_result(result, validator)

        return cast("D", result)

    def auto_map_many(
        self,
        sources: list[S],
        dest_type: type[D],
        *,
        validate: bool = False,
        validator: ValidatorProtocol | None = None,
    ) -> list[D]:
        """Auto-map a list of source objects to *dest_type*.

        Args:
            sources: List of source objects.
            dest_type: The target type for each.
            validate: Whether to validate results.
            validator: Optional validator to use.

        Returns:
            List of auto-mapped destination instances.
        """
        return [
            self.auto_map(s, dest_type, validate=validate, validator=validator)
            for s in sources
        ]

    def _validate_result(
        self, result: Any, validator: ValidatorProtocol | None = None
    ) -> None:
        """Validate a mapping result.

        Args:
            result: The object to validate.
            validator: Optional validator. If not provided, and result has a
                'validate' or similar method, we could call it, but M-14
                specifically mentions using the validation subsystem.
        """
        from quadkit.mapping.exceptions import MappingExecutionError

        if validator:
            v_res = validator.validate_object(result)
            if v_res.is_err():
                raise MappingExecutionError(
                    f"Post-mapping validation failed: {v_res.unwrap_err()}"
                )

    def register_two_way(
        self,
        type_a: type,
        type_b: type,
        a_to_b: Callable[..., Any],
        b_to_a: Callable[..., Any],
    ) -> None:
        """Register bidirectional mappings between *type_a* and *type_b*.

        Args:
            type_a: First type.
            type_b: Second type.
            a_to_b: Mapping function from type_a → type_b.
            b_to_a: Mapping function from type_b → type_a.
        """
        self._registry.register(type_a, type_b, a_to_b)
        self._registry.register(type_b, type_a, b_to_a)

    def map_or_auto(self, source: S, dest_type: type[D]) -> D:
        """Use a registered mapping if available, otherwise auto-map.

        Args:
            source: The source object.
            dest_type: The target type.

        Returns:
            A new instance of *dest_type*.
        """
        if self._registry.has(type(source), dest_type):
            return self.map(source, dest_type)
        return self.auto_map(source, dest_type)


def _extract_fields(obj: Any) -> dict[str, Any]:
    """Extract a dict of field values from an arbitrary object."""
    result: dict[str, Any]
    if hasattr(obj, "model_dump"):
        result = obj.model_dump()
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result = dataclasses.asdict(obj)
    elif isinstance(obj, dict):
        result = obj
    else:
        result = vars(obj)
    return result
