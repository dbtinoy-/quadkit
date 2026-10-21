"""Basic domain modelling base mixin.

This module includes ``DomainModel`` which acts as an "auto-dataclass" mixin.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import MISSING
import re as _re
from typing import (
    Any,
    ClassVar,
    get_type_hints,
)

from quadkit.domain.models.coercion import coerce_and_build
from quadkit.identity import ambient as identity_ambient
from quadkit.primitives.typing import resolve_type_hints, type_allows_none

# Infrastructure imports (new locations)
from quadkit.serialization.domain import (
    get_model_extra,
    json_serialize,
    model_dump_to_dict,
)
from quadkit.serialization.schema import build_json_schema
from quadkit.validation import ConfigDict
from quadkit.validation.engine import coerce_field_value
from quadkit.validation.schema import (
    collect_field_validators,
    collect_model_validators,
)


def _coerce_value(fname: str, val: Any, type_hints: dict[str, Any], f: Any) -> Any:
    """Apply type coercion to a field value.

    Delegates to coerce_field_value for actual implementation.
    """
    return coerce_field_value(fname, val, type_hints, f)


def _convert_pydantic_fields_for_dataclass(cls: type) -> None:
    """Convert any Pydantic FieldInfo class attributes to stdlib dataclass fields.

    This allows ``@dataclass``-decorated ``DomainModel`` subclasses to use
    ``Field(...)`` (Pydantic's real FieldInfo) without triggering the
    "non-default argument follows default argument" error.  Required fields
    (``Field(...)``) are converted to bare ``dataclasses.field()`` (no default),
    and optional fields preserve their default or factory.  Field metadata
    (title, description) is placed in ``dc.field(metadata=...)``.
    """
    import dataclasses as _dc

    try:
        from pydantic.fields import FieldInfo
    except ImportError:
        return  # pydantic not installed — nothing to do

    for attr_name in list(vars(cls)):
        value = vars(cls)[attr_name]
        if not isinstance(value, FieldInfo):
            continue

        meta: dict[str, Any] = {}
        if value.title:
            meta["title"] = str(value.title)
        if value.description:
            meta["description"] = str(value.description)
        if value.exclude:
            meta["exclude"] = True

        # Extract numeric/string constraints from annotated_types metadata objects
        # (e.g. Gt(gt=0), Ge(ge=1), Le(le=100), MinLen(min_length=2), …)
        for _constraint in getattr(value, "metadata", []):
            for _attr in (
                "gt",
                "ge",
                "lt",
                "le",
                "min_length",
                "max_length",
                "multiple_of",
                "pattern",
            ):
                if hasattr(_constraint, _attr):
                    _cv = getattr(_constraint, _attr)
                    if _cv is not None:
                        meta[_attr] = _cv

        # Pull in json_schema_extra fields (e.g. unique, index, foreign_key,
        # primary_key) so migration generators and schema tools can read them
        # from the standard dataclass field metadata.
        # Two patterns are supported:
        #   Field(json_schema_extra={"unique": True})          → merge directly
        #   Field(..., metadata={"unique": True}) (legacy)     → unpack nested
        if isinstance(getattr(value, "json_schema_extra", None), dict):
            for _k, _v in value.json_schema_extra.items():  # type: ignore[union-attr]
                if _k == "metadata" and isinstance(_v, dict):
                    meta.update(_v)
                else:
                    meta[_k] = _v

        if value.is_required():
            # Required field: replace FieldInfo with a dataclasses.field that
            # has no default so @dataclass treats it as required.
            setattr(cls, attr_name, _dc.field(metadata=meta))
        elif value.default_factory is not None:
            setattr(
                cls,
                attr_name,
                _dc.field(default_factory=value.default_factory, metadata=meta),  # type: ignore[arg-type]
            )
        else:
            setattr(cls, attr_name, _dc.field(default=value.default, metadata=meta))


_GUARD_DONE_ATTR = "_quadkit_guard_done"


def run_field_guard(model: Any) -> None:
    """Coerce and validate a dataclass-built model, once per instance.

    ``@dataclass`` regenerates ``__init__`` on the subclass, so
    ``DomainModel.__init__`` — the only place scalar coercion, ``Field(...)``
    constraints and field validators ran — never executed for the documented
    pattern::

        @dataclass
        class Product(DomainModel):
            name: str = Field(default="", min_length=3)

    A ``Field(min_length=3)`` there was documentation rather than a check, and
    an ISO timestamp handed to the constructor stayed a string. Dataclasses
    always call ``__post_init__``, so the guard is installed there (see
    ``_install_field_guard``) and this function is what runs.

    Idempotent by instance marker: ``DomainModel.__init__`` does this work
    itself and then calls ``__post_init__``, so it marks the instance first.

    Args:
        model: The instance to coerce and validate in place.
    """
    if getattr(model, _GUARD_DONE_ATTR, False):
        return
    object.__setattr__(model, _GUARD_DONE_ATTR, True)

    cls = type(model)
    dc_fields = getattr(cls, "__dataclass_fields__", None)
    if not dc_fields:
        return

    try:
        type_hints = cls._cached_type_hints or resolve_type_hints(cls)
    except (NameError, AttributeError, TypeError):
        type_hints = {}

    field_validators = getattr(cls, "_field_validators", None) or {}
    values: dict[str, Any] = {}
    for fname, f in dc_fields.items():
        if not hasattr(model, fname):
            continue
        current = getattr(model, fname)
        value = current

        # `mode="before"` runs on the raw value: `@dataclass` has already
        # assigned it, but coercion has not touched it yet, and a validator that
        # declares the storage shape of a column (an epoch integer, a JSON
        # document in a Text column) has to see that raw value.
        # `DomainModel.__init__` dispatches the same mode the same way, and the
        # two paths have to agree: one model, one behaviour.
        for mode, vfn in field_validators.get(fname, []):
            if mode == "before":
                value = vfn(cls, value)

        value = _coerce_value(fname, value, type_hints, f)
        if value is not current:
            object.__setattr__(model, fname, value)
        values[fname] = value

    cls._validate_field_constraints(dc_fields, values)

    for fname, fval in list(values.items()):
        for mode, vfn in field_validators.get(fname, []):
            if mode == "after":
                new_val = vfn(cls, fval)
                if new_val is not None:
                    object.__setattr__(model, fname, new_val)
                    values[fname] = new_val

    # ``getattr(..., None)`` is ``Any | None``, so the default has to be applied
    # before the ``.get`` rather than inside it.
    model_validators = getattr(cls, "_model_validators", None) or {}
    for validator_fn in model_validators.get("after", []):
        result = validator_fn(model)
        if result is not None and result is not model:
            for attr_k, attr_v in result.__dict__.items():
                object.__setattr__(model, attr_k, attr_v)


def _install_field_guard(cls: type) -> None:
    """Chain :func:`run_field_guard` onto the class's ``__post_init__``.

    ``__post_init__`` is the one hook a generated ``__init__`` always calls, so
    it is where a ``@dataclass`` subclass gets the same coercion and validation
    a ``DomainModel``-initialised model does. A user-defined ``__post_init__``
    is preserved and runs after the guard.

    Args:
        cls: The subclass being created.
    """
    existing = cls.__dict__.get("__post_init__")
    if getattr(existing, "_quadkit_field_guard", False):
        return

    def __post_init__(self: Any) -> None:  # noqa: N807 — the hook name is fixed by dataclasses
        run_field_guard(self)
        if existing is not None:
            existing(self)

    __post_init__._quadkit_field_guard = True  # type: ignore[attr-defined]
    cls.__post_init__ = __post_init__  # type: ignore[attr-defined]


class DomainModel:
    """Mixin providing dataclass-like helpers for easy serialization.

    Automatically applies @dataclass(init=False, eq=False) to subclasses that
    don't already have @dataclass applied, converting any Pydantic Field()
    descriptors to stdlib dataclass field() equivalents. Skips classes that
    have explicit dataclass.field() objects (expecting their own @dataclass).

    Provides Pydantic-compatible interface (model_dump, model_validate, etc.)
    backed by dataclass fields introspection.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict()
    _field_validators: ClassVar[dict[str, list[tuple[str, Any]]]] = {}
    _model_validators: ClassVar[dict[str, list[Any]]] = {}
    _cached_type_hints: ClassVar[dict[str, Any] | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Collect validators for the subclass and pre-cache type hints."""
        try:
            super().__init_subclass__(**kwargs)
        except TypeError:
            super().__init_subclass__()

        # Convert any Pydantic FieldInfo objects to stdlib dataclasses.field()
        # so that @dataclass applied to the subclass sees correct required/optional
        # semantics and field metadata rather than a bare FieldInfo sentinel.
        _convert_pydantic_fields_for_dataclass(cls)

        # Subclasses MUST be @dataclass-decorated.
        # Collect validators whether they are or not
        cls._field_validators = collect_field_validators(cls)
        cls._model_validators = collect_model_validators(cls)

        # Pre-resolve and cache type hints at class-creation time to avoid
        # repeated get_type_hints() calls on every __init__ invocation.
        hints = resolve_type_hints(cls)
        cls._cached_type_hints = hints if hints else None

        # `@dataclass` replaces `__init__`, so the coercion, constraint and
        # validator work below has to be reachable from the generated one.
        _install_field_guard(cls)

    @staticmethod
    def _ensure_dataclass(target_cls: type) -> None:
        """Auto-apply @dataclass if annotations have unconverted Field objects.

        When a subclass uses pydantic ``Field()`` defaults but is not decorated
        with ``@dataclass`` itself, ``__init_subclass__`` converts FieldInfo to
        ``dataclasses.Field`` objects.  However, without an explicit
        ``@dataclass`` decorator the Field objects stay as raw class attributes
        and never appear in ``__dataclass_fields__``.

        This method detects that situation at first instantiation and applies
        ``@dataclass(init=False)`` to fix it, then refreshes class caches.
        """
        import dataclasses as _dc

        own_annotations = vars(target_cls).get("__annotations__", {})
        dc_fields = vars(target_cls).get("__dataclass_fields__", {})

        # Check if any own annotations have a dataclasses.Field class attr
        # that isn't yet registered in __dataclass_fields__
        needs_dc = False
        for attr_name in own_annotations:
            if attr_name in dc_fields:
                continue
            val = vars(target_cls).get(attr_name)
            if isinstance(val, _dc.Field):
                needs_dc = True
                break

        if not needs_dc:
            return

        _frozen = any(
            getattr(getattr(b, "__dataclass_params__", None), "frozen", False)
            for b in target_cls.__mro__[1:]
        )
        _dc.dataclass(init=False, frozen=_frozen)(target_cls)

        # Refresh cached hints and validators after dataclass re-processing
        target_cls._field_validators = collect_field_validators(target_cls)  # type: ignore[attr-defined]
        target_cls._model_validators = collect_model_validators(target_cls)  # type: ignore[attr-defined]
        try:
            target_cls._cached_type_hints = get_type_hints(target_cls)  # type: ignore[attr-defined]
        except (NameError, AttributeError, TypeError):
            target_cls._cached_type_hints = None  # type: ignore[attr-defined]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Check if the class is a dataclass.
        # Note: We check for __dataclass_fields__ which is added by @dataclass.
        dc_fields = getattr(self, "__dataclass_fields__", None)
        if dc_fields is None:
            raise TypeError(
                f"Class {self.__class__.__name__} must be a dataclass "
                f"to use DomainModel features. Please add @dataclass."
            )

        # Auto-apply @dataclass for subclasses that have converted Field
        # objects in their annotations but no explicit @dataclass decorator.
        # This runs once per class (subsequent calls see __dataclass_fields__
        # already populated) and fixes config classes that inherit from
        # BaseConfig without their own @dataclass.
        self._ensure_dataclass(self.__class__)
        dc_fields = getattr(self.__class__, "__dataclass_fields__", {})

        try:
            type_hints = self.__class__._cached_type_hints or resolve_type_hints(
                self.__class__
            )
        except (NameError, AttributeError, TypeError):
            type_hints = {}

        for validator_fn in self.__class__._model_validators.get("before", []):
            result = validator_fn(self.__class__, kwargs)
            if isinstance(result, dict):
                kwargs = result

        self._init_from_dataclass_fields(dc_fields, type_hints, kwargs)

        extra_keys = list(kwargs.keys())
        for k in extra_keys:
            object.__setattr__(self, k, kwargs.pop(k))

        # The guard has already run on this path; the marker keeps the chained
        # `__post_init__` from repeating (and re-applying) the same work.
        object.__setattr__(self, _GUARD_DONE_ATTR, True)
        if hasattr(self, "__post_init__"):
            self.__post_init__()

        for validator_fn in self.__class__._model_validators.get("after", []):
            result = validator_fn(self)
            if result is not None and result is not self:
                for attr_k, attr_v in result.__dict__.items():
                    object.__setattr__(self, attr_k, attr_v)

    def _init_from_dataclass_fields(
        self,
        dc_fields: dict[str, Any],
        type_hints: dict[str, Any],
        kwargs: dict[str, Any],
    ) -> None:
        """Initialize from __dataclass_fields__ (dataclass-backed classes)."""
        from quadkit.contracts.exceptions.domain import FieldError, ValidationError

        field_validators = self.__class__._field_validators
        values: dict[str, Any] = {}
        missing_fields: list[str] = []

        for fname, f in dc_fields.items():
            if fname in kwargs:
                val = kwargs.pop(fname)

                for mode, vfn in field_validators.get(fname, []):
                    if mode == "before":
                        val = vfn(self.__class__, val)

                val = _coerce_value(fname, val, type_hints, f)
                values[fname] = val
            elif f.default is not MISSING:
                # Coerced like a provided value: the guard path (a generated
                # `__init__` followed by `__post_init__`) coerces whatever the
                # default left on the instance, so this path has to as well or
                # the two disagree about a defaulted field's type.
                values[fname] = _coerce_value(fname, f.default, type_hints, f)
            elif f.default_factory is not MISSING:
                values[fname] = _coerce_value(fname, f.default_factory(), type_hints, f)
            elif fname == "id":
                values[fname] = None
            else:
                missing_fields.append(fname)

        if missing_fields:
            errors = [
                FieldError(field=fname, message="Field required", code="missing")
                for fname in missing_fields
            ]
            raise ValidationError("Validation failed", errors=errors)

        for k, v in values.items():
            if k == "id" and v is None:
                id_hint = type_hints.get("id")
                if id_hint is not None and type_allows_none(id_hint):
                    object.__setattr__(self, k, None)
                else:
                    object.__setattr__(
                        self,
                        k,
                        identity_ambient.generate_for(type(self).__name__),
                    )
            else:
                object.__setattr__(self, k, v)

        self._validate_field_constraints(dc_fields, values)

        for fname, fval in values.items():
            for mode, vfn in field_validators.get(fname, []):
                if mode == "after":
                    new_val = vfn(self.__class__, fval)
                    if new_val is not None:
                        object.__setattr__(self, fname, new_val)
                        values[fname] = new_val

    @staticmethod
    def _validate_field_constraints(
        dc_fields: dict[str, Any],
        values: dict[str, Any],
    ) -> None:
        """Validate field values against metadata constraints.

        **A default is not exempt.** ``name: str = Field(default="", min_length=3)``
        is a contradiction the *declaration* contains, and the framework answers
        it by refusing to construct the model — for a caller who omits the field
        exactly as for one who passes the same value. Silently accepting the
        default would let a constraint the model documents be violated by the
        value the model itself supplies, which is how a `ge=0` counter ends up
        negative in production. The failure is loud and points at the
        declaration, and the two construction paths agree on it because both
        check whatever value the field ended up holding.
        """
        for fname, f in dc_fields.items():
            meta = getattr(f, "metadata", None)
            if not meta:
                continue
            val = values.get(fname)
            if val is None:
                continue
            gt = meta.get("gt")
            if gt is not None and val <= gt:
                msg = f"Field '{fname}' must be greater than {gt}, got {val}"
                raise ValueError(msg)
            ge = meta.get("ge")
            if ge is not None and val < ge:
                msg = (
                    f"Field '{fname}' must be greater than or equal to {ge}, got {val}"
                )
                raise ValueError(msg)
            lt = meta.get("lt")
            if lt is not None and val >= lt:
                msg = f"Field '{fname}' must be less than {lt}, got {val}"
                raise ValueError(msg)
            le = meta.get("le")
            if le is not None and val > le:
                msg = f"Field '{fname}' must be less than or equal to {le}, got {val}"
                raise ValueError(msg)
            min_length = meta.get("min_length")
            if (
                min_length is not None
                and hasattr(val, "__len__")
                and len(val) < min_length
            ):
                msg = f"Field '{fname}' must have at least {min_length} characters, got {len(val)}"
                raise ValueError(msg)
            max_length = meta.get("max_length")
            if (
                max_length is not None
                and hasattr(val, "__len__")
                and len(val) > max_length
            ):
                msg = f"Field '{fname}' must have at most {max_length} characters, got {len(val)}"
                raise ValueError(msg)
            pattern = meta.get("pattern")
            if (
                pattern is not None
                and isinstance(val, str)
                and not _re.fullmatch(pattern, val)
            ):
                msg = f"Field '{fname}' must match pattern {pattern!r}, got {val!r}"
                raise ValueError(msg)

    @property
    def model_extra(self) -> dict[str, Any] | None:
        """Return extra fields that are not declared in the model schema."""
        return get_model_extra(self)

    def model_dump(
        self,
        *,
        mode: str = "python",
        exclude: set[str] | None = None,
        include: set[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return a dict representation of the model."""
        return model_dump_to_dict(self, mode=mode, exclude=exclude, include=include)

    def _json_serialize(self, obj: Any) -> Any:
        """Recursively convert types to JSON-serializable primitives."""
        return json_serialize(obj)

    def model_dump_json(self, **kwargs: Any) -> str:
        """Return a JSON string representation of the model."""
        from quadkit.serialization import dumps

        data = self.model_dump(mode="json", **kwargs)
        return dumps(data).decode()

    @classmethod
    def model_validate(cls, data: dict[str, Any], **kwargs: Any) -> Any:
        """Create an instance from a dictionary, coercing scalar types."""
        return coerce_and_build(cls, data)

    @classmethod
    def model_validate_json(cls, json_str: str, **kwargs: Any) -> Any:
        """Create an instance from a JSON string."""
        from quadkit.serialization import loads

        data = loads(json_str)
        return cls(**data)

    def model_copy(
        self,
        *,
        update: dict[str, Any] | None = None,
        deep: bool = False,
    ) -> Any:
        """Create a copy of the model with optional updates."""
        data = deepcopy(self.model_dump()) if deep else self.model_dump()

        if update:
            data.update(update)
        return type(self)(**data)

    @classmethod
    def model_json_schema(cls) -> dict[str, Any]:
        """Generate JSON schema for the model."""
        annotations = getattr(cls, "__annotations__", {})
        dc_fields = getattr(cls, "__dataclass_fields__", {})
        return build_json_schema(annotations, dc_fields)

    def __repr__(self) -> str:
        """Return string representation."""
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.model_dump().items())
        return f"{self.__class__.__name__}({attrs})"

    def __str__(self) -> str:
        """Return string representation."""
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        """Compare two models for equality."""
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.model_dump() == other.model_dump()

    __hash__ = None  # type: ignore[assignment]

    @classmethod
    def model_rebuild(cls, **kwargs: Any) -> None:
        """No-op shim for Pydantic v2 API compatibility."""
