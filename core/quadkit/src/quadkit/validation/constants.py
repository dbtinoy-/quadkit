"""Constants for the validation subsystem.

Standard error codes used by Rule implementations to identify failures.
Used in ``FieldError.code`` to distinguish rule violations.
"""

from __future__ import annotations

import importlib.metadata

try:
    __version__: str = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"


CODE_REQUIRED: str = "required"  # consumed by: Required rule
CODE_MIN_LENGTH: str = "min_length"  # consumed by: MinLength rule
CODE_MAX_LENGTH: str = "max_length"  # consumed by: MaxLength rule
CODE_PATTERN: str = "pattern"  # consumed by: Pattern rule
CODE_RANGE: str = "range"  # consumed by: Range rule
CODE_RANGE_MIN: str = "range_min"  # consumed by: Range rule (min check)
CODE_RANGE_MAX: str = "range_max"  # consumed by: Range rule (max check)
CODE_ONE_OF: str = "one_of"  # consumed by: OneOf rule
CODE_EMAIL: str = "email_format"  # consumed by: EmailFormat rule
CODE_TYPE: str = "type"  # consumed by: type-check rules — forward
CODE_CUSTOM: str = "custom"  # consumed by: Custom rule

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
    "__version__",
]
