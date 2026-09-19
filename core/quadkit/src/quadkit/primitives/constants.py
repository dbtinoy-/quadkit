"""Constants for the core subsystem.

Canonical sentinel key names shared across RequestContext, middleware,
and tracing to avoid magic-string duplication.
"""

from __future__ import annotations

import importlib.metadata

__version__: str
try:
    __version__ = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"


# Context variable key names — consumed by RequestContext and middleware
REQUEST_ID_KEY: str = "request_id"  # consumed by: RequestContext.request_id_var
TENANT_ID_KEY: str = "tenant_id"  # consumed by: RequestContext.tenant_id
TRACE_ID_KEY: str = "trace_id"  # consumed by: tracing middleware — forward
SPAN_ID_KEY: str = "span_id"  # consumed by: tracing middleware — forward
USER_ID_KEY: str = "user_id"  # consumed by: RequestContext.user_id
REQUEST_PATH_KEY: str = "request_path"  # consumed by: RequestContext.request_path
REQUEST_METHOD_KEY: str = "request_method"  # consumed by: RequestContext.request_method
REQUEST_START_TIME_KEY: str = (
    "request_start_time"  # consumed by: RequestContext.start_time
)

__all__ = [
    "REQUEST_ID_KEY",
    "REQUEST_METHOD_KEY",
    "REQUEST_PATH_KEY",
    "REQUEST_START_TIME_KEY",
    "SPAN_ID_KEY",
    "TENANT_ID_KEY",
    "TRACE_ID_KEY",
    "USER_ID_KEY",
    "__version__",
]
