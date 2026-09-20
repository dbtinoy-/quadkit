"""CORS configuration and middleware package for quadkit-web."""

from __future__ import annotations

from quadkit.web.security.config import CORSConfig
from quadkit.web.security.cors.middleware import CORSMiddleware

__all__ = ["CORSConfig", "CORSMiddleware"]
