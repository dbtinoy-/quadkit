"""Web contributor discovery and registry.

Entry-point-based contributor system for extension packages to register
controllers and middleware with the web provider.
"""

from quadkit.web.contributors.discovery import ENTRY_POINT_GROUP, load_web_contributors
from quadkit.web.contributors.registry import WebContributorRegistry

__all__ = ["ENTRY_POINT_GROUP", "WebContributorRegistry", "load_web_contributors"]
