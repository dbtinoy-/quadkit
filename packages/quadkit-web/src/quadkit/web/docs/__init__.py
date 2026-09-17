"""Docs utilities for quadkit-web

This package provides a minimal OpenAPI generator and UI helpers used by the
WebProvider to expose /openapi.json, /docs and /redoc when enabled.
"""
from __future__ import annotations

from quadkit.web.docs.decorators import openapi
from quadkit.web.docs.generator import OpenAPIGenerator

__all__ = ["OpenAPIGenerator", "openapi"]

# Note: `SwaggerUI` and `ReDoc` placeholders were deprecated and removed.
# The WebProvider now serves pre-built templates from `templates/`.
