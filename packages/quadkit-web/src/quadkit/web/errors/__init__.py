"""Problem detail implementation for Quadkit Web."""

from __future__ import annotations

from quadkit.web.errors.html_error_renderer import DebugHtmlErrorRenderer
from quadkit.web.errors.mapping import (
    get_mapping_for_domain_error,
    get_retry_after_header,
    get_status_for_error,
    get_type_title_for_status,
    register_error_status,
)
from quadkit.web.errors.problem_detail import ProblemDetail

__all__ = [
    "DebugHtmlErrorRenderer",
    "ProblemDetail",
    "get_mapping_for_domain_error",
    "get_retry_after_header",
    "get_status_for_error",
    "get_type_title_for_status",
    "register_error_status",
]
