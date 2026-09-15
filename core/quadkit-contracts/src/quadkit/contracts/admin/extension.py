"""Base classes for admin extensions.

Defines the Extension ABC and ExtensionConfig so that third-party packages
can implement admin extensions without depending on quadkit-admin.

Note: As of Phase 2e (2026-03), these types have been moved to quadkit-admin.types.
This module is retained for backward compatibility and contains only protocol-level
configurations if needed. Extension implementations should import from quadkit.admin.types.
"""

from __future__ import annotations

__all__: list[str] = []
