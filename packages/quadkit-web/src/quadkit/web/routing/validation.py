"""Request parameter validation helpers using Pydantic.

Provides helpers to build a lightweight Pydantic model for query parameters and
validate them in a single step. This reduces manual parsing in the router and
provides clear validation errors.
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any, get_origin

from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.domain import DomainModel
from quadkit.logging import get_logger
from quadkit.web.routing.param_coercion import (
    _cached_get_type_hints_for_handler,
    _create_validation_model,
    _get_cached_combined_model,
    _get_cached_query_model,
    _is_simple_type,
    _set_cached_combined_model,
    _set_cached_query_model,
)

logger = get_logger(__name__)


def get_or_build_query_model(handler: Any) -> type[DomainModel] | None:
    """Build and cache a Pydantic model class for handler query parameters.

    The model includes parameters that are simple types (str/int/float/bool)
    and are not explicitly a Request, path param, or a Pydantic DomainModel
    (which are treated as body models).
    """
    # When handler is a bound method, attributes can't be set on the method object.
    # Use the underlying function object (handler.__func__) as the cache target when present.
    cache_target = getattr(handler, "__func__", handler)
    cached_model = _get_cached_query_model(handler)
    if cached_model is not None:
        return cached_model

    sig = inspect.signature(handler)
    hints = _cached_get_type_hints_for_handler(handler)

    fields: dict[str, tuple] = {}

    for name, param in sig.parameters.items():
        if name == "self":
            continue

        annotation = hints.get(name, param.annotation)

        # Skip request object or explicit DomainModel bodies
        if annotation == inspect.Parameter.empty:
            continue

        # Skip Pydantic models (handled as body)
        try:
            if isinstance(annotation, type) and issubclass(annotation, DomainModel):
                continue
        except (TypeError, AttributeError) as e:
            logger.debug("Annotation is not a type or cannot be inspected: %s", e)

        if _is_simple_type(annotation):
            default = (
                param.default if param.default is not inspect.Parameter.empty else ...
            )
            fields[name] = (annotation, default)

    if not fields:
        _set_cached_query_model(handler, None)
        return None

    model_name = f"{getattr(cache_target, '__name__', 'Handler')}_QueryModel"
    model = _create_validation_model(model_name, **fields)
    _set_cached_query_model(handler, model)
    return model


def validate_query_params(request_query: dict[str, str], handler: Any) -> DomainModel:
    """Validate and coerce query parameters using the handler's query model.

    Raises ValidationError if validation fails.
    """
    model = get_or_build_query_model(handler)

    if model is None:
        # Nothing to validate
        @dataclass(init=False)
        class EmptyModel(DomainModel):
            pass

        return EmptyModel()

    # Pydantic expects values of correct types; pass the dict of strings and let
    # pydantic coerce types where possible
    return model(**request_query)


def get_or_build_combined_model(handler: Any) -> type[DomainModel] | None:
    """Build and cache a Pydantic model class that merges path, query, and body params.

    This creates a single model with fields corresponding to simple query/path
    parameters and any parameters annotated as Pydantic models (these will be
    nested models). This allows a single call to pydantic to validate and
    coerce all inputs and produce a consistent ValidationError structure.
    """
    # Similar to query model caching, cache on the underlying function to support bound methods
    cache_target = getattr(handler, "__func__", handler)
    cached_model = _get_cached_combined_model(handler)
    if cached_model is not None:
        return cached_model

    sig = inspect.signature(handler)
    hints = _cached_get_type_hints_for_handler(handler)

    # Get explicit metadata if provided via decorators (@query, @header, etc)
    param_metadata = getattr(cache_target, "_param_metadata", [])
    metadata_by_pos = {i: m for i, m in enumerate(param_metadata)}

    fields: dict[str, tuple] = {}

    for i, (name, param) in enumerate(sig.parameters.items()):
        if name in ("self", "request"):
            continue

        annotation = hints.get(name, param.annotation)

        if annotation == inspect.Parameter.empty:
            continue

        # Determine matching source metadata
        meta = getattr(param.default, "_quadkit_param_info", None)
        if meta is None:
            meta = metadata_by_pos.get(i - 1 if "self" in sig.parameters else i)

        # Basic default value handling
        default = param.default if param.default is not inspect.Parameter.empty else ...

        # Determine if this is strictly a body parameter (Pydantic model or other complex type)
        is_pydantic = False
        try:
            if isinstance(annotation, type) and issubclass(annotation, DomainModel):
                is_pydantic = True
        except (TypeError, AttributeError):
            pass

        # Also treat plain Pydantic BaseModel subclasses as body params
        # (zero-annotation auto-injection: `body: CreateUserDTO` without @body decorator)
        if not is_pydantic:
            try:
                from pydantic import BaseModel as _PydanticBM

                if isinstance(annotation, type) and issubclass(annotation, _PydanticBM):
                    is_pydantic = True
            except ImportError:
                pass

        # If it's a simple type OR explicitly decorated for a source, add it to fields
        is_explicit_source = meta and meta.get("type") in ("header", "cookie", "form")
        # If the param has pipes, use Any so pydantic doesn't validate — the pipe does it
        has_pipes = bool(meta and meta.get("pipes"))

        if _is_simple_type(annotation) or is_explicit_source:
            # If default is a Quadkit decorator, use its internal default instead
            if hasattr(default, "_quadkit_param_info"):
                decorator_info = default._quadkit_param_info
                default = decorator_info.get("default")
                if default is ...:
                    default = ...

            if meta and meta.get("default") is not ...:
                default = meta.get("default")

            fields[name] = (Any if has_pipes else annotation, default)
            continue

        # Everything else is treated as a potential body parameter (Pydantic model, dict, list, etc)
        # unless it was explicitly decorated for something else (handled above).
        # CRITICAL: We MUST skip parameters that are intended for DI!
        # If it's a class/type that is not a DomainModel and not a recognized complex type,
        # we treat it as a DI parameter and exclude it from the Pydantic model to avoid
        # PydanticSchemaGenerationError for unknown types.
        is_complex = False
        origin = get_origin(annotation)
        if origin in (list, dict, set, tuple, Any) or annotation in (
            list,
            dict,
            set,
            tuple,
            Any,
        ):
            is_complex = True

        if is_pydantic or is_complex:
            fields[name] = (
                Any if has_pipes else annotation,
                default if default is not inspect.Parameter.empty else ...,
            )
        else:
            # Likely a DI parameter (e.g. svc: MyService) or something we don't want to validate
            logger.debug(
                "Skipping parameter '%s' (%s) from Pydantic model (assumed DI)",
                name,
                annotation,
            )
            continue

    if not fields:
        _set_cached_combined_model(handler, None)
        return None

    model_name = f"{getattr(cache_target, '__name__', 'Handler')}_CombinedModel"
    model = _create_validation_model(model_name, **fields)
    _set_cached_combined_model(handler, model)
    return model


async def validate_and_merge_request(
    request: Any,
    handler: Any,
    path_params: dict[str, Any],
) -> DomainModel | None:
    """Validate path, query, and body parameters and return a pydantic model instance.

    Returns None if there are no fields to validate for this handler.
    Raises pydantic.ValidationError when validation fails.
    """
    model = get_or_build_combined_model(handler)

    if model is None:
        return None

    data: dict[str, Any] = {}

    # Start with path params and query params (both are dict-like)
    data.update(path_params or {})
    data.update(dict(request.query_params))

    # Pull from headers and cookies if needed
    cache_target = getattr(handler, "__func__", handler)
    sig = inspect.signature(handler)
    param_metadata = getattr(cache_target, "_param_metadata", [])

    # Map parameter names to metadata (both from defaults and decorators)
    meta_by_name = {}
    param_names = list(sig.parameters.keys())
    offset = 1 if "self" in param_names else 0

    for i, (p_name, param) in enumerate(sig.parameters.items()):
        # 1. Check signature default
        info = getattr(param.default, "_quadkit_param_info", None)
        if info:
            meta_by_name[p_name] = info
        # 2. Check position-based decorator metadata
        elif i - offset >= 0 and i - offset < len(param_metadata):
            meta_by_name[p_name] = param_metadata[i - offset]

    for name, meta in meta_by_name.items():
        m_type = meta.get("type")
        lookup_name = meta.get("alias") or meta.get("name") or name

        if m_type == "header":
            val = request.headers.get(lookup_name)
            if val is not None:
                data[name] = val
        elif m_type == "cookie":
            val = request.cookies.get(lookup_name)
            if val is not None:
                data[name] = val

    # Identify fields that sub-select from JSON body or are complex types
    fields_iter = (
        getattr(model, "model_fields", None) or getattr(model, "__fields__", None) or {}
    )
    if not fields_iter and hasattr(model, "__annotations__"):
        fields_iter = {k: getattr(model, k, None) for k in model.__annotations__}

    model_field_names = list(fields_iter.keys())

    # Body fields are those that are NOT sourced from path, query, header, cookie, or form
    explicit_sources = ("header", "cookie", "form", "path", "query")
    body_field_names = []

    for f_name in model_field_names:
        meta = meta_by_name.get(f_name)
        if f_name in (path_params or {}) or f_name in request.query_params:
            continue

        if meta and meta.get("type") in explicit_sources:
            continue

        # Check annotation - only treat as body if it's NOT a simple type
        # Get annotation from model field
        ann = None
        if hasattr(model, "__annotations__") and f_name in model.__annotations__:
            ann = model.__annotations__[f_name]
        else:
            field_info = fields_iter.get(f_name)
            if field_info is not None and hasattr(field_info, "annotation"):
                ann = field_info.annotation
            elif isinstance(field_info, tuple):  # pydantic v1 fallback or tuple
                ann = field_info[0]

        if ann and _is_simple_type(ann):
            continue

        # It's a candidate for body (complex type or Pydantic model)
        body_field_names.append(f_name)

    # Check for form fields too
    form_field_names = [
        name for name, meta in meta_by_name.items() if meta.get("type") == "form"
    ]

    if body_field_names:
        body_json = None
        try:
            body_json = await request.json()
        except (ValueError, TypeError) as e:
            logger.debug("Failed to parse request.json() for body fields: %s", e)
            body_json = None

        if isinstance(body_json, dict):
            for name in body_field_names:
                # Get the annotation for this body field to check if it's a model
                ann = None
                if hasattr(model, "__annotations__") and name in model.__annotations__:
                    ann = model.__annotations__[name]

                is_model_type = False
                if ann is not None:
                    try:
                        from pydantic import BaseModel

                        if isinstance(ann, type) and issubclass(ann, BaseModel):
                            is_model_type = True
                    except ImportError:
                        pass

                if len(body_field_names) == 1 and (
                    name not in body_json or is_model_type
                ):
                    # Single body field: map whole body to it (handles both
                    # `body: CreateUserDTO` and param name collisions)
                    data[name] = body_json
                elif name in body_json:
                    data[name] = body_json[name]
        # Body is not a dict (e.g. list or literal), but we have body fields
        # If only one body field, map body to it
        elif len(body_field_names) == 1:
            data[body_field_names[0]] = body_json

    if form_field_names:
        try:
            form_data = await request.form()
            for name in form_field_names:
                meta = meta_by_name[name]
                lookup_name = meta.get("alias") or meta.get("name") or name
                val = form_data.get(lookup_name)
                if val is not None:
                    data[name] = val
        except (ValueError, TypeError) as e:
            logger.debug("Failed to parse request.form() for form fields: %s", e)

    # Let pydantic coerce types and raise ValidationError for any problems
    try:
        instance = model(**data)
    except Exception as e:  # noqa: BLE001 — duck-typing on Pydantic ValidationError (v1/v2) requires catching broadly before re-raising
        from quadkit.contracts.exceptions.domain import (
            ValidationError as QuadkitValidationError,
        )

        if isinstance(e, QuadkitValidationError):
            raise

        # Check if it's a Pydantic ValidationError
        if type(e).__name__ == "ValidationError":
            from quadkit.contracts.exceptions.domain import FieldError

            qk_errors = []
            # Extract errors from pydantic (works for v1 and v2)
            pydantic_errors = getattr(e, "errors", None)
            if callable(pydantic_errors):
                pydantic_errors = pydantic_errors()
            elif pydantic_errors is None:
                pydantic_errors = []

            for err in pydantic_errors:
                field = ".".join(str(loc) for loc in err.get("loc", []))
                qk_errors.append(
                    FieldError(
                        field=field,
                        message=err.get("msg", "Invalid value"),
                        code=err.get("type", "invalid"),
                    )
                )
            raise ValidationError("Validation failed", errors=qk_errors) from e
        raise

    # Run custom validation callables if present
    for name, meta in meta_by_name.items():
        validator = meta.get("validation")
        if validator and callable(validator):
            val = getattr(instance, name, None)
            if val is not None:
                # If validator returns False or raises, it should be treated as failure
                try:
                    res = validator(val)
                    if res is False:
                        # Create a mock Quadkit error for consistency
                        from quadkit.contracts.exceptions.domain import FieldError

                        raise ValidationError(
                            "Custom validation failed",
                            errors=[
                                FieldError(
                                    field=name,
                                    message="Value failed custom validation",
                                    code="custom_validation",
                                )
                            ],
                        )
                except (ValueError, TypeError, AssertionError) as e:
                    from quadkit.contracts.exceptions.domain import FieldError

                    raise ValidationError(
                        "Custom validation failed",
                        errors=[
                            FieldError(
                                field=name,
                                message=str(e),
                                code="custom_validation",
                            )
                        ],
                    ) from e

    return instance
