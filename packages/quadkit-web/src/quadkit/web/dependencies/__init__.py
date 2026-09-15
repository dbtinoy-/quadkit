"""Request state management with safe accessors."""

from __future__ import annotations

from quadkit.web.dependencies.functions import (
    get_current_user_optional,
    get_current_user_required,
    get_database,
    get_request_id,
)
from quadkit.web.dependencies.state import RequestState

__all__ = [
    "RequestState",
    "get_current_user_optional",
    "get_current_user_required",
    "get_database",
    "get_request_id",
]
