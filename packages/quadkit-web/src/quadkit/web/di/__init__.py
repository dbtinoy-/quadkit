"""Framework integration for quadkit-web."""

from __future__ import annotations

from quadkit.web.di.provider import WebProvider
from quadkit.web.di.rate_limit import RateLimitProvider
from quadkit.web.integrations.setup import lifespan

__all__ = ["RateLimitProvider", "WebProvider", "lifespan"]
