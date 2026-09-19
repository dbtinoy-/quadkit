"""Exceptions for the core subsystem.

All exceptions derive from :class:`QuadkitError` so they can be caught
uniformly at the framework level.
"""

from __future__ import annotations

from quadkit.contracts.exceptions import QuadkitError


class CoreError(QuadkitError):
    """Base exception for all core errors."""

    _code: str = "QK_ERR_CORE_005"


__all__ = [
    "CoreError",
]
