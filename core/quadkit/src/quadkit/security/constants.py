"""Constants for the security subsystem.

Default error messages and codes used by guards and the GuardChain pipeline.
"""

from __future__ import annotations

# -- Environment Variable Prefixes -------------------------------------------

ENV_PREFIX: str = "QK_SECURITY__"
ENV_NESTED_DELIMITER: str = "__"

DEFAULT_GUARD_ERROR_MESSAGE: str = (
    "Access denied."  # consumed by: GuardChain default rejection
)
DEFAULT_GUARD_ERROR_CODE: str = "GUARD_DENIED"  # consumed by: GuardError.code — forward

__all__ = [
    "DEFAULT_GUARD_ERROR_CODE",
    "DEFAULT_GUARD_ERROR_MESSAGE",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
]
