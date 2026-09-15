"""Quadkit Validation — composable imperative validation pipeline.

Complements the declarative ``Field()`` constraints from
``quadkit.validation.schema`` with a runtime validation pipeline that
returns ``Result`` types, enabling pre-domain-object data validation.

Rules are composable and chainable; the ``ValidatorImpl`` accumulates
field-level ``FieldError`` instances and surfaces them as a
``ValidationError`` wrapped in an ``Err`` result — never raising.

Basic Usage::

    from quadkit.validation import ValidatorImpl, required, min_length, email_format

    user_validator = (
        ValidatorImpl()
        .rule("name", required(), min_length(2))
        .rule("email", required(), email_format())
    )

    result = user_validator.validate({"name": "Jo", "email": "jo@example.com"})
    if result.is_ok():
        data = result.unwrap()

Module Structure:
    - config: Configuration models (``ValidationConfig``)
    - decorators: ``@validate_input`` decorator
    - engine: Sync and async validators (``ValidatorImpl``, ``AsyncValidator``)
    - exceptions: Validation exception hierarchy (``ValidationError``, ``ValidationSystemError``)
    - module: ``ValidationModule`` IoC registration
    - rules: Built-in validation rules (``Required``, ``MinLength``, ``EmailFormat``, …)
    - schema: Pydantic schema utilities (``Field``, ``EmailStr``, ``model_validator``, …)
    - types: Type aliases (``FieldName``)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.validation.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.contracts.core.validation import (
        AsyncRuleProtocol,
        RuleProtocol,
        RuleResult,
        ValidationResult,
        ValidatorProtocol,
    )
    from quadkit.contracts.exceptions.domain import FieldError
    from quadkit.validation.config import ValidationConfig
    from quadkit.validation.constants import (
        CODE_CUSTOM,
        CODE_EMAIL,
        CODE_MAX_LENGTH,
        CODE_MIN_LENGTH,
        CODE_ONE_OF,
        CODE_PATTERN,
        CODE_RANGE,
        CODE_RANGE_MAX,
        CODE_RANGE_MIN,
        CODE_REQUIRED,
        CODE_TYPE,
    )
    from quadkit.validation.decorators import validate_input
    from quadkit.validation.engine import AsyncValidator, ValidatorImpl
    from quadkit.validation.exceptions import ValidationError, ValidationSystemError
    from quadkit.validation.module import ValidationModule
    from quadkit.validation.rules import (
        AbstractAsyncRule,
        AbstractRule,
        Custom,
        EmailFormat,
        MaxLength,
        MinLength,
        OneOf,
        Pattern,
        Range,
        Required,
        custom,
        email_format,
        max_length,
        min_length,
        one_of,
        pattern,
        range_check,
        required,
        validate_range,
        validate_required,
        validate_type,
    )
    from quadkit.validation.schema import (
        ConfigDict,
        EmailStr,
        Field,
        HttpUrl,
        SecretStr,
        field_validator,
        model_validator,
    )
    from quadkit.validation.types import FieldName

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # --- Module ---
    "ValidationModule": ("quadkit.validation.module", "ValidationModule"),
    # --- Config ---
    "ValidationConfig": ("quadkit.validation.config", "ValidationConfig"),
    # --- Exceptions ---
    "ValidationError": ("quadkit.validation.exceptions", "ValidationError"),
    "ValidationSystemError": (
        "quadkit.validation.exceptions",
        "ValidationSystemError",
    ),
    "FieldError": ("quadkit.contracts.exceptions.domain", "FieldError"),
    # --- Decorators ---
    "validate_input": ("quadkit.validation.decorators", "validate_input"),
    # --- Fields ---
    "ConfigDict": ("quadkit.validation.schema", "ConfigDict"),
    "EmailStr": ("quadkit.validation.schema", "EmailStr"),
    "Field": ("quadkit.validation.schema", "Field"),
    "HttpUrl": ("quadkit.validation.schema", "HttpUrl"),
    "SecretStr": ("quadkit.validation.schema", "SecretStr"),
    "field_validator": ("quadkit.validation.schema", "field_validator"),
    "model_validator": ("quadkit.validation.schema", "model_validator"),
    # --- Rules (classes) ---
    "AbstractAsyncRule": ("quadkit.validation.rules", "AbstractAsyncRule"),
    "AbstractRule": ("quadkit.validation.rules", "AbstractRule"),
    "Custom": ("quadkit.validation.rules", "Custom"),
    "EmailFormat": ("quadkit.validation.rules", "EmailFormat"),
    "MaxLength": ("quadkit.validation.rules", "MaxLength"),
    "MinLength": ("quadkit.validation.rules", "MinLength"),
    "OneOf": ("quadkit.validation.rules", "OneOf"),
    "Pattern": ("quadkit.validation.rules", "Pattern"),
    "Range": ("quadkit.validation.rules", "Range"),
    "Required": ("quadkit.validation.rules", "Required"),
    # --- Rules (factory functions) ---
    "custom": ("quadkit.validation.rules", "custom"),
    "email_format": ("quadkit.validation.rules", "email_format"),
    "max_length": ("quadkit.validation.rules", "max_length"),
    "min_length": ("quadkit.validation.rules", "min_length"),
    "one_of": ("quadkit.validation.rules", "one_of"),
    "pattern": ("quadkit.validation.rules", "pattern"),
    "range_check": ("quadkit.validation.rules", "range_check"),
    "required": ("quadkit.validation.rules", "required"),
    # --- Result-based helpers (merged from helpers.py → rules.py) ---
    "validate_range": ("quadkit.validation.rules", "validate_range"),
    "validate_required": ("quadkit.validation.rules", "validate_required"),
    "validate_type": ("quadkit.validation.rules", "validate_type"),
    # --- Validator ---
    "AsyncValidator": ("quadkit.validation.engine", "AsyncValidator"),
    "ValidatorImpl": ("quadkit.validation.engine", "ValidatorImpl"),
    # --- Types ---
    "FieldName": ("quadkit.validation.types", "FieldName"),
    # --- Constants ---
    "CODE_REQUIRED": ("quadkit.validation.constants", "CODE_REQUIRED"),
    "CODE_MIN_LENGTH": ("quadkit.validation.constants", "CODE_MIN_LENGTH"),
    "CODE_MAX_LENGTH": ("quadkit.validation.constants", "CODE_MAX_LENGTH"),
    "CODE_PATTERN": ("quadkit.validation.constants", "CODE_PATTERN"),
    "CODE_RANGE": ("quadkit.validation.constants", "CODE_RANGE"),
    "CODE_RANGE_MIN": ("quadkit.validation.constants", "CODE_RANGE_MIN"),
    "CODE_RANGE_MAX": ("quadkit.validation.constants", "CODE_RANGE_MAX"),
    "CODE_ONE_OF": ("quadkit.validation.constants", "CODE_ONE_OF"),
    "CODE_EMAIL": ("quadkit.validation.constants", "CODE_EMAIL"),
    "CODE_TYPE": ("quadkit.validation.constants", "CODE_TYPE"),
    "CODE_CUSTOM": ("quadkit.validation.constants", "CODE_CUSTOM"),
    # --- Protocols (from contracts) ---
    "RuleResult": ("quadkit.contracts.core.validation", "RuleResult"),
    "ValidationResult": ("quadkit.contracts.core.validation", "ValidationResult"),
    "RuleProtocol": ("quadkit.contracts.core.validation", "RuleProtocol"),
    "AsyncRuleProtocol": ("quadkit.contracts.core.validation", "AsyncRuleProtocol"),
    "ValidatorProtocol": ("quadkit.contracts.core.validation", "ValidatorProtocol"),
}


def __getattr__(name: str) -> Any:
    """Lazy-load symbols on first access."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = [
    "CODE_CUSTOM",
    "CODE_EMAIL",
    "CODE_MAX_LENGTH",
    "CODE_MIN_LENGTH",
    "CODE_ONE_OF",
    "CODE_PATTERN",
    "CODE_RANGE",
    "CODE_RANGE_MAX",
    "CODE_RANGE_MIN",
    "CODE_REQUIRED",
    "CODE_TYPE",
    "AbstractAsyncRule",
    "AbstractRule",
    "AsyncRuleProtocol",
    "AsyncValidator",
    "ConfigDict",
    "Custom",
    "EmailFormat",
    "EmailStr",
    "Field",
    "FieldError",
    "FieldName",
    "HttpUrl",
    "MaxLength",
    "MinLength",
    "OneOf",
    "Pattern",
    "Range",
    "Required",
    "RuleProtocol",
    "RuleResult",
    "SecretStr",
    "ValidationConfig",
    "ValidationError",
    "ValidationModule",
    "ValidationResult",
    "ValidationSystemError",
    "ValidatorImpl",
    "ValidatorProtocol",
    "custom",
    "email_format",
    "field_validator",
    "max_length",
    "min_length",
    "model_validator",
    "one_of",
    "pattern",
    "range_check",
    "required",
    "validate_input",
    "validate_range",
    "validate_required",
    "validate_type",
]
