"""CSRF protection package for quadkit-web."""

from __future__ import annotations

from quadkit.web.security.config import CSRFConfig
from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

__all__ = ["CSRFConfig", "CSRFProtectionMiddleware"]
