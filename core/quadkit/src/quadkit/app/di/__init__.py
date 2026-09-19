"""Integration layer for the app package.

Exports the :class:`CoreProvider` DI provider that bootstraps all
Quadkit framework sub-providers.
"""

from __future__ import annotations

from quadkit.app.di.provider import CoreProvider

__all__ = ["CoreProvider"]
