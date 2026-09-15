"""Constants for quadkit-web."""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__: str = importlib.metadata.version("quadkit-web")
except ImportError:
    __version__ = "0.0.0"

# -- Environment Variable Prefixes -------------------------------------------

ENV_PREFIX: str = "QK_WEB__"
ENV_NESTED_DELIMITER: str = "__"

# -- Default Server Configuration --------------------------------------------

DEFAULT_HOST: str = "0.0.0.0"  # noqa: S104 — config default; runner binds 127.0.0.1
DEFAULT_PORT: int = 8000
DEFAULT_WORKERS: int = 1
DEFAULT_RELOAD: bool = False
DEFAULT_BACKEND: str = "granian"  # granian | uvicorn | hypercorn | gunicorn

# -- Route Paths -------------------------------------------------------------

DEFAULT_HEALTH_PATH: str = "/health"
DEFAULT_DOCS_PATH: str = "/docs"
DEFAULT_OPENAPI_PATH: str = "/openapi.json"
DEFAULT_DEBUG_ROUTES_PATH: str = "/_debug/routes"

# -- Security Defaults -------------------------------------------------------

DEFAULT_CORS_ALLOW_ORIGINS: tuple[str, ...] = ("*",)
DEFAULT_RATE_LIMIT_REQUESTS: int = 100
DEFAULT_RATE_LIMIT_WINDOW: int = 60

# -- Pagination Defaults -----------------------------------------------------

DEFAULT_PAGE_SIZE: int = 20
DEFAULT_MAX_PAGE_SIZE: int = 100

__all__ = [
    "DEFAULT_BACKEND",
    "DEFAULT_CORS_ALLOW_ORIGINS",
    "DEFAULT_DEBUG_ROUTES_PATH",
    "DEFAULT_DOCS_PATH",
    "DEFAULT_HEALTH_PATH",
    "DEFAULT_HOST",
    "DEFAULT_MAX_PAGE_SIZE",
    "DEFAULT_OPENAPI_PATH",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_PORT",
    "DEFAULT_RATE_LIMIT_REQUESTS",
    "DEFAULT_RATE_LIMIT_WINDOW",
    "DEFAULT_RELOAD",
    "DEFAULT_WORKERS",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
]
