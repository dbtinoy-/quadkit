"""Content Security Policy package for quadkit-web."""

from __future__ import annotations

from quadkit.web.security.config import CSPConfig
from quadkit.web.security.csp.builder import CSPPolicy

__all__ = ["CSPConfig", "CSPPolicy"]
